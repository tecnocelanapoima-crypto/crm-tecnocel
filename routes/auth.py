"""
Autenticación — registro, login y logout
Tecnocel CRM
"""

import hashlib
import logging
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db

auth_bp = Blueprint('auth', __name__)
logger  = logging.getLogger(__name__)

# ── Rate limiting en memoria ─────────────────────────────────────────────────
# Estructura: { ip: {'intentos': int, 'bloqueado_hasta': datetime | None} }
# Nota: se reinicia al reiniciar el servidor. Suficiente para un deploy single-process.
_intentos_fallidos: dict = defaultdict(lambda: {'intentos': 0, 'bloqueado_hasta': None})
MAX_INTENTOS     = 5   # intentos antes de bloquear
BLOQUEO_MINUTOS  = 15  # minutos de bloqueo tras superar MAX_INTENTOS

# ── Regex de validación de email ─────────────────────────────────────────────
_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


# ── Helpers de rate limiting ─────────────────────────────────────────────────

def _get_ip() -> str:
    """Retorna la IP del cliente, respetando el header X-Forwarded-For de proxies."""
    return (request.headers.get('X-Forwarded-For', request.remote_addr) or '').split(',')[0].strip()


def _verificar_rate_limit(ip: str) -> bool:
    """
    Retorna True si la IP está bloqueada.
    Limpia el bloqueo automáticamente si ya expiró.
    """
    estado = _intentos_fallidos[ip]
    if estado['bloqueado_hasta']:
        if datetime.now() < estado['bloqueado_hasta']:
            return True  # sigue bloqueada
        # El bloqueo expiró — reiniciar
        _intentos_fallidos[ip] = {'intentos': 0, 'bloqueado_hasta': None}
    return False


def _registrar_intento_fallido(ip: str) -> int:
    """
    Incrementa el contador de intentos fallidos para la IP.
    Aplica bloqueo temporal al superar MAX_INTENTOS.
    Retorna los intentos restantes antes del bloqueo (puede ser negativo).
    """
    _intentos_fallidos[ip]['intentos'] += 1
    intentos = _intentos_fallidos[ip]['intentos']
    if intentos >= MAX_INTENTOS:
        _intentos_fallidos[ip]['bloqueado_hasta'] = datetime.now() + timedelta(minutes=BLOQUEO_MINUTOS)
        logger.warning(
            "Rate limit: IP %s bloqueada por %d min tras %d intentos fallidos.",
            ip, BLOQUEO_MINUTOS, intentos
        )
    return MAX_INTENTOS - intentos


def _limpiar_intentos(ip: str) -> None:
    """Reinicia el contador de intentos al hacer login exitoso."""
    _intentos_fallidos[ip] = {'intentos': 0, 'bloqueado_hasta': None}


# ── Decorador de protección de rutas ─────────────────────────────────────────

def login_required(f):
    """
    Decorador que protege rutas autenticadas:
    - Redirige al login si no hay sesión activa.
    - Verifica que la cuenta no esté desactivada.
    - Verifica que la suscripción esté vigente (respetando días de gracia).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('negocio_id'):
            flash('Debes iniciar sesión para continuar.', 'warning')
            return redirect(url_for('auth.login'))

        db = get_db()
        negocio = db.execute(
            '''SELECT fecha_vencimiento, plan_nombre, dias_gracia, activo
               FROM negocios WHERE id = ?''',
            (session['negocio_id'],)
        ).fetchone()

        # El negocio fue eliminado de la BD — sesión huérfana
        if not negocio:
            session.clear()
            flash('Sesión inválida. Por favor inicia sesión de nuevo.', 'warning')
            return redirect(url_for('auth.login'))

        if not negocio['activo']:
            session.clear()
            flash('Tu cuenta ha sido desactivada. Contacta al administrador.', 'danger')
            return redirect(url_for('auth.login'))

        # Verificar vencimiento de suscripción con días de gracia
        fecha_venc = negocio['fecha_vencimiento']
        if fecha_venc:
            dias_gracia = negocio['dias_gracia'] or 3
            try:
                fecha_limite = (
                    datetime.strptime(fecha_venc, '%Y-%m-%d') + timedelta(days=dias_gracia)
                ).strftime('%Y-%m-%d')
            except ValueError:
                logger.error(
                    "Formato de fecha inválido para negocio id=%s: '%s'",
                    session['negocio_id'], fecha_venc
                )
                fecha_limite = fecha_venc  # usar la fecha tal cual ante error de formato

            if date.today().isoformat() > fecha_limite:
                logger.info(
                    "Suscripción vencida para negocio id=%s, redirigiendo.",
                    session['negocio_id']
                )
                return redirect(url_for('auth.suscripcion_vencida'))

        return f(*args, **kwargs)
    return decorated


# ── Rutas ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """Registro de un nuevo negocio. Crea la cuenta con plan de prueba de 14 días."""
    if session.get('negocio_id'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        nombre_negocio = request.form.get('nombre_negocio', '').strip()
        email          = request.form.get('email', '').strip().lower()
        password       = request.form.get('password', '')
        confirmar      = request.form.get('confirmar', '')
        telefono       = request.form.get('telefono', '').strip()
        ciudad         = request.form.get('ciudad', '').strip()

        # ── Validaciones de entrada ──────────────────────────────────────
        errores = []

        if not nombre_negocio:
            errores.append('El nombre del negocio es obligatorio.')
        elif len(nombre_negocio) > 100:
            errores.append('El nombre del negocio no puede superar 100 caracteres.')

        if not email:
            errores.append('El correo electrónico es obligatorio.')
        elif not _EMAIL_RE.match(email):
            errores.append('El formato del correo electrónico no es válido.')
        elif len(email) > 120:
            errores.append('El correo electrónico es demasiado largo.')

        if len(password) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres.')
        elif len(password) > 128:
            errores.append('La contraseña no puede superar 128 caracteres.')

        if password != confirmar:
            errores.append('Las contraseñas no coinciden.')

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('auth/registro.html', form=request.form)

        # ── Operaciones de base de datos ─────────────────────────────────
        try:
            db = get_db()

            existente = db.execute(
                'SELECT id FROM negocios WHERE email = ?', (email,)
            ).fetchone()
            if existente:
                flash('Este correo ya está registrado. ¿Olvidaste tu contraseña?', 'warning')
                return render_template('auth/registro.html', form=request.form)

            fecha_venc = (date.today() + timedelta(days=14)).isoformat()
            db.execute(
                '''INSERT INTO negocios
                       (nombre_negocio, email, password_hash, telefono, ciudad,
                        fecha_vencimiento, plan_nombre)
                   VALUES (?, ?, ?, ?, ?, ?, 'prueba')''',
                (nombre_negocio, email, generate_password_hash(password),
                 telefono, ciudad, fecha_venc)
            )
            db.commit()

            nuevo = db.execute(
                'SELECT id FROM negocios WHERE email = ?', (email,)
            ).fetchone()

            session['negocio_id']     = nuevo['id']
            session['negocio_nombre'] = nombre_negocio
            session['negocio_email']  = email

            logger.info("Nuevo negocio registrado: %s (id=%s)", email, nuevo['id'])
            flash(f'¡Bienvenido a Tecnocel CRM, {nombre_negocio}!', 'success')
            return redirect(url_for('index'))

        except Exception as exc:
            logger.exception("Error al registrar negocio '%s': %s", email, exc)
            flash('Ocurrió un error al crear tu cuenta. Intenta de nuevo.', 'danger')
            return render_template('auth/registro.html', form=request.form)

    return render_template('auth/registro.html', form={})


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login de negocio existente con protección básica anti-fuerza bruta."""
    if session.get('negocio_id'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        ip       = _get_ip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # ── Rate limiting ────────────────────────────────────────────────
        if _verificar_rate_limit(ip):
            logger.warning("Login bloqueado para IP %s (rate limit activo).", ip)
            flash(
                f'Demasiados intentos fallidos. Espera {BLOQUEO_MINUTOS} minutos e intenta de nuevo.',
                'danger'
            )
            return render_template('auth/login.html', email=email)

        # ── Validación básica de campos ──────────────────────────────────
        if not email or not password:
            flash('El correo y la contraseña son obligatorios.', 'danger')
            return render_template('auth/login.html', email=email)

        try:
            db = get_db()
            negocio = db.execute(
                '''SELECT id, nombre_negocio, email, password_hash, activo
                   FROM negocios WHERE email = ?''',
                (email,)
            ).fetchone()

            # ── Verificar contraseña ─────────────────────────────────────
            # Se ejecuta check_password_hash incluso si el usuario no existe para
            # que el tiempo de respuesta no revele si el email está registrado.
            hash_a_verificar = negocio['password_hash'] if negocio else generate_password_hash('__dummy__')
            password_valida  = check_password_hash(hash_a_verificar, password)

            if not negocio:
                _registrar_intento_fallido(ip)
                logger.warning("Login con email no registrado: '%s' (IP: %s)", email, ip)
                flash('El correo electrónico no está registrado.', 'danger')
                return render_template('auth/login.html', email=email)

            # ── Soporte de migración: hash SHA-256 sin sal (cuentas antiguas) ──
            if not password_valida:
                legacy_hash = hashlib.sha256(password.encode()).hexdigest()
                if negocio['password_hash'] == legacy_hash:
                    # Migrar al formato seguro Werkzeug (pbkdf2)
                    db.execute(
                        'UPDATE negocios SET password_hash = ? WHERE id = ?',
                        (generate_password_hash(password), negocio['id'])
                    )
                    db.commit()
                    password_valida = True
                    logger.info("Hash SHA-256 migrado a Werkzeug para negocio id=%s.", negocio['id'])

            if not password_valida:
                restantes = _registrar_intento_fallido(ip)
                logger.warning(
                    "Contraseña incorrecta para '%s' (IP: %s). Intentos restantes: %d",
                    email, ip, max(restantes, 0)
                )
                if restantes > 0:
                    flash(f'Contraseña incorrecta. Te quedan {max(restantes, 0)} intentos.', 'danger')
                else:
                    flash(
                        f'Demasiados intentos fallidos. Acceso bloqueado por {BLOQUEO_MINUTOS} minutos.',
                        'danger'
                    )
                return render_template('auth/login.html', email=email)

            # ── Verificar cuenta activa ──────────────────────────────────
            if not negocio['activo']:
                logger.warning("Login rechazado: cuenta desactivada para '%s'.", email)
                flash('Tu cuenta está desactivada. Contacta al soporte.', 'warning')
                return render_template('auth/login.html', email=email)

            # ── Login exitoso ────────────────────────────────────────────
            _limpiar_intentos(ip)
            session.clear()  # prevenir session fixation
            session['negocio_id']     = negocio['id']
            session['negocio_nombre'] = negocio['nombre_negocio']
            session['negocio_email']  = negocio['email']

            logger.info("Login exitoso: '%s' (id=%s, IP: %s)", email, negocio['id'], ip)
            flash(f'¡Bienvenido, {negocio["nombre_negocio"]}!', 'success')
            return redirect(url_for('index'))

        except Exception as exc:
            logger.exception("Error inesperado en login para '%s': %s", email, exc)
            flash('Ocurrió un error interno. Intenta de nuevo.', 'danger')
            return render_template('auth/login.html', email=email)

    return render_template('auth/login.html', email='')


@auth_bp.route('/logout')
def logout():
    """Cierra la sesión activa y redirige al login."""
    negocio_email = session.get('negocio_email', 'desconocido')
    session.clear()
    logger.info("Logout: '%s'", negocio_email)
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/suscripcion-vencida')
def suscripcion_vencida():
    """Página informativa cuando la suscripción del negocio ha vencido."""
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))

    negocio = None
    try:
        db = get_db()
        negocio = db.execute(
            '''SELECT nombre_negocio, email, fecha_vencimiento, plan_nombre
               FROM negocios WHERE id = ?''',
            (session['negocio_id'],)
        ).fetchone()
    except Exception as exc:
        logger.exception(
            "Error al consultar suscripción para id=%s: %s",
            session.get('negocio_id'), exc
        )

    return render_template('auth/suscripcion_vencida.html', negocio=negocio)

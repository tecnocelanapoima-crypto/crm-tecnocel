"""
Autenticación — registro, login y logout
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    """Decorador: redirige al login si no hay sesión activa.
       También verifica que la suscripción esté vigente."""
    from functools import wraps
    from datetime import date
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('negocio_id'):
            flash('Debes iniciar sesión para continuar.', 'warning')
            return redirect(url_for('auth.login'))

        # ── Verificar suscripción ───────────────────────────────────────
        db = get_db()
        negocio = db.execute(
            'SELECT fecha_vencimiento, plan_nombre, dias_gracia, activo FROM negocios WHERE id = ?',
            (session['negocio_id'],)
        ).fetchone()

        if negocio:
            if not negocio['activo']:
                session.clear()
                flash('Tu cuenta ha sido desactivada. Contacta al administrador.', 'danger')
                return redirect(url_for('auth.login'))

            fecha_venc = negocio['fecha_vencimiento']
            if fecha_venc:
                hoy = date.today().isoformat()
                dias_gracia = negocio['dias_gracia'] or 3
                # Calcular fecha límite con días de gracia
                from datetime import datetime, timedelta
                fecha_limite = (datetime.strptime(fecha_venc, '%Y-%m-%d') +
                                timedelta(days=dias_gracia)).strftime('%Y-%m-%d')
                if hoy > fecha_limite:
                    return redirect(url_for('auth.suscripcion_vencida'))

        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if session.get('negocio_id'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        nombre_negocio = request.form.get('nombre_negocio', '').strip()
        email          = request.form.get('email', '').strip().lower()
        password       = request.form.get('password', '')
        confirmar      = request.form.get('confirmar', '')
        telefono       = request.form.get('telefono', '').strip()
        ciudad         = request.form.get('ciudad', '').strip()

        errores = []
        if not nombre_negocio: errores.append('El nombre del negocio es obligatorio.')
        if not email:          errores.append('El correo es obligatorio.')
        if len(password) < 6:  errores.append('La contraseña debe tener al menos 6 caracteres.')
        if password != confirmar: errores.append('Las contraseñas no coinciden.')

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('auth/registro.html', form=request.form)

        db = get_db()
        existente = db.execute('SELECT id FROM negocios WHERE email = ?', (email,)).fetchone()
        if existente:
            flash('Este correo electrónico ya está registrado. Por favor, inicia sesión.', 'warning')
            return render_template('auth/registro.html', form=request.form)

        from datetime import date, timedelta
        fecha_venc = (date.today() + timedelta(days=14)).isoformat()

        db.execute('''
            INSERT INTO negocios (nombre_negocio, email, password_hash, telefono, ciudad, fecha_vencimiento, plan_nombre)
            VALUES (?, ?, ?, ?, ?, ?, 'prueba')
        ''', (nombre_negocio, email, generate_password_hash(password), telefono, ciudad, fecha_venc))
        db.commit()

        negocio = db.execute('SELECT id FROM negocios WHERE email = ?', (email,)).fetchone()

        session['negocio_id']     = negocio['id']
        session['negocio_nombre'] = nombre_negocio
        session['negocio_email']  = email

        flash(f'¡Bienvenido a Tecnocel CRM, {nombre_negocio}! 🎉', 'success')
        return redirect(url_for('index'))

    return render_template('auth/registro.html', form={})


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('negocio_id'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        db = get_db()
        negocio = db.execute(
            'SELECT * FROM negocios WHERE email = ?',
            (email,)
        ).fetchone()

        if not negocio:
            flash('El correo electrónico no está registrado.', 'danger')
            return render_template('auth/login.html', email=email)
        
        if not check_password_hash(negocio['password_hash'], password):
            # Soporte para migración: Verificar si es un hash SHA-256 antiguo
            import hashlib
            legacy_hash = hashlib.sha256(password.encode()).hexdigest()
            
            if negocio['password_hash'] == legacy_hash:
                # ¡Es una cuenta antigua! La actualizamos al nuevo formato de seguridad
                new_hash = generate_password_hash(password)
                db.execute('UPDATE negocios SET password_hash = ? WHERE id = ?', (new_hash, negocio['id']))
                db.commit()
            else:
                flash('La contraseña es incorrecta.', 'danger')
                return render_template('auth/login.html', email=email)

        if not negocio['activo']:
            flash('Tu cuenta está desactivada. Contacta al soporte.', 'warning')
            return render_template('auth/login.html', email=email)

        session['negocio_id']     = negocio['id']
        session['negocio_nombre'] = negocio['nombre_negocio']
        session['negocio_email']  = negocio['email']

        flash(f'¡Bienvenido, {negocio["nombre_negocio"]}!', 'success')
        return redirect(url_for('index'))

    return render_template('auth/login.html', email='')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/suscripcion-vencida')
def suscripcion_vencida():
    """Página que se muestra cuando la suscripción ha vencido."""
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))
    db = get_db()
    negocio = db.execute(
        'SELECT nombre_negocio, email, fecha_vencimiento, plan_nombre FROM negocios WHERE id = ?',
        (session['negocio_id'],)
    ).fetchone()
    return render_template('auth/suscripcion_vencida.html', negocio=negocio)

"""
Panel de Administrador — Tecnocel CRM
Solo accesible con usuario y contraseña de administrador.
Permite gestionar negocios, planes y fechas de vencimiento.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db
from datetime import date, timedelta
import os

admin_bp = Blueprint('admin', __name__)

# ── Credenciales del administrador (cambiar antes de producción) ──────────
ADMIN_USER = os.environ.get('ADMIN_USER', 'tecnocel_admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'TecnoAdmin2026!')


def admin_required(f):
    """Decorador: solo permite acceso si hay sesión de administrador."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('es_admin'):
            return redirect(url_for('admin.login_admin'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/login', methods=['GET', 'POST'])
def login_admin():
    if session.get('es_admin'):
        return redirect(url_for('admin.panel'))

    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        clave   = request.form.get('clave', '')

        if usuario == ADMIN_USER and clave == ADMIN_PASS:
            session['es_admin'] = True
            flash('Bienvenido al panel de administrador.', 'success')
            return redirect(url_for('admin.panel'))
        else:
            flash('Credenciales incorrectas.', 'danger')

    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout_admin():
    session.pop('es_admin', None)
    flash('Sesión de administrador cerrada.', 'info')
    return redirect(url_for('admin.login_admin'))


@admin_bp.route('/')
@admin_required
def panel():
    """Panel principal: lista todos los negocios con su estado de suscripción."""
    db  = get_db()
    hoy = date.today().isoformat()

    negocios = db.execute('''
        SELECT id, nombre_negocio, email, telefono, ciudad,
               plan_nombre, fecha_vencimiento, dias_gracia, activo,
               fecha_creacion
        FROM negocios
        ORDER BY fecha_creacion DESC
    ''').fetchall()

    # Estadísticas rápidas
    total       = len(negocios)
    activos     = sum(1 for n in negocios if n['activo'] and
                      (n['fecha_vencimiento'] or '9999') >= hoy)
    vencidos    = sum(1 for n in negocios if n['activo'] and
                      n['fecha_vencimiento'] and n['fecha_vencimiento'] < hoy)
    inactivos   = sum(1 for n in negocios if not n['activo'])

    return render_template('admin/panel.html',
                           negocios=negocios,
                           hoy=hoy,
                           total=total,
                           activos=activos,
                           vencidos=vencidos,
                           inactivos=inactivos)


@admin_bp.route('/renovar/<int:negocio_id>', methods=['POST'])
@admin_required
def renovar(negocio_id):
    """Renueva la suscripción de un negocio por N días desde hoy."""
    db       = get_db()
    dias     = int(request.form.get('dias', 30))
    plan     = request.form.get('plan', 'basico')
    hoy      = date.today()

    # Si ya tiene fecha futura, extender desde esa fecha; si venció, desde hoy
    negocio  = db.execute(
        'SELECT fecha_vencimiento FROM negocios WHERE id = ?', (negocio_id,)
    ).fetchone()

    if negocio and negocio['fecha_vencimiento']:
        from datetime import datetime
        fecha_actual = datetime.strptime(negocio['fecha_vencimiento'], '%Y-%m-%d').date()
        base = max(hoy, fecha_actual)  # Extender desde la fecha más reciente
    else:
        base = hoy

    nueva_fecha = (base + timedelta(days=dias)).isoformat()

    db.execute('''
        UPDATE negocios
        SET fecha_vencimiento = ?, plan_nombre = ?, activo = 1
        WHERE id = ?
    ''', (nueva_fecha, plan, negocio_id))
    db.commit()

    negocio_info = db.execute(
        'SELECT nombre_negocio FROM negocios WHERE id = ?', (negocio_id,)
    ).fetchone()
    nombre = negocio_info['nombre_negocio'] if negocio_info else f'ID {negocio_id}'

    flash(f'✅ Suscripción de "{nombre}" renovada hasta {nueva_fecha} ({plan}).', 'success')
    return redirect(url_for('admin.panel'))


@admin_bp.route('/activar/<int:negocio_id>', methods=['POST'])
@admin_required
def activar(negocio_id):
    """Activa o desactiva un negocio."""
    db     = get_db()
    accion = request.form.get('accion', 'activar')
    valor  = 1 if accion == 'activar' else 0

    db.execute('UPDATE negocios SET activo = ? WHERE id = ?', (valor, negocio_id))
    db.commit()

    msg = 'activado' if valor else 'desactivado'
    flash(f'Negocio {msg} correctamente.', 'success' if valor else 'warning')
    return redirect(url_for('admin.panel'))


@admin_bp.route('/gracia/<int:negocio_id>', methods=['POST'])
@admin_required
def cambiar_gracia(negocio_id):
    """Cambia los días de gracia de un negocio."""
    db   = get_db()
    dias = int(request.form.get('dias_gracia', 3))
    db.execute('UPDATE negocios SET dias_gracia = ? WHERE id = ?', (dias, negocio_id))
    db.commit()
    flash('Días de gracia actualizados.', 'success')
    return redirect(url_for('admin.panel'))

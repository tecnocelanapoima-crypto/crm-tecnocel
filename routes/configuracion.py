"""
Configuración del negocio — Logo, slogan y datos del perfil
"""

import base64
from flask import Blueprint, render_template, redirect, url_for, session, request, flash
from database.db import get_db
from routes.auth import login_required

configuracion_bp = Blueprint('configuracion', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@configuracion_bp.route('/', methods=['GET', 'POST'])
@login_required
def perfil():
    nid = session['negocio_id']
    db  = get_db()

    if request.method == 'POST':
        accion = request.form.get('accion', 'guardar')

        # ── Eliminar logo ──────────────────────────────────────────────────
        if accion == 'eliminar_logo':
            db.execute('UPDATE negocios SET logo_base64 = NULL WHERE id = ?', (nid,))
            db.commit()
            flash('Logo eliminado correctamente.', 'success')
            return redirect(url_for('configuracion.perfil'))

        # ── Guardar datos del perfil ───────────────────────────────────────
        nombre_negocio = request.form.get('nombre_negocio', '').strip()
        telefono       = request.form.get('telefono', '').strip()
        ciudad         = request.form.get('ciudad', '').strip()
        slogan         = request.form.get('slogan', '').strip()

        # Procesar logo si se subió uno
        logo_base64 = None
        archivo = request.files.get('logo')
        if archivo and archivo.filename:
            if not allowed_file(archivo.filename):
                flash('Formato no permitido. Usa PNG, JPG, GIF, WEBP o SVG.', 'danger')
                return redirect(url_for('configuracion.perfil'))
            contenido = archivo.read()
            if len(contenido) > MAX_SIZE_BYTES:
                flash('La imagen es demasiado grande. Máximo 2 MB.', 'danger')
                return redirect(url_for('configuracion.perfil'))
            ext = archivo.filename.rsplit('.', 1)[1].lower()
            mime = 'image/svg+xml' if ext == 'svg' else f'image/{ext}'
            logo_base64 = f'data:{mime};base64,' + base64.b64encode(contenido).decode('utf-8')

        # Actualizar base de datos
        if logo_base64:
            db.execute('''
                UPDATE negocios
                SET nombre_negocio = ?, telefono = ?, ciudad = ?, slogan = ?, logo_base64 = ?
                WHERE id = ?
            ''', (nombre_negocio, telefono, ciudad, slogan, logo_base64, nid))
        else:
            db.execute('''
                UPDATE negocios
                SET nombre_negocio = ?, telefono = ?, ciudad = ?, slogan = ?
                WHERE id = ?
            ''', (nombre_negocio, telefono, ciudad, slogan, nid))

        db.commit()

        # Actualizar nombre en sesión
        session['negocio_nombre'] = nombre_negocio
        flash('Configuración guardada correctamente.', 'success')
        return redirect(url_for('configuracion.perfil'))

    # GET — cargar datos actuales
    negocio = db.execute(
        'SELECT nombre_negocio, email, telefono, ciudad, slogan, logo_base64 FROM negocios WHERE id = ?',
        (nid,)
    ).fetchone()

    return render_template('configuracion/perfil.html', negocio=negocio)

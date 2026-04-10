"""
Configuración del negocio — Logo, datos del perfil y estilo de factura
"""

import base64
import json
import logging

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from database.db import get_db
from routes.auth import login_required

configuracion_bp = Blueprint('configuracion', __name__)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
MAX_SIZE_BYTES     = 2 * 1024 * 1024  # 2 MB

# Magic bytes → MIME type para validación real del contenido del archivo
ALLOWED_MIMES = {
    'image/png', 'image/jpeg', 'image/gif',
    'image/webp', 'image/svg+xml',
}
_MAGIC = [
    (b'\x89PNG\r\n\x1a\n',  'image/png'),
    (b'\xff\xd8\xff',        'image/jpeg'),
    (b'GIF87a',              'image/gif'),
    (b'GIF89a',              'image/gif'),
    (b'RIFF',                'image/webp'),   # los 4 primeros; webp tiene RIFF????WEBP
]


def _detectar_mime(data: bytes) -> str:
    """
    Detecta el MIME type real del archivo por sus magic bytes.
    Fallback a image/svg+xml si el contenido parece XML/SVG.
    """
    for magic, mime in _MAGIC:
        if data[:len(magic)] == magic:
            # Caso especial: RIFF puede no ser WEBP; verificar bytes 8-12
            if mime == 'image/webp' and data[8:12] != b'WEBP':
                continue
            return mime
    # SVG es XML legible — buscar firma textual
    snippet = data[:512].lstrip()
    if snippet.startswith(b'<') and (b'<svg' in snippet or b'<?xml' in snippet):
        return 'image/svg+xml'
    return 'application/octet-stream'  # tipo desconocido → será rechazado

# ── Config de factura por defecto ─────────────────────────────────────────────
DEFAULT_FACTURA_CONFIG = {
    'modelo':            'clasico',   # 'clasico' | 'moderno' | 'minimalista'
    'color_primario':    '#0088CC',   # color principal (header, botones, acentos)
    'color_header':      '#050D1A',   # color de fondo del header (solo modelo clásico)
    'mostrar_telefono':  True,
    'mostrar_ciudad':    True,
    'pie_texto':         'Este comprobante es válido para reclamaciones. Consérvelo.',
    'btn_pdf_label':     'Descargar PDF',
    'btn_wa_label':      'Enviar por WhatsApp',
}


def get_factura_config(db, negocio_id: int) -> dict:
    """
    Carga la config de factura del negocio, fusionada con los valores por defecto.
    Siempre retorna un dict completo aunque no haya config guardada.
    """
    config = DEFAULT_FACTURA_CONFIG.copy()
    try:
        row = db.execute(
            'SELECT factura_config FROM negocios WHERE id = ?', (negocio_id,)
        ).fetchone()
        if row and row['factura_config']:
            guardado = json.loads(row['factura_config'])
            config.update(guardado)
    except Exception as exc:
        logger.warning("No se pudo cargar factura_config para negocio %s: %s", negocio_id, exc)
    return config


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@configuracion_bp.route('/', methods=['GET', 'POST'])
@login_required
def perfil():
    nid = session['negocio_id']
    db  = get_db()

    if request.method == 'POST':
        accion = request.form.get('accion', 'guardar')

        # ── Eliminar logo ────────────────────────────────────────────────
        if accion == 'eliminar_logo':
            db.execute('UPDATE negocios SET logo_base64 = NULL WHERE id = ?', (nid,))
            db.commit()
            flash('Logo eliminado correctamente.', 'success')
            return redirect(url_for('configuracion.perfil'))

        # ── Guardar datos del negocio ────────────────────────────────────
        if accion == 'guardar':
            nombre_negocio = request.form.get('nombre_negocio', '').strip()
            telefono       = request.form.get('telefono', '').strip()
            ciudad         = request.form.get('ciudad', '').strip()
            slogan         = request.form.get('slogan', '').strip()

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
                # Validar MIME real leyendo los magic bytes del archivo
                mime_real = _detectar_mime(contenido)
                if mime_real not in ALLOWED_MIMES:
                    flash('El archivo no es una imagen válida. Usa PNG, JPG, GIF, WEBP o SVG.', 'danger')
                    return redirect(url_for('configuracion.perfil'))
                logo_base64 = f'data:{mime_real};base64,' + base64.b64encode(contenido).decode('utf-8')

            if logo_base64:
                db.execute(
                    '''UPDATE negocios
                       SET nombre_negocio=?, telefono=?, ciudad=?, slogan=?, logo_base64=?
                       WHERE id=?''',
                    (nombre_negocio, telefono, ciudad, slogan, logo_base64, nid)
                )
            else:
                db.execute(
                    '''UPDATE negocios
                       SET nombre_negocio=?, telefono=?, ciudad=?, slogan=?
                       WHERE id=?''',
                    (nombre_negocio, telefono, ciudad, slogan, nid)
                )
            db.commit()
            session['negocio_nombre'] = nombre_negocio
            flash('Configuración guardada correctamente.', 'success')
            return redirect(url_for('configuracion.perfil') + '#tab-negocio')

        # ── Guardar configuración de factura ─────────────────────────────
        if accion == 'guardar_factura':
            config = {
                'modelo':           request.form.get('modelo', 'clasico'),
                'color_primario':   request.form.get('color_primario', DEFAULT_FACTURA_CONFIG['color_primario']),
                'color_header':     request.form.get('color_header',   DEFAULT_FACTURA_CONFIG['color_header']),
                'mostrar_telefono': request.form.get('mostrar_telefono') == '1',
                'mostrar_ciudad':   request.form.get('mostrar_ciudad')   == '1',
                'pie_texto':        request.form.get('pie_texto',   DEFAULT_FACTURA_CONFIG['pie_texto']).strip(),
                'btn_pdf_label':    request.form.get('btn_pdf_label', DEFAULT_FACTURA_CONFIG['btn_pdf_label']).strip(),
                'btn_wa_label':     request.form.get('btn_wa_label',  DEFAULT_FACTURA_CONFIG['btn_wa_label']).strip(),
            }
            # Validar modelo
            if config['modelo'] not in ('clasico', 'moderno', 'minimalista'):
                config['modelo'] = 'clasico'

            db.execute(
                'UPDATE negocios SET factura_config=? WHERE id=?',
                (json.dumps(config, ensure_ascii=False), nid)
            )
            db.commit()
            logger.info("factura_config actualizada para negocio %s: modelo=%s", nid, config['modelo'])
            flash('Estilo de factura guardado correctamente.', 'success')
            return redirect(url_for('configuracion.perfil') + '#tab-factura')

    # ── GET — cargar datos actuales ──────────────────────────────────────
    negocio = db.execute(
        'SELECT nombre_negocio, email, telefono, ciudad, slogan, logo_base64 FROM negocios WHERE id=?',
        (nid,)
    ).fetchone()
    factura_cfg = get_factura_config(db, nid)

    return render_template('configuracion/perfil.html', negocio=negocio, factura_cfg=factura_cfg)

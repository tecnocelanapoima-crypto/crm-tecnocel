"""
Módulo de Órdenes de Trabajo — Tecnocel CRM
Gestiona el flujo completo: Recibido → Listo → Entregado
Con notificaciones WhatsApp en cada cambio de estado
"""

import os
import uuid
import json
import base64
import io
import urllib.parse
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database.db import get_db
from routes.auth import login_required
from datetime import datetime
from werkzeug.utils import secure_filename
import platform
import subprocess
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

ordenes_bp = Blueprint('ordenes', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def limpiar_telefono(telefono):
    numero = ''.join(filter(str.isdigit, telefono or ''))
    if not numero: return None
    if numero.startswith('0'): numero = numero[1:]
    if len(numero) == 10: numero = '57' + numero
    return numero


def init_ordenes_table():
    """Crea la tabla de órdenes si no existe"""
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS ordenes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            negocio_id      INTEGER NOT NULL,
            cliente_id      INTEGER NOT NULL,
            numero_orden    TEXT    NOT NULL,
            marca_modelo    TEXT    NOT NULL,
            problema        TEXT    NOT NULL,
            foto            TEXT,
            estado          TEXT    NOT NULL DEFAULT 'recibido',
            costo_estimado  REAL,
            abono           REAL    DEFAULT 0,
            tipo_pago_abono TEXT    DEFAULT 'Efectivo',
            saldo_pendiente REAL    DEFAULT 0,
            costo_final     REAL,
            notas_tecnico   TEXT,
            fecha_recibido  TEXT    NOT NULL,
            fecha_listo     TEXT,
            fecha_entregado TEXT,
            fecha_creacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE CASCADE,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
        )
    ''')
    db.commit()

    # Agregar columnas faltantes si la tabla ya existe (migracion segura)
    for col, definition in [
        ('abono',           'REAL DEFAULT 0'),
        ('tipo_pago_abono', "TEXT DEFAULT 'Efectivo'"),
        ('saldo_pendiente', 'REAL DEFAULT 0'),
    ]:
        try:
            db.execute(f'ALTER TABLE ordenes ADD COLUMN {col} {definition}')
            db.commit()
        except Exception:
            pass  # La columna ya existe


def generar_pdf_recepcion(orden, cliente, negocio, factura_config=None):
    """
    Genera el comprobante de recepción con el estilo visual personalizado
    del negocio (logo, colores, slogan) configurado en Configuración → Estilo.
    """
    import shutil
    from routes.configuracion import DEFAULT_FACTURA_CONFIG

    # ── Configuración de estilo ───────────────────────────────────────────────
    cfg = DEFAULT_FACTURA_CONFIG.copy()
    if factura_config:
        cfg.update(factura_config)

    C_DARK  = colors.HexColor('#050D1A')
    C_DARK2 = colors.HexColor('#0A1628')
    C_DARK3 = colors.HexColor('#0D1E35')
    C_MGRAY = colors.HexColor('#4A6A80')
    C_LGRAY = colors.HexColor('#A0C4D8')
    C_WHITE = colors.white
    C_ACENT = colors.HexColor(cfg.get('color_primario', '#00CFFF'))  # color del usuario
    C_HEAD  = colors.HexColor(cfg.get('color_header',   '#050D1A'))

    # ── Datos del negocio ─────────────────────────────────────────────────────
    neg_nombre   = (negocio['nombre_negocio'] if negocio and negocio['nombre_negocio'] else 'Tecnocel')
    neg_slogan   = (negocio['slogan']         if negocio and negocio['slogan']         else 'Venta y soporte de celulares')
    neg_email    = (negocio['email']          if negocio and negocio['email']          else '')
    neg_telefono = (negocio['telefono']       if negocio and negocio['telefono']       else '')
    neg_logo_b64 = (negocio['logo_base64']    if negocio and negocio['logo_base64']    else None)

    # ── Carpeta organizada por año / mes / día ────────────────────────────────
    ahora    = datetime.now()
    meses_es = {1:'Enero',2:'Febrero',3:'Marzo',4:'Abril',5:'Mayo',6:'Junio',
                7:'Julio',8:'Agosto',9:'Septiembre',10:'Octubre',11:'Noviembre',12:'Diciembre'}
    carpeta  = os.path.join('facturas', ahora.strftime('%Y'), meses_es[ahora.month], ahora.strftime('%d'))
    os.makedirs(carpeta, exist_ok=True)
    os.makedirs('facturas_pdf', exist_ok=True)

    hora           = ahora.strftime('%H-%M-%S')
    nombre_archivo = f"recepcion_{orden['numero_orden'].replace('-', '_')}_{hora}.pdf"
    ruta           = os.path.join(carpeta, nombre_archivo)
    ruta_legacy    = os.path.join('facturas_pdf', nombre_archivo)

    W = A4[0] - 3.6 * cm

    doc = SimpleDocTemplate(ruta, pagesize=A4,
                            rightMargin=1.8*cm, leftMargin=1.8*cm,
                            topMargin=1.5*cm,  bottomMargin=1.5*cm)

    # ── Estilos de texto ──────────────────────────────────────────────────────
    estilos = getSampleStyleSheet()

    def ep(nombre, **kw):
        base = kw.pop('base', 'Normal')
        return ParagraphStyle(nombre, parent=estilos[base], **kw)

    st_sub   = ep('sub',  fontSize=9,  textColor=C_LGRAY, alignment=TA_CENTER, spaceAfter=1)
    st_label = ep('lbl',  fontSize=9,  textColor=C_LGRAY, fontName='Helvetica-Bold')
    st_val   = ep('val',  fontSize=10, textColor=C_WHITE)
    st_sec   = ep('sec',  fontSize=9,  textColor=C_ACENT, fontName='Helvetica-Bold', spaceAfter=0)
    st_ot    = ep('ot',   fontSize=26, textColor=C_ACENT, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=4)
    st_foot  = ep('foot', fontSize=8,  textColor=C_LGRAY, alignment=TA_CENTER, spaceAfter=2)
    st_total = ep('tot',  fontSize=12, textColor=C_ACENT, fontName='Helvetica-Bold', alignment=TA_RIGHT)

    # ── Fondo oscuro ──────────────────────────────────────────────────────────
    def fondo(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C_DARK)
        canvas.rect(0, 0, A4[0], A4[1], fill=True, stroke=False)
        canvas.restoreState()

    contenido = []

    # ── ENCABEZADO con logo personalizado ─────────────────────────────────────
    if neg_logo_b64:
        try:
            b64_data = neg_logo_b64.split(',', 1)[1] if ',' in neg_logo_b64 else neg_logo_b64
            logo_img = Image(io.BytesIO(base64.b64decode(b64_data)),
                             width=8.5*cm, height=2.2*cm)
            logo_img.hAlign = 'CENTER'
            logo_cell = logo_img
        except Exception:
            logo_cell = Paragraph(
                f'<b><font color="{cfg["color_primario"]}" size="20">{neg_nombre}</font></b>',
                estilos['Title'])
    else:
        logo_cell = Paragraph(
            f'<b><font color="{cfg["color_primario"]}" size="20">{neg_nombre}</font></b>',
            estilos['Title'])

    header_data = [
        [logo_cell],
        [Paragraph(neg_slogan, st_sub)],
    ]
    if neg_email:
        header_data.append([Paragraph(neg_email, st_sub)])
    if neg_telefono:
        header_data.append([Paragraph(f'Tel: {neg_telefono}', st_sub)])

    ht = Table(header_data, colWidths=[W])
    ht.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,-1), colors.HexColor(cfg.get('color_header','#050D1A'))),
        ('ALIGN',        (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',   (0,0),(-1,0),  14),
        ('BOTTOMPADDING',(0,-1),(-1,-1),10),
        ('LEFTPADDING',  (0,0),(-1,-1), 8),
        ('RIGHTPADDING', (0,0),(-1,-1), 8),
        ('LINEBELOW',    (0,-1),(-1,-1), 2, C_ACENT),
    ]))
    contenido += [ht, Spacer(1, 0.4*cm)]

    # ── Título: número de orden ───────────────────────────────────────────────
    meta = Table(
        [[Paragraph('COMPROBANTE DE RECEPCIÓN', st_sec),
          Paragraph(datetime.now().strftime('%d/%m/%Y  %H:%M'), st_sub)]],
        colWidths=[W * 0.6, W * 0.4]
    )
    meta.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,-1), C_DARK2),
        ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',   (0,0),(-1,-1), 7),
        ('BOTTOMPADDING',(0,0),(-1,-1), 7),
        ('LEFTPADDING',  (0,0),(-1,-1), 10),
        ('RIGHTPADDING', (0,0),(-1,-1), 10),
        ('ALIGN',        (1,0),(1,-1),  'RIGHT'),
        ('BOX',          (0,0),(-1,-1), 1, C_ACENT),
    ]))
    contenido += [meta, Spacer(1, 0.2*cm)]
    contenido.append(Paragraph(orden['numero_orden'], st_ot))
    contenido.append(HRFlowable(width='100%', thickness=1.5, color=C_ACENT))
    contenido.append(Spacer(1, 0.4*cm))

    # ── Sección: datos del cliente ────────────────────────────────────────────
    sec_c = Table([[Paragraph('  ▌  DATOS DEL CLIENTE', st_sec)]], colWidths=[W])
    sec_c.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,-1), C_DARK3),
        ('TOPPADDING',   (0,0),(-1,-1), 6),
        ('BOTTOMPADDING',(0,0),(-1,-1), 6),
        ('LEFTPADDING',  (0,0),(-1,-1), 8),
        ('LINEBEFORE',   (0,0),(0,-1),  3, C_ACENT),
        ('LINEBELOW',    (0,-1),(-1,-1), 0.5, C_MGRAY),
    ]))
    contenido += [sec_c, Spacer(1, 0.12*cm)]

    filas_c = [
        [Paragraph('Nombre',   st_label), Paragraph(cliente['nombre'].title(), st_val)],
        [Paragraph('Teléfono', st_label), Paragraph(cliente['telefono'] or '—', st_val)],
    ]
    if cliente.get('ciudad'):
        filas_c.append([Paragraph('Ciudad', st_label), Paragraph(cliente['ciudad'], st_val)])

    tc = Table(filas_c, colWidths=[W * 0.28, W * 0.72])
    tc.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,-1), C_DARK2),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[C_DARK2, C_DARK3]),
        ('TOPPADDING',   (0,0),(-1,-1), 7),
        ('BOTTOMPADDING',(0,0),(-1,-1), 7),
        ('LEFTPADDING',  (0,0),(-1,-1), 10),
        ('RIGHTPADDING', (0,0),(-1,-1), 10),
        ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ('BOX',          (0,0),(-1,-1), 1, colors.HexColor('#0088AA')),
        ('LINEBELOW',    (0,0),(-1,-2), 0.3, C_MGRAY),
    ]))
    contenido += [tc, Spacer(1, 0.4*cm)]

    # ── Sección: datos del equipo ─────────────────────────────────────────────
    sec_e = Table([[Paragraph('  ▌  DETALLE DEL EQUIPO', st_sec)]], colWidths=[W])
    sec_e.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,-1), C_DARK3),
        ('TOPPADDING',   (0,0),(-1,-1), 6),
        ('BOTTOMPADDING',(0,0),(-1,-1), 6),
        ('LEFTPADDING',  (0,0),(-1,-1), 8),
        ('LINEBEFORE',   (0,0),(0,-1),  3, C_ACENT),
        ('LINEBELOW',    (0,-1),(-1,-1), 0.5, C_MGRAY),
    ]))
    contenido += [sec_e, Spacer(1, 0.12*cm)]

    filas_e = [
        [Paragraph('Equipo',    st_label), Paragraph(orden['marca_modelo'], st_val)],
        [Paragraph('Problema',  st_label), Paragraph(orden['problema'],     st_val)],
    ]
    if orden.get('notas_tecnico'):
        filas_e.append([Paragraph('Notas', st_label), Paragraph(orden['notas_tecnico'], st_val)])

    te = Table(filas_e, colWidths=[W * 0.28, W * 0.72])
    te.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,-1), C_DARK2),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[C_DARK2, C_DARK3]),
        ('TOPPADDING',   (0,0),(-1,-1), 7),
        ('BOTTOMPADDING',(0,0),(-1,-1), 7),
        ('LEFTPADDING',  (0,0),(-1,-1), 10),
        ('RIGHTPADDING', (0,0),(-1,-1), 10),
        ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ('BOX',          (0,0),(-1,-1), 1, colors.HexColor('#0088AA')),
        ('LINEBELOW',    (0,0),(-1,-2), 0.3, C_MGRAY),
    ]))
    contenido += [te, Spacer(1, 0.4*cm)]

    # ── Sección: costos ───────────────────────────────────────────────────────
    sec_p = Table([[Paragraph('  ▌  COSTOS Y PAGOS', st_sec)]], colWidths=[W])
    sec_p.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,-1), C_DARK3),
        ('TOPPADDING',   (0,0),(-1,-1), 6),
        ('BOTTOMPADDING',(0,0),(-1,-1), 6),
        ('LEFTPADDING',  (0,0),(-1,-1), 8),
        ('LINEBEFORE',   (0,0),(0,-1),  3, C_ACENT),
        ('LINEBELOW',    (0,-1),(-1,-1), 0.5, C_MGRAY),
    ]))
    contenido += [sec_p, Spacer(1, 0.12*cm)]

    fmt = lambda v: '$ ' + f'{int(v or 0):,}'.replace(',', '.')
    tipo_pago = orden['tipo_pago_abono'] or 'Efectivo'
    filas_p = [
        [Paragraph('Costo estimado', st_label),
         Paragraph(fmt(orden['costo_estimado']), st_val)],
        [Paragraph(f'Abono ({tipo_pago})', st_label),
         Paragraph(fmt(orden['abono']),          st_val)],
        [Paragraph('Saldo pendiente', ep('sp', fontSize=10, textColor=C_ACENT, fontName='Helvetica-Bold')),
         Paragraph(fmt(orden['saldo_pendiente']),
                   ep('sv', fontSize=10, textColor=C_ACENT, fontName='Helvetica-Bold', alignment=TA_RIGHT))],
    ]

    tp = Table(filas_p, colWidths=[W * 0.5, W * 0.5])
    tp.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,1),  C_DARK2),
        ('BACKGROUND',   (0,2),(-1,2),  colors.HexColor('#000000')),
        ('ROWBACKGROUNDS',(0,0),(-1,1),[C_DARK2, C_DARK3]),
        ('TOPPADDING',   (0,0),(-1,-1), 8),
        ('BOTTOMPADDING',(0,0),(-1,-1), 8),
        ('LEFTPADDING',  (0,0),(-1,-1), 10),
        ('RIGHTPADDING', (0,0),(-1,-1), 10),
        ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ('ALIGN',        (1,0),(1,-1),  'RIGHT'),
        ('BOX',          (0,0),(-1,-1), 1, colors.HexColor('#0088AA')),
        ('LINEABOVE',    (0,2),(-1,2),  1.5, C_ACENT),
        ('LINEBELOW',    (0,2),(-1,2),  1.5, C_ACENT),
        ('LINEBELOW',    (0,0),(-1,1),  0.3, C_MGRAY),
    ]))
    contenido += [tp, Spacer(1, 0.8*cm)]

    # ── Pie ───────────────────────────────────────────────────────────────────
    pie_texto = cfg.get('pie_texto', 'Conserve este comprobante. Le avisaremos cuando su equipo esté listo.')
    contenido.append(HRFlowable(width='100%', thickness=1.5, color=C_ACENT))
    contenido.append(Spacer(1, 0.25*cm))
    pie_t = Table([
        [Paragraph(f'¡Gracias por confiar en <font color="{cfg["color_primario"]}"><b>{neg_nombre}</b></font>!', st_foot)],
        [Paragraph(pie_texto, ep('fp2', fontSize=8, textColor=C_MGRAY, alignment=TA_CENTER))],
    ], colWidths=[W])
    pie_t.setStyle(TableStyle([
        ('BACKGROUND',   (0,0),(-1,-1), colors.HexColor('#000000')),
        ('TOPPADDING',   (0,0),(-1,-1), 6),
        ('BOTTOMPADDING',(0,0),(-1,-1), 6),
        ('ALIGN',        (0,0),(-1,-1), 'CENTER'),
    ]))
    contenido.append(pie_t)

    # ── Construir PDF ─────────────────────────────────────────────────────────
    doc.build(contenido, onFirstPage=fondo, onLaterPages=fondo)

    try:
        shutil.copy2(ruta, ruta_legacy)
    except Exception:
        pass

    return ruta, nombre_archivo


@ordenes_bp.before_app_request
def setup_ordenes():
    """Inicializa la tabla al arrancar"""
    try:
        init_ordenes_table()
    except Exception:
        pass


@ordenes_bp.route('/')
@login_required
def lista():
    nid = session['negocio_id']
    db  = get_db()
    estado = request.args.get('estado', '')
    buscar = request.args.get('buscar', '').strip()

    if buscar:
        termino = f'%{buscar}%'
        ordenes = db.execute('''
            SELECT o.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ordenes o JOIN clientes c ON o.cliente_id = c.id
            WHERE o.negocio_id = ? AND (c.nombre LIKE ? OR c.telefono LIKE ? OR o.numero_orden LIKE ?)
            ORDER BY o.fecha_creacion DESC
        ''', (nid, termino, termino, termino)).fetchall()
    elif estado:
        ordenes = db.execute('''
            SELECT o.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ordenes o JOIN clientes c ON o.cliente_id = c.id
            WHERE o.negocio_id = ? AND o.estado = ?
            ORDER BY o.fecha_creacion DESC
        ''', (nid, estado)).fetchall()
    else:
        ordenes = db.execute('''
            SELECT o.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ordenes o JOIN clientes c ON o.cliente_id = c.id
            WHERE o.negocio_id = ?
            ORDER BY o.fecha_creacion DESC
        ''', (nid,)).fetchall()

    # Contadores por estado
    contadores = db.execute('''
        SELECT estado, COUNT(*) as total
        FROM ordenes WHERE negocio_id = ?
        GROUP BY estado
    ''', (nid,)).fetchall()

    contadores_dict = {r['estado']: r['total'] for r in contadores}

    from datetime import date
    clientes = db.execute(
        'SELECT id, nombre FROM clientes WHERE negocio_id = ? ORDER BY nombre', (nid,)
    ).fetchall()
    hoy = date.today().isoformat()

    return render_template('ordenes/lista.html',
                           ordenes=ordenes,
                           estado_filtro=estado,
                           contadores=contadores_dict,
                           clientes=clientes,
                           hoy=hoy)


@ordenes_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear():
    nid = session['negocio_id']
    db  = get_db()

    if request.method == 'POST':
        cliente_nombre   = request.form.get('cliente_nombre', '').strip().title()
        cliente_telefono = request.form.get('cliente_telefono', '').strip()
        marca_modelo  = request.form.get('marca_modelo', '').strip()
        problema      = request.form.get('problema', '').strip()
        costo_estimado = request.form.get('costo_estimado', '').strip()
        abono          = request.form.get('abono', '0').strip()
        tipo_pago_abono = request.form.get('tipo_pago_abono', 'Efectivo').strip()
        notas_tecnico = request.form.get('notas_tecnico', '').strip()
        fecha_recibido= request.form.get('fecha_recibido', datetime.now().strftime('%Y-%m-%d'))

        abono_num       = float(abono) if abono else 0
        costo_num       = float(costo_estimado) if costo_estimado else 0
        saldo_pendiente = max(costo_num - abono_num, 0)

        errores = []
        if not cliente_nombre:   errores.append('El nombre del cliente es obligatorio.')
        if not cliente_telefono: errores.append('El teléfono del cliente es obligatorio.')
        if not marca_modelo: errores.append('Marca y modelo son obligatorios.')
        if not problema:     errores.append('El problema es obligatorio.')

        if errores:
            for e in errores: flash(e, 'danger')
            return render_template('ordenes/form.html', form=request.form, hoy=datetime.now().strftime('%Y-%m-%d'))

        # Buscar si ya existe ese cliente en este negocio por teléfono
        cliente = db.execute(
            'SELECT id FROM clientes WHERE negocio_id = ? AND telefono = ?',
            (nid, cliente_telefono)
        ).fetchone()

        if cliente:
            cliente_id = cliente['id']
        else:
            db.execute(
                'INSERT INTO clientes (negocio_id, nombre, telefono) VALUES (?, ?, ?)',
                (nid, cliente_nombre, cliente_telefono)
            )
            db.commit()
            cliente_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Generar número de orden único
        ultimo = db.execute(
            'SELECT COUNT(*) FROM ordenes WHERE negocio_id = ?', (nid,)
        ).fetchone()[0]
        numero_orden = f'OT-{nid:03d}-{(ultimo+1):04d}'

        # Guardar foto si existe
        foto_filename = None
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '' and allowed_file(file.filename):
                from flask import current_app
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{ext}"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'ordenes')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                foto_filename = filename

        db.execute('''
            INSERT INTO ordenes
            (negocio_id, cliente_id, numero_orden, marca_modelo, problema, foto, estado,
             costo_estimado, abono, saldo_pendiente, notas_tecnico, fecha_recibido)
            VALUES (?, ?, ?, ?, ?, ?, 'recibido', ?, ?, ?, ?, ?)
        ''', (nid, cliente_id, numero_orden, marca_modelo, problema, foto_filename,
              costo_num, abono_num, saldo_pendiente, notas_tecnico, fecha_recibido))
        db.commit()

        orden_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        flash(f'Orden {numero_orden} creada exitosamente.', 'success')

        # Si el técnico presionó "Crear + PDF + WhatsApp", generar PDF y abrir WA directamente
        accion = request.form.get('accion', 'solo_crear')
        if accion == 'crear_y_confirmar':
            return redirect(url_for('ordenes.confirmar_recepcion', id=orden_id))

        return redirect(url_for('ordenes.detalle', id=orden_id))

    return render_template('ordenes/form.html',
                           form={}, hoy=datetime.now().strftime('%Y-%m-%d'))


@ordenes_bp.route('/<int:id>')
@login_required
def detalle(id):
    nid = session['negocio_id']
    db  = get_db()
    orden = db.execute('''
        SELECT o.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono,
               c.cedula as cliente_cedula, c.ciudad as cliente_ciudad
        FROM ordenes o JOIN clientes c ON o.cliente_id = c.id
        WHERE o.id = ? AND o.negocio_id = ?
    ''', (id, nid)).fetchone()

    if not orden:
        flash('Orden no encontrada.', 'danger')
        return redirect(url_for('ordenes.lista'))

    return render_template('ordenes/detalle.html', orden=orden)


@ordenes_bp.route('/<int:id>/confirmar-recepcion')
@login_required
def confirmar_recepcion(id):
    negocio_id = session.get('negocio_id')
    if not negocio_id:
        return redirect(url_for('auth.login'))

    db = get_db()

    orden = db.execute(
        'SELECT * FROM ordenes WHERE id = ? AND negocio_id = ?',
        (id, negocio_id)
    ).fetchone()

    if not orden:
        flash('Orden no encontrada.', 'danger')
        return redirect(url_for('ordenes.lista'))

    cliente = db.execute(
        'SELECT * FROM clientes WHERE id = ?', (orden['cliente_id'],)
    ).fetchone()

    negocio = db.execute(
        'SELECT * FROM negocios WHERE id = ?', (negocio_id,)
    ).fetchone()

    # Cargar factura_config del negocio para aplicar estilo personalizado al PDF
    factura_cfg = None
    if negocio and negocio['factura_config']:
        try:
            factura_cfg = json.loads(negocio['factura_config'])
        except Exception:
            pass

    # Generar PDF con estilo personalizado
    ruta_pdf, nombre_archivo = generar_pdf_recepcion(orden, cliente, negocio, factura_cfg)

    # Abrir la carpeta organizada por fecha en Windows Explorer
    carpeta_fecha = os.path.abspath(os.path.dirname(ruta_pdf))
    if platform.system() == 'Windows':
        subprocess.Popen(['explorer', carpeta_fecha])

    # Construir mensaje WhatsApp
    numero = limpiar_telefono(cliente['telefono'])
    negocio_nombre = negocio['nombre_negocio'] if negocio else 'Tecnocel'
    
    costo_fmt  = '$ ' + f'{int(orden["costo_estimado"] or 0):,}'.replace(',', '.')
    abono_fmt  = '$ ' + f'{int(orden["abono"] or 0):,}'.replace(',', '.')
    saldo_fmt  = '$ ' + f'{int(orden["saldo_pendiente"] or 0):,}'.replace(',', '.')

    mensaje = (
        f"Hola {cliente['nombre'].title()}, hemos recibido tu equipo "
        f"{orden['marca_modelo']} correctamente. "
        f"Tu número de orden es *{orden['numero_orden']}*. "
        f"Costo total: *{costo_fmt}*. "
        f"Abono recibido: *{abono_fmt}* ({orden['tipo_pago_abono'] or 'Efectivo'}). "
        f"Saldo pendiente: *{saldo_fmt}*. "
        f"Te avisamos cuando esté listo. — {negocio_nombre}"
    )

    url_whatsapp = f"https://wa.me/{numero}?text={urllib.parse.quote(mensaje)}"

    flash(f'Comprobante generado: {nombre_archivo}', 'success')

    # Si es petición AJAX, devolver JSON para que el JS abra WA en nueva pestaña
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from flask import jsonify
        return jsonify({'ok': True, 'wa_url': url_whatsapp, 'pdf': nombre_archivo})

    # Fallback para petición directa (abre WA en la misma pestaña)
    return redirect(url_whatsapp)


@ordenes_bp.route('/<int:id>/cambiar-estado', methods=['POST'])
@login_required
def cambiar_estado(id):
    nid = session['negocio_id']
    nuevo_estado = request.form.get('estado', '')
    costo_final  = request.form.get('costo_final', '').strip()

    if nuevo_estado not in ['recibido', 'listo', 'entregado']:
        flash('Estado no válido.', 'danger')
        return redirect(url_for('ordenes.detalle', id=id))

    db = get_db()
    orden = db.execute(
        'SELECT * FROM ordenes WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()

    if not orden:
        flash('Orden no encontrada.', 'danger')
        return redirect(url_for('ordenes.lista'))

    hoy = datetime.now().strftime('%Y-%m-%d')
    fecha_listo     = orden['fecha_listo']
    fecha_entregado = orden['fecha_entregado']
    costo_f         = orden['costo_final']

    if nuevo_estado == 'listo':
        fecha_listo = hoy
    if nuevo_estado == 'entregado':
        fecha_entregado = hoy
        if costo_final:
            costo_f = float(costo_final)

    db.execute('''
        UPDATE ordenes SET estado=?, fecha_listo=?, fecha_entregado=?, costo_final=?
        WHERE id=? AND negocio_id=?
    ''', (nuevo_estado, fecha_listo, fecha_entregado, costo_f, id, nid))
    db.commit()
    # NOTA: Las órdenes entregadas se registran únicamente en la tabla ordenes.
    # No se crea venta automática para evitar duplicados en Trabajos Completos.

    estados = {'recibido': 'Recibido', 'listo': 'Listo para retirar', 'entregado': 'Entregado'}
    flash(f'Estado cambiado a "{estados[nuevo_estado]}".', 'success')
    return redirect(url_for('ordenes.detalle', id=id))


@ordenes_bp.route('/<int:id>/whatsapp/<tipo>')
@login_required
def whatsapp(id, tipo):
    """Envía mensaje WhatsApp según el tipo: recibido, listo, factura"""
    nid = session['negocio_id']
    db  = get_db()
    orden = db.execute('''
        SELECT o.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
        FROM ordenes o JOIN clientes c ON o.cliente_id = c.id
        WHERE o.id = ? AND o.negocio_id = ?
    ''', (id, nid)).fetchone()

    if not orden:
        flash('Orden no encontrada.', 'danger')
        return redirect(url_for('ordenes.lista'))

    negocio_nombre = session.get('negocio_nombre', 'Tecnocel')
    numero = limpiar_telefono(orden['cliente_telefono'])

    if not numero:
        flash('El cliente no tiene número de teléfono.', 'warning')
        return redirect(url_for('ordenes.detalle', id=id))

    if tipo == 'recibido':
        mensaje = (
            f"Hola {orden['cliente_nombre']} 👋\n\n"
            f"✅ Hemos recibido tu equipo en *{negocio_nombre}*.\n\n"
            f"📋 *Orden:* {orden['numero_orden']}\n"
            f"📱 *Equipo:* {orden['marca_modelo']}\n"
            f"🔧 *Problema reportado:* {orden['problema']}\n"
            f"📅 *Fecha de recepción:* {orden['fecha_recibido']}\n"
            + ("Costo estimado: $ " + '{:,.0f}'.format(orden['costo_estimado']) + '\n\n' if orden['costo_estimado'] else '\n\n')
            + "Te notificaremos cuando esté listo. ¡Gracias por confiar en nosotros! 🙏"
        )
    elif tipo == 'listo':
        mensaje = (
            f"Hola {orden['cliente_nombre']} 👋\n\n"
            f"🎉 ¡Tu equipo está *LISTO* para retirar!\n\n"
            f"📋 *Orden:* {orden['numero_orden']}\n"
            f"📱 *Equipo:* {orden['marca_modelo']}\n"
            + ("Valor a pagar: $ " + '{:,.0f}'.format(orden['costo_final']) + '\n\n' if orden['costo_final'] else '\n\n')
            + f"Puedes pasar a recogerlo en *{negocio_nombre}*.\n"
            f"¡Te esperamos! 😊"
        )
    elif tipo == 'factura':
        costo = orden['costo_final'] or orden['costo_estimado'] or 0
        mensaje = (
            f"Hola {orden['cliente_nombre']} 👋\n\n"
            f"✅ Gracias por recoger tu equipo en *{negocio_nombre}*.\n\n"
            f"📋 *Orden:* {orden['numero_orden']}\n"
            f"📱 *Equipo:* {orden['marca_modelo']}\n"
            f"🔧 *Servicio:* {orden['problema']}\n"
            f"💰 *Total pagado:* $ {costo:,.0f}\n"
            f"📅 *Fecha:* {orden['fecha_entregado'] or datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"¡Gracias por tu preferencia! Cualquier garantía comunícate con nosotros. 🙏"
        )
    else:
        flash('Tipo de mensaje no válido.', 'danger')
        return redirect(url_for('ordenes.detalle', id=id))

    url_wa = f"https://wa.me/{numero}?text={urllib.parse.quote(mensaje)}"
    return redirect(url_wa)


@ordenes_bp.route('/recepcion-rapida', methods=['POST'])
@login_required
def recepcion_rapida():
    """Recepción rápida de equipos - Solo los datos esenciales"""
    nid = session['negocio_id']
    db  = get_db()

    nombre_cliente = request.form.get('nombre_cliente_rapida', '').strip().title()
    telefono_cliente = request.form.get('telefono_cliente_rapida', '').strip()
    marca_modelo = request.form.get('marca_modelo_rapida', '').strip()
    problema = request.form.get('problema_rapida', '').strip()
    costo_estimado = request.form.get('costo_estimado_rapida', '').strip()

    # Validaciones
    es_ajax = request.form.get('origen') == 'modal'

    def error(msg):
        if es_ajax:
            from flask import jsonify
            return jsonify({'error': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('ordenes.lista'))

    if not nombre_cliente:   return error('El nombre del cliente es obligatorio.')
    if not telefono_cliente: return error('El teléfono es obligatorio.')
    if not marca_modelo:     return error('La marca/modelo es obligatoria.')
    if not problema:         return error('El problema es obligatorio.')

    # Convertir costo estimado a número
    costo_estimado_num = None
    if costo_estimado:
        try:
            costo_estimado_num = float(costo_estimado)
        except ValueError:
            return error('El costo estimado debe ser un número válido.')

    # Buscar o crear cliente
    cliente = db.execute(
        'SELECT id FROM clientes WHERE negocio_id = ? AND telefono = ?',
        (nid, telefono_cliente)
    ).fetchone()
    
    if cliente:
        cliente_id = cliente['id']
    else:
        db.execute(
            'INSERT INTO clientes (negocio_id, nombre, telefono) VALUES (?, ?, ?)',
            (nid, nombre_cliente, telefono_cliente)
        )
        db.commit()
        cliente_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Generar número de orden
    ultima_orden = db.execute(
        'SELECT numero_orden FROM ordenes WHERE negocio_id = ? ORDER BY id DESC LIMIT 1',
        (nid,)
    ).fetchone()
    
    if ultima_orden:
        ultimo_num = int(ultima_orden['numero_orden'].split('-')[-1])
        nuevo_num = f"OT-{nid:03d}-{ultimo_num + 1:04d}"
    else:
        nuevo_num = f"OT-{nid:03d}-0001"

    # Crear la orden
    fecha_hoy = datetime.now().strftime('%Y-%m-%d')
    db.execute(
        '''INSERT INTO ordenes
           (negocio_id, cliente_id, numero_orden, marca_modelo, problema,
            estado, costo_estimado, abono, saldo_pendiente, fecha_recibido)
           VALUES (?, ?, ?, ?, ?, 'recibido', ?, 0, ?, ?)''',
        (nid, cliente_id, nuevo_num, marca_modelo, problema,
         costo_estimado_num or 0, costo_estimado_num or 0, fecha_hoy)
    )
    db.commit()
    orden_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    flash(f'Equipo registrado. Orden: {nuevo_num}', 'success')

    # Construir URL de WhatsApp directamente
    negocio = db.execute('SELECT * FROM negocios WHERE id = ?', (nid,)).fetchone()
    negocio_nombre = negocio['nombre_negocio'] if negocio else 'Tecnocel'
    numero = limpiar_telefono(telefono_cliente)
    costo_fmt = '$ ' + f'{int(costo_estimado_num or 0):,}'.replace(',', '.')
    mensaje = (
        f"Hola {nombre_cliente}, hemos recibido tu equipo {marca_modelo} correctamente. "
        f"Problema reportado: {problema}. "
        f"Costo estimado: {costo_fmt}. "
        f"Te avisamos cuando esté listo. — {negocio_nombre}"
    )
    wa_url = f"https://wa.me/{numero}?text={urllib.parse.quote(mensaje)}" if numero else None

    # Si viene del modal (fetch), devolver JSON
    if es_ajax:
        from flask import jsonify
        return jsonify({'success': True, 'whatsapp_url': wa_url, 'numero_orden': nuevo_num})

    return redirect(wa_url) if wa_url else redirect(url_for('ordenes.lista'))


@ordenes_bp.route('/recepcion_rapida', methods=['POST'])
@login_required
def recepcion_rapida_v2():
    db = get_db()
    nid = session.get('negocio_id')

    nombre = request.form.get('nombre_cliente_rapida', '').strip().title()
    telefono = request.form.get('telefono_rapida', '').strip()
    marca_modelo = request.form.get('marca_modelo_rapida', '').strip()
    problema = request.form.get('problema_rapido', '').strip()
    costo = request.form.get('costo_estimado_rapido', 0)
    try:
        costo = float(costo) if costo else 0
    except ValueError:
        costo = 0

    # Buscar o crear cliente
    cliente = db.execute('SELECT id FROM clientes WHERE negocio_id = ? AND telefono = ?', (nid, telefono)).fetchone()
    if not cliente:
        db.execute('INSERT INTO clientes (negocio_id, nombre, telefono) VALUES (?, ?, ?)', (nid, nombre, telefono))
        db.commit()
        cliente_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    else:
        cliente_id = cliente['id']

    # Generar número de orden consistente con el resto del sistema
    ultima = db.execute('SELECT numero_orden FROM ordenes WHERE negocio_id = ? ORDER BY id DESC LIMIT 1', (nid,)).fetchone()
    if ultima:
        try:
            ultimo_num = int(ultima['numero_orden'].split('-')[-1])
        except (ValueError, IndexError):
            ultimo_num = 0
        numero_orden = f'OT-{nid:03d}-{ultimo_num + 1:04d}'
    else:
        numero_orden = f'OT-{nid:03d}-0001'

    # Guardar orden
    fecha_hoy = datetime.now().strftime('%Y-%m-%d')
    db.execute('''INSERT INTO ordenes (negocio_id, cliente_id, numero_orden, marca_modelo, problema,
                  estado, costo_estimado, abono, saldo_pendiente, fecha_recibido)
                  VALUES (?, ?, ?, ?, ?, 'recibido', ?, 0, ?, ?)''',
               (nid, cliente_id, numero_orden, marca_modelo, problema, costo, costo, fecha_hoy))
    db.commit()

    # WhatsApp
    negocio = db.execute('SELECT * FROM negocios WHERE id = ?', (nid,)).fetchone()
    negocio_nombre = negocio['nombre_negocio'] if negocio else 'Tecnocel'
    numero = limpiar_telefono(telefono)
    mensaje = f'Hola {nombre}, recibimos tu equipo {marca_modelo}. Número de orden: {numero_orden}. Te avisamos cuando esté listo. — {negocio_nombre}'
    whatsapp_url = f'https://wa.me/{numero}?text={urllib.parse.quote(mensaje)}' if numero else None

    return jsonify({'success': True, 'whatsapp_url': whatsapp_url, 'numero_orden': numero_orden})

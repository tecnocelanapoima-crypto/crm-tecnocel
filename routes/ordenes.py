"""
Módulo de Órdenes de Trabajo — Tecnocel CRM
Gestiona el flujo completo: Recibido → Listo → Entregado
Con notificaciones WhatsApp en cada cambio de estado
"""

import os
import uuid
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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

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


def generar_pdf_recepcion(orden, cliente, negocio):
    # ── Carpeta organizada por año / mes / día ────────────────────────────────
    ahora       = datetime.now()
    meses_es    = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    anio   = ahora.strftime('%Y')
    mes    = meses_es[ahora.month]
    dia    = ahora.strftime('%d')
    hora   = ahora.strftime('%H-%M-%S')

    carpeta = os.path.join('facturas', anio, mes, dia)
    os.makedirs(carpeta, exist_ok=True)

    # Mantener también la carpeta facturas_pdf para compatibilidad
    os.makedirs('facturas_pdf', exist_ok=True)

    nombre_archivo = f"recepcion_{orden['numero_orden'].replace('-', '_')}_{hora}.pdf"
    ruta           = os.path.join(carpeta, nombre_archivo)
    ruta_legacy    = os.path.join('facturas_pdf', nombre_archivo)

    doc = SimpleDocTemplate(ruta, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle('titulo', fontSize=20, alignment=TA_CENTER,
                                   fontName='Helvetica-Bold', spaceAfter=4)
    estilo_sub    = ParagraphStyle('sub', fontSize=11, alignment=TA_CENTER,
                                   textColor=colors.grey, spaceAfter=2)
    estilo_ot     = ParagraphStyle('ot', fontSize=28, alignment=TA_CENTER,
                                   fontName='Helvetica-Bold', textColor=colors.HexColor('#1a73e8'),
                                   spaceAfter=6)
    estilo_label  = ParagraphStyle('label', fontSize=9, textColor=colors.grey)
    estilo_valor  = ParagraphStyle('valor', fontSize=11, fontName='Helvetica-Bold')
    estilo_nota   = ParagraphStyle('nota', fontSize=9, alignment=TA_CENTER,
                                   textColor=colors.grey, spaceBefore=10)

    fecha_hora = datetime.now().strftime('%d/%m/%Y  %H:%M')
    nombre_negocio = negocio['nombre_negocio'] if negocio else 'Tecnocel'
    telefono_negocio = negocio['telefono'] if negocio else ''

    contenido = []

    # Encabezado negocio
    contenido.append(Paragraph(nombre_negocio.upper(), estilo_titulo))
    if telefono_negocio:
        contenido.append(Paragraph(f'Tel: {telefono_negocio}', estilo_sub))
    contenido.append(Spacer(1, 0.3*cm))
    contenido.append(HRFlowable(width='100%', thickness=1.5,
                                color=colors.HexColor('#1a73e8')))
    contenido.append(Spacer(1, 0.4*cm))

    # Título comprobante
    contenido.append(Paragraph('COMPROBANTE DE RECEPCIÓN', estilo_sub))
    contenido.append(Paragraph(orden['numero_orden'], estilo_ot))
    contenido.append(HRFlowable(width='100%', thickness=0.5, color=colors.lightgrey))
    contenido.append(Spacer(1, 0.5*cm))

    # Tabla de datos
    datos = [
        ['Fecha y hora:', fecha_hora],
        ['Cliente:', cliente['nombre'].title()],
        ['Teléfono:', cliente['telefono']],
        ['Equipo:', orden['marca_modelo']],
        ['Problema reportado:', orden['problema']],
        ['Costo estimado:', f"$ {int(orden['costo_estimado'] or 0):,}".replace(',', '.')],
        ['Abono recibido:', f"$ {int(orden['abono'] or 0):,}".replace(',', '.') + f" ({orden['tipo_pago_abono'] if orden['tipo_pago_abono'] else 'Efectivo'})"],
        ['Saldo pendiente:', f"$ {int(orden['saldo_pendiente'] or 0):,}".replace(',', '.')],
    ]

    tabla = Table(datos, colWidths=[5*cm, 11*cm])
    tabla.setStyle(TableStyle([
        ('FONTNAME',    (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE',    (0,0), (-1,-1), 10),
        ('TEXTCOLOR',  (0,0), (0,-1), colors.grey),
        ('TEXTCOLOR',  (1,0), (1,-1), colors.black),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, colors.HexColor('#f5f8ff')]),
        ('TOPPADDING',  (0,0), (-1,-1), 7),
        ('BOTTOMPADDING',(0,0),(-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('GRID',        (0,0), (-1,-1), 0.3, colors.HexColor('#e0e0e0')),
        ('ROUNDEDCORNERS', [4]),
    ]))
    contenido.append(tabla)
    contenido.append(Spacer(1, 0.8*cm))
    contenido.append(HRFlowable(width='100%', thickness=0.5, color=colors.lightgrey))
    contenido.append(Paragraph(
        'Conserve este comprobante. Le avisaremos cuando su equipo esté listo.',
        estilo_nota))

    doc.build(contenido)

    # Copiar también a facturas_pdf para compatibilidad con el resto del sistema
    import shutil
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

    # Generar PDF
    ruta_pdf, nombre_archivo = generar_pdf_recepcion(orden, cliente, negocio)

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
            f"{'Costo estimado: $ ' + '{:,.0f}'.format(orden['costo_estimado']) + '\n\n' if orden['costo_estimado'] else '\n\n'}"
            f"Te notificaremos cuando esté listo. ¡Gracias por confiar en nosotros! 🙏"
        )
    elif tipo == 'listo':
        mensaje = (
            f"Hola {orden['cliente_nombre']} 👋\n\n"
            f"🎉 ¡Tu equipo está *LISTO* para retirar!\n\n"
            f"📋 *Orden:* {orden['numero_orden']}\n"
            f"📱 *Equipo:* {orden['marca_modelo']}\n"
            f"{'Valor a pagar: $ ' + '{:,.0f}'.format(orden['costo_final']) + '\n\n' if orden['costo_final'] else '\n\n'}"
            f"Puedes pasar a recogerlo en *{negocio_nombre}*.\n"
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

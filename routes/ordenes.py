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

    if estado:
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
    return render_template('ordenes/lista.html',
                           ordenes=ordenes,
                           estado_filtro=estado,
                           contadores=contadores_dict)


@ordenes_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear():
    nid = session['negocio_id']
    db  = get_db()

    if request.method == 'POST':
        cliente_id    = request.form.get('cliente_id', '').strip()
        marca_modelo  = request.form.get('marca_modelo', '').strip()
        problema      = request.form.get('problema', '').strip()
        costo_estimado= request.form.get('costo_estimado', '').strip()
        notas_tecnico = request.form.get('notas_tecnico', '').strip()
        fecha_recibido= request.form.get('fecha_recibido', datetime.now().strftime('%Y-%m-%d'))

        errores = []
        if not cliente_id:   errores.append('Debe seleccionar un cliente.')
        if not marca_modelo: errores.append('Marca y modelo son obligatorios.')
        if not problema:     errores.append('El problema es obligatorio.')

        if errores:
            for e in errores: flash(e, 'danger')
            clientes = db.execute(
                'SELECT id, nombre, telefono FROM clientes WHERE negocio_id = ? ORDER BY nombre', (nid,)
            ).fetchall()
            return render_template('ordenes/form.html', clientes=clientes,
                                   form=request.form, hoy=datetime.now().strftime('%Y-%m-%d'))

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

        costo_est = float(costo_estimado) if costo_estimado else None

        db.execute('''
            INSERT INTO ordenes
            (negocio_id, cliente_id, numero_orden, marca_modelo, problema,
             foto, estado, costo_estimado, notas_tecnico, fecha_recibido)
            VALUES (?, ?, ?, ?, ?, ?, 'recibido', ?, ?, ?)
        ''', (nid, cliente_id, numero_orden, marca_modelo, problema,
              foto_filename, costo_est, notas_tecnico, fecha_recibido))
        db.commit()

        orden_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        flash(f'Orden {numero_orden} creada exitosamente.', 'success')
        return redirect(url_for('ordenes.detalle', id=orden_id))

    clientes = db.execute(
        'SELECT id, nombre, telefono FROM clientes WHERE negocio_id = ? ORDER BY nombre', (nid,)
    ).fetchall()
    return render_template('ordenes/form.html', clientes=clientes,
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

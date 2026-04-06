from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db
from routes.auth import login_required
from datetime import date
import os
import platform
import subprocess
import urllib.parse

ventas_bp = Blueprint('ventas', __name__)


def generar_pdf_venta(venta_id, nid):
    from routes.facturas import generar_pdf
    try:
        db = get_db()
        venta = db.execute(
            'SELECT v.*, c.nombre as cliente_nombre, c.cedula, c.telefono, c.direccion, c.ciudad '
            'FROM ventas v JOIN clientes c ON v.cliente_id = c.id '
            'WHERE v.id = ? AND v.negocio_id = ?', (venta_id, nid)
        ).fetchone()
        negocio = db.execute(
            'SELECT * FROM negocios WHERE id = ?', (nid,)
        ).fetchone()
        # La función generar_pdf espera venta y cliente. Usamos el mismo objeto unido.
        ruta, nombre = generar_pdf(venta, venta)
        return ruta, venta, negocio
    except Exception:
        return None, None, None


@ventas_bp.route('/')
@login_required
def lista():
    nid = session['negocio_id']
    db  = get_db()
    cliente_id = request.args.get('cliente_id', '')

    if cliente_id:
        ventas = db.execute('''
            SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ventas v JOIN clientes c ON v.cliente_id = c.id
            WHERE v.negocio_id = ? AND v.cliente_id = ?
            ORDER BY v.fecha DESC
        ''', (nid, cliente_id)).fetchall()
    else:
        ventas = db.execute('''
            SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ventas v JOIN clientes c ON v.cliente_id = c.id
            WHERE v.negocio_id = ?
            ORDER BY v.fecha_creacion DESC
        ''', (nid,)).fetchall()

    total_ingresos = sum(v['precio'] for v in ventas)
    return render_template('ventas/lista.html', ventas=ventas, total_ingresos=total_ingresos)


@ventas_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear():
    nid = session['negocio_id']
    db  = get_db()

    if request.method == 'POST':
        cliente_nombre   = request.form.get('cliente_nombre', '').strip().title()
        cliente_telefono = request.form.get('cliente_telefono', '').strip()
        producto   = request.form.get('producto', '').strip()
        precio     = request.form.get('precio', '').strip()
        tipo_pago  = request.form.get('tipo_pago', 'contado').strip()
        fecha      = request.form.get('fecha', '').strip()
        notas      = request.form.get('notas', '').strip()

        # Si viene del modal y está vacío, es Cliente Exprés
        if not cliente_nombre and not cliente_telefono:
            cliente_nombre = "Cliente Exprés"
            cliente_telefono = "0000000000"

        errores = []
        if not cliente_nombre: errores.append('El nombre del cliente es obligatorio.')
        if not producto:   errores.append('El producto es obligatorio.')
        if not fecha:      errores.append('La fecha es obligatoria.')
        if not precio:
            errores.append('El precio es obligatorio.')
        else:
            try:
                precio = float(precio)
                if precio <= 0: errores.append('El precio debe ser mayor a 0.')
            except ValueError:
                errores.append('El precio debe ser un número válido.')

        if errores:
            for e in errores: flash(e, 'danger')
            return render_template('ventas/form.html', form=request.form, hoy=date.today().isoformat())

        # Buscar o crear cliente por teléfono
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

        db.execute('''
            INSERT INTO ventas (negocio_id, cliente_id, producto, precio, tipo_pago, fecha, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nid, cliente_id, producto, precio, tipo_pago, fecha, notas))
        db.commit()
        venta_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        # ── NUEVA LÓGICA: PDF + WHATSAPP ──────────────────────────────────────

        # Obtener datos completos para el mensaje
        venta_obj = db.execute(
            'SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono '
            'FROM ventas v JOIN clientes c ON v.cliente_id = c.id '
            'WHERE v.id = ?', (venta_id,)
        ).fetchone()
        
        negocio = db.execute(
            'SELECT * FROM negocios WHERE id = ?', (nid,)
        ).fetchone()

        # Generar PDF usando la función existente
        try:
            from routes.facturas import generar_pdf
            ruta_pdf, nombre_pdf = generar_pdf(venta_obj, venta_obj)
            flash(f'Venta registrada. PDF generado: {nombre_pdf}', 'success')
        except Exception:
            flash(f'Venta de "{producto}" registrada. (PDF no generado)', 'success')

        # Abrir carpeta facturas_pdf en Windows
        carpeta = os.path.abspath('facturas_pdf')
        if platform.system() == 'Windows':
            subprocess.Popen(['explorer', carpeta])

        # Armar mensaje WhatsApp
        nombre_cliente = venta_obj['cliente_nombre'].title()
        telefono       = ''.join(filter(str.isdigit, venta_obj['cliente_telefono'] or ''))
        nombre_negocio = negocio['nombre_negocio'] if negocio else 'Tecnocel'
        precio_fmt     = '$ ' + f'{int(precio):,}'.replace(',', '.')
        
        mensaje = (
            f"Hola {nombre_cliente}, gracias por tu compra en {nombre_negocio}. "
            f"Producto: {producto}. "
            f"Total: {precio_fmt}. "
            f"Metodo de pago: {tipo_pago}. "
            f"Que lo disfrutes!"
        )
        
        # Eliminar prefijo si ya existe o asegurar el de Colombia
        if telefono.startswith('57'): telefono = telefono
        elif len(telefono) == 10: telefono = '57' + telefono

        url_wa = f"https://wa.me/{telefono}?text={urllib.parse.quote(mensaje)}"
        return redirect(url_wa)

    return render_template('ventas/form.html',
                           form={},
                           hoy=date.today().isoformat())


@ventas_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    nid = session['negocio_id']
    db  = get_db()
    venta = db.execute(
        'SELECT * FROM ventas WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()

    if not venta:
        flash('Venta no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))

    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id', '').strip()
        producto   = request.form.get('producto', '').strip()
        precio     = request.form.get('precio', '').strip()
        tipo_pago  = request.form.get('tipo_pago', 'contado').strip()
        fecha      = request.form.get('fecha', '').strip()
        notas      = request.form.get('notas', '').strip()

        errores = []
        if not cliente_id: errores.append('Debe seleccionar un cliente.')
        if not producto:   errores.append('El producto es obligatorio.')
        if not fecha:      errores.append('La fecha es obligatoria.')
        if not precio:
            errores.append('El precio es obligatorio.')
        else:
            try: precio = float(precio)
            except ValueError: errores.append('El precio debe ser un número válido.')

        if errores:
            for e in errores: flash(e, 'danger')
            clientes = db.execute(
                'SELECT id, nombre FROM clientes WHERE negocio_id = ? ORDER BY nombre', (nid,)
            ).fetchall()
            vd = dict(venta); vd.update(request.form)
            return render_template('ventas/form.html', clientes=clientes, form=vd, accion='Editar')

        db.execute('''
            UPDATE ventas
            SET cliente_id=?, producto=?, precio=?, tipo_pago=?, fecha=?, notas=?
            WHERE id=? AND negocio_id=?
        ''', (cliente_id, producto, precio, tipo_pago, fecha, notas, id, nid))
        db.commit()
        flash('Venta actualizada correctamente.', 'success')
        return redirect(url_for('index'))

    clientes = db.execute(
        'SELECT id, nombre, telefono FROM clientes WHERE negocio_id = ? ORDER BY nombre', (nid,)
    ).fetchall()
    return render_template('ventas/form.html', clientes=clientes,
                           form=dict(venta), accion='Editar', hoy=venta['fecha'])


@ventas_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar(id):
    nid = session['negocio_id']
    db  = get_db()
    venta = db.execute(
        'SELECT producto FROM ventas WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()
    if venta:
        db.execute('DELETE FROM ventas WHERE id = ? AND negocio_id = ?', (id, nid))
        db.commit()
        flash(f'Venta de "{venta["producto"]}" eliminada.', 'success')
    else:
        flash('Venta no encontrada.', 'danger')
    return redirect(url_for('ventas.lista'))


@ventas_bp.route('/accesorio', methods=['POST'])
@login_required
def venta_accesorio():
    """Venta de accesorio con opción de factura"""
    nid = session['negocio_id']
    db  = get_db()

    nombre_accesorio   = request.form.get('nombre_accesorio', '').strip().title()
    telefono_accesorio = request.form.get('telefono_accesorio', '').strip()
    producto_accesorio = request.form.get('producto_accesorio', '').strip()
    precio_accesorio   = request.form.get('precio_accesorio', '').strip()
    tipo_pago_accesorio = request.form.get('tipo_pago_accesorio', 'contado').strip()
    con_factura        = request.form.get('con_factura', 'no').strip()

    # Validaciones básicas
    if not nombre_accesorio:
        flash('El nombre del cliente es obligatorio.', 'danger')
        return redirect(url_for('ventas.lista'))
    
    if not telefono_accesorio:
        flash('El teléfono es obligatorio.', 'danger')
        return redirect(url_for('ventas.lista'))
    
    if not producto_accesorio:
        flash('El producto es obligatorio.', 'danger')
        return redirect(url_for('ventas.lista'))
    
    if not precio_accesorio:
        flash('El precio es obligatorio.', 'danger')
        return redirect(url_for('ventas.lista'))
    
    try:
        precio_num = float(precio_accesorio)
        if precio_num <= 0:
            flash('El precio debe ser mayor a 0.', 'danger')
            return redirect(url_for('ventas.lista'))
    except ValueError:
        flash('El precio debe ser un número válido.', 'danger')
        return redirect(url_for('ventas.lista'))

    # Buscar o crear cliente
    cliente = db.execute(
        'SELECT id FROM clientes WHERE negocio_id = ? AND telefono = ?',
        (nid, telefono_accesorio)
    ).fetchone()
    
    if cliente:
        cliente_id = cliente['id']
    else:
        db.execute(
            'INSERT INTO clientes (negocio_id, nombre, telefono) VALUES (?, ?, ?)',
            (nid, nombre_accesorio, telefono_accesorio)
        )
        db.commit()
        cliente_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Crear la venta
    fecha_hoy = date.today().isoformat()
    db.execute(
        'INSERT INTO ventas (negocio_id, cliente_id, producto, precio, tipo_pago, fecha) VALUES (?, ?, ?, ?, ?, ?)',
        (nid, cliente_id, producto_accesorio, precio_num, tipo_pago_accesorio, fecha_hoy)
    )
    db.commit()
    venta_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Si es sin factura, solo registra y redirige a lista
    if con_factura == 'no':
        flash(f'Venta de "{producto_accesorio}" registrada correctamente.', 'success')
        return redirect(url_for('ventas.lista'))
    
    # Si es con factura, genera PDF y envía por WhatsApp
    else:
        # Obtener datos completos para generar factura
        venta_obj = db.execute('''
            SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono,
                   c.cedula, c.direccion, c.ciudad
            FROM ventas v JOIN clientes c ON v.cliente_id = c.id
            WHERE v.id = ? AND v.negocio_id = ?
        ''', (venta_id, nid)).fetchone()
        
        # Generar PDF
        try:
            from routes.facturas import generar_pdf
            ruta_pdf, nombre_pdf = generar_pdf(venta_obj, venta_obj)
            flash(f'Venta registrada. PDF generado: {nombre_pdf}', 'success')
        except Exception as e:
            flash(f'Venta registrada. (PDF no generado)', 'success')

        # Abrir carpeta facturas_pdf en Windows
        carpeta = os.path.abspath('facturas_pdf')
        if platform.system() == 'Windows':
            subprocess.Popen(['explorer', carpeta])

        # Enviar por WhatsApp
        return redirect(url_for('whatsapp.enviar', venta_id=venta_id))


@ventas_bp.route('/rapida-casual', methods=['POST'])
@login_required
def venta_rapida_casual():
    """Flujo rápido para clientes casuales: solo nombre y teléfono"""
    nid = session['negocio_id']
    db  = get_db()

    nombre_casual   = request.form.get('nombre_casual', '').strip().title()
    telefono_casual = request.form.get('telefono_casual', '').strip()

    # Validaciones básicas
    if not nombre_casual:
        flash('El nombre del cliente es obligatorio.', 'danger')
        return redirect(url_for('ventas.lista'))
    
    if not telefono_casual:
        flash('El teléfono es obligatorio.', 'danger')
        return redirect(url_for('ventas.lista'))

    # Buscar o crear cliente
    cliente = db.execute(
        'SELECT id FROM clientes WHERE negocio_id = ? AND telefono = ?',
        (nid, telefono_casual)
    ).fetchone()
    
    if cliente:
        cliente_id = cliente['id']
    else:
        db.execute(
            'INSERT INTO clientes (negocio_id, nombre, telefono) VALUES (?, ?, ?)',
            (nid, nombre_casual, telefono_casual)
        )
        db.commit()
        cliente_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Crear una venta de ticket (sin producto, solo para registrar el contacto)
    fecha_hoy = date.today().isoformat()
    db.execute(
        'INSERT INTO ventas (negocio_id, cliente_id, producto, precio, tipo_pago, fecha) VALUES (?, ?, ?, ?, ?, ?)',
        (nid, cliente_id, 'TICKET', 0, 'ticket', fecha_hoy)
    )
    db.commit()
    venta_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Generar ticket y enviar por WhatsApp
    return redirect(url_for('ventas.enviar_ticket_whatsapp', venta_id=venta_id))


@ventas_bp.route('/<int:venta_id>/ticket-whatsapp')
@login_required
def enviar_ticket_whatsapp(venta_id):
    """Genera un ticket y lo envía por WhatsApp"""
    nid = session['negocio_id']
    db  = get_db()

    # Obtener datos de la venta y cliente
    venta = db.execute('''
        SELECT v.*, c.nombre, c.telefono
        FROM ventas v JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ? AND v.negocio_id = ?
    ''', (venta_id, nid)).fetchone()

    if not venta:
        flash('Venta no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))

    # Obtener datos del negocio
    negocio = db.execute(
        'SELECT * FROM negocios WHERE id = ?', (nid,)
    ).fetchone()

    # Limpiar y formatear teléfono
    from routes.whatsapp import limpiar_telefono
    numero = limpiar_telefono(venta['telefono'])
    
    if not numero:
        flash('El cliente no tiene un teléfono válido.', 'warning')
        return redirect(url_for('ventas.lista'))

    # Generar número de ticket único
    ticket_numero = f"{venta_id:06d}"
    nombre_negocio = negocio['nombre_negocio'] if negocio else 'Tecnocel'
    
    # Obtener fecha y hora actual
    from datetime import datetime
    fecha_hora = datetime.now().strftime('%d/%m/%Y %H:%M')

    # Construir mensaje de ticket para WhatsApp
    mensaje_ticket = (
        f"*🎫 TICKET DE CONTACTO*\n\n"
        f"Hola {venta['nombre'].title()},\n\n"
        f"Gracias por contactarnos en *{nombre_negocio}*\n\n"
        f"📋 *Número de Ticket:* #{ticket_numero}\n"
        f"📅 *Fecha y Hora:* {fecha_hora}\n"
        f"👤 *Nombre:* {venta['nombre'].title()}\n"
        f"📱 *Teléfono:* {venta['telefono']}\n\n"
        f"Nos pondremos en contacto pronto con más información.\n\n"
        f"Gracias por tu confianza! 🙏"
    )

    # Generar URL de WhatsApp
    url_wa = f"https://wa.me/{numero}?text={urllib.parse.quote(mensaje_ticket)}"
    
    # Registrar en la base de datos que se envió el ticket
    db.execute(
        'UPDATE ventas SET notas = ? WHERE id = ?',
        (f'Ticket enviado por WhatsApp el {fecha_hora}', venta_id)
    )
    db.commit()

    flash(f'Ticket #{ticket_numero} generado. Abriendo WhatsApp...', 'success')
    return redirect(url_wa)


@ventas_bp.route('/rapida', methods=['POST'])
@login_required
def venta_rapida():
    nid = session['negocio_id']
    db  = get_db()

    cliente_nombre   = request.form.get('cliente_nombre', '').strip().title()
    cliente_telefono = request.form.get('cliente_telefono', '').strip()
    producto         = request.form.get('producto', '').strip()
    precio           = request.form.get('precio', '').strip()
    tipo_pago        = request.form.get('tipo_pago', 'Efectivo').strip()
    fecha            = date.today().isoformat()

    # Si no hay nombre ni teléfono usar Cliente Exprés
    if not cliente_nombre and not cliente_telefono:
        cliente_telefono = '0000000000'
        cliente_nombre   = 'Cliente Exprés'

    # Buscar o crear cliente
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

    # Guardar venta
    try:
        precio_num = float(precio) if precio else 0
    except ValueError:
        precio_num = 0

    db.execute(
        'INSERT INTO ventas (negocio_id, cliente_id, producto, precio, tipo_pago, fecha) VALUES (?, ?, ?, ?, ?, ?)',
        (nid, cliente_id, producto, precio_num, tipo_pago, fecha)
    )
    db.commit()
    venta_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]

    # Generar PDF
    try:
        from routes.facturas import generar_pdf
        venta_obj = db.execute(
            'SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono, '
            'c.cedula, c.direccion, c.ciudad '
            'FROM ventas v JOIN clientes c ON v.cliente_id = c.id WHERE v.id = ?',
            (venta_id,)
        ).fetchone()
        if venta_obj:
            generar_pdf(venta_obj, venta_obj)
    except Exception:
        pass

    # Abrir carpeta en Windows
    import subprocess, platform, os
    carpeta = os.path.abspath('facturas_pdf')
    if platform.system() == 'Windows':
        subprocess.Popen(['explorer', carpeta])

    # WhatsApp
    import urllib.parse
    negocio = db.execute('SELECT * FROM negocios WHERE id = ?', (nid,)).fetchone()
    nombre_negocio = negocio['nombre_negocio'] if negocio else 'Tecnocel'
    precio_fmt = '$ ' + f'{int(precio_num):,}'.replace(',', '.')
    
    mensaje = (
        f"Hola {cliente_nombre}, gracias por tu compra en {nombre_negocio}. "
        f"Producto: {producto}. Total: {precio_fmt}. "
        f"Metodo de pago: {tipo_pago}. Que lo disfrutes!"
    )
    
    telefono_limpio = cliente_telefono.replace(' ', '').replace('-', '')
    if not telefono_limpio.startswith('57') and len(telefono_limpio) == 10:
        telefono_limpio = '57' + telefono_limpio
        
    url_wa = f"https://wa.me/{telefono_limpio}?text={urllib.parse.quote(mensaje)}"
    return redirect(url_wa)

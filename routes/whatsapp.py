import urllib.parse
from flask import Blueprint, redirect, url_for, flash, session
from database.db import get_db
from routes.auth import login_required

whatsapp_bp = Blueprint('whatsapp', __name__)

def limpiar_telefono(telefono):
    numero = ''.join(filter(str.isdigit, telefono or ''))
    if not numero: return None
    if numero.startswith('0'): numero = numero[1:]
    if len(numero) == 10: numero = '57' + numero
    return numero

@whatsapp_bp.route('/enviar/<int:venta_id>')
@login_required
def enviar(venta_id):
    nid = session['negocio_id']
    db = get_db()
    venta = db.execute('''
        SELECT v.*, c.nombre, c.cedula, c.telefono, c.direccion, c.ciudad
        FROM ventas v JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ? AND v.negocio_id = ?
    ''', (venta_id, nid)).fetchone()
    if not venta:
        flash('Venta no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))
    numero = limpiar_telefono(venta['telefono'])
    if not numero:
        flash('El cliente no tiene numero de telefono.', 'warning')
        return redirect(url_for('facturas.generar', venta_id=venta_id))
    negocio_nombre = session.get('negocio_nombre', 'Tecnocel')
    mensaje = (
        f"Hola {venta['nombre']}, 👋\n\n"
        f"Le enviamos el comprobante de su compra en *{negocio_nombre}*:\n\n"
        f"📱 *Producto:* {venta['producto']}\n"
        f"💰 *Total pagado:* $ {venta['precio']:,.0f}\n"
        f"📅 *Fecha:* {venta['fecha']}\n"
        f"💳 *Forma de pago:* {venta['tipo_pago'].upper()}\n\n"
        f"Factura #{venta_id:04d}\n\n"
        f"Gracias por su compra! 🙏"
    )
    url_wa = f"https://wa.me/{numero}?text={urllib.parse.quote(mensaje)}"
    return redirect(url_wa)

@whatsapp_bp.route('/abrir/<int:venta_id>')
@login_required
def abrir_chat(venta_id):
    nid = session['negocio_id']
    db = get_db()
    venta = db.execute('''
        SELECT v.id, c.nombre, c.telefono FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ? AND v.negocio_id = ?
    ''', (venta_id, nid)).fetchone()
    if not venta:
        flash('Venta no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))
    numero = limpiar_telefono(venta['telefono'])
    if numero:
        return redirect(f"https://wa.me/{numero}")
    flash('El cliente no tiene telefono.', 'warning')
    return redirect(url_for('facturas.generar', venta_id=venta_id))

import os
import webbrowser
import urllib.parse
from flask import Blueprint, request, redirect, url_for, flash, jsonify, session
from database.db import get_db
from routes.auth import login_required
from routes.facturas import generar_pdf

whatsapp_bp = Blueprint('whatsapp', __name__)


def limpiar_telefono(telefono):
    numero = ''.join(filter(str.isdigit, telefono or ''))
    if not numero: return None
    if numero.startswith('0'): numero = numero[1:]
    if len(numero) == 10: numero = '57' + numero
    return numero


@whatsapp_bp.route('/enviar/<int:venta_id>', methods=['POST'])
@login_required
def enviar(venta_id):
    nid = session['negocio_id']
    db  = get_db()
    venta = db.execute('''
        SELECT v.*, c.nombre, c.cedula, c.telefono, c.direccion, c.ciudad
        FROM ventas v JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ? AND v.negocio_id = ?
    ''', (venta_id, nid)).fetchone()
    db.close()

    if not venta:
        flash('Venta no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))

    numero = limpiar_telefono(venta['telefono'])
    if not numero:
        flash('El cliente no tiene número de teléfono.', 'warning')
        return redirect(url_for('facturas.generar', venta_id=venta_id))

    try:
        ruta_pdf, nombre_archivo = generar_pdf(venta, venta)
    except Exception as e:
        flash(f'Error al generar el PDF: {str(e)}', 'danger')
        return redirect(url_for('facturas.generar', venta_id=venta_id))

    negocio_nombre = session.get('negocio_nombre', 'Tecnocel')
    mensaje = (
        f"Hola {venta['nombre']}, 👋\n\n"
        f"Le enviamos el comprobante de su compra en *{negocio_nombre}*:\n\n"
        f"📱 *Producto:* {venta['producto']}\n"
        f"💰 *Total pagado:* $ {venta['precio']:,.0f}\n"
        f"📅 *Fecha:* {venta['fecha']}\n"
        f"💳 *Forma de pago:* {venta['tipo_pago'].upper()}\n\n"
        f"Adjuntamos su factura en PDF (#{venta_id:04d}).\n\n"
        f"¡Gracias por su compra! 🙏"
    )

    url_wa = f"https://wa.me/{numero}?text={urllib.parse.quote(mensaje)}"
    webbrowser.open(url_wa)
    flash(f'WhatsApp abierto para {venta["nombre"]}. Adjunte el PDF desde: facturas_pdf/{nombre_archivo}', 'success')
    return redirect(url_for('facturas.generar', venta_id=venta_id))


@whatsapp_bp.route('/abrir/<int:venta_id>')
@login_required
def abrir_chat(venta_id):
    nid = session['negocio_id']
    db  = get_db()
    venta = db.execute('''
        SELECT v.id, c.nombre, c.telefono FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ? AND v.negocio_id = ?
    ''', (venta_id, nid)).fetchone()
    db.close()

    if not venta:
        return jsonify({'error': 'Venta no encontrada'}), 404

    numero = limpiar_telefono(venta['telefono'])
    if numero:
        webbrowser.open(f"https://wa.me/{numero}")
        flash(f'Chat de WhatsApp abierto para {venta["nombre"]}.', 'info')
    else:
        flash('El cliente no tiene teléfono registrado.', 'warning')

    return redirect(url_for('facturas.generar', venta_id=venta_id))

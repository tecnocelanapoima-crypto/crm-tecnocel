"""
Rutas para envío de facturas por WhatsApp
Abre WhatsApp Web con el número del cliente para facilitar el envío
"""

import os
import webbrowser
import urllib.parse
from flask import Blueprint, request, redirect, url_for, flash, jsonify
from database.db import get_db
from routes.facturas import generar_pdf

whatsapp_bp = Blueprint('whatsapp', __name__)


def limpiar_telefono(telefono):
    """
    Limpia y formatea el número de teléfono para WhatsApp.
    Agrega el código de país de Colombia (+57) si no tiene prefijo.
    """
    # Eliminar espacios, guiones y paréntesis
    numero = ''.join(filter(str.isdigit, telefono or ''))

    if not numero:
        return None

    # Si empieza por 0, quitar el 0
    if numero.startswith('0'):
        numero = numero[1:]

    # Si no tiene código de país (menos de 11 dígitos), agregar +57 (Colombia)
    if len(numero) == 10:
        numero = '57' + numero

    return numero


@whatsapp_bp.route('/enviar/<int:venta_id>', methods=['POST'])
def enviar(venta_id):
    """
    Genera la factura PDF y abre WhatsApp Web con un mensaje prearmado.
    El usuario deberá adjuntar manualmente el PDF desde su computador.
    """
    db = get_db()
    venta = db.execute('''
        SELECT v.*, c.nombre, c.cedula, c.telefono, c.direccion, c.ciudad
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ?
    ''', (venta_id,)).fetchone()
    db.close()

    if not venta:
        flash('Venta no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))

    telefono = venta['telefono']
    numero = limpiar_telefono(telefono)

    if not numero:
        flash('El cliente no tiene un número de teléfono registrado.', 'warning')
        return redirect(url_for('facturas.generar', venta_id=venta_id))

    # Generar el PDF primero
    try:
        ruta_pdf, nombre_archivo = generar_pdf(venta, venta)
    except Exception as e:
        flash(f'Error al generar el PDF: {str(e)}', 'danger')
        return redirect(url_for('facturas.generar', venta_id=venta_id))

    # Construir el mensaje de WhatsApp
    mensaje = (
        f"Hola {venta['nombre']}, 👋\n\n"
        f"Le enviamos el comprobante de su compra en *Tecnocel*:\n\n"
        f"📱 *Producto:* {venta['producto']}\n"
        f"💰 *Total pagado:* $ {venta['precio']:,.0f}\n"
        f"📅 *Fecha:* {venta['fecha']}\n"
        f"💳 *Forma de pago:* {venta['tipo_pago'].upper()}\n\n"
        f"Adjuntamos su factura en PDF (#{venta_id:04d}).\n\n"
        f"¡Gracias por comprar en Tecnocel! 🙏"
    )

    # Codificar el mensaje para la URL
    mensaje_codificado = urllib.parse.quote(mensaje)
    url_whatsapp = f"https://wa.me/{numero}?text={mensaje_codificado}"

    # Abrir WhatsApp Web en el navegador predeterminado
    webbrowser.open(url_whatsapp)

    # Ruta del PDF para mostrarla al usuario
    ruta_relativa = os.path.join('facturas_pdf', nombre_archivo)

    flash(
        f'WhatsApp Web abierto para {venta["nombre"]}. '
        f'Adjunte el PDF manualmente desde: {ruta_relativa}',
        'success'
    )

    return redirect(url_for('facturas.generar', venta_id=venta_id))


@whatsapp_bp.route('/abrir/<int:venta_id>')
def abrir_chat(venta_id):
    """Solo abre el chat de WhatsApp sin enviar mensaje (útil para seguimiento)"""
    db = get_db()
    venta = db.execute('''
        SELECT v.id, c.nombre, c.telefono
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ?
    ''', (venta_id,)).fetchone()
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

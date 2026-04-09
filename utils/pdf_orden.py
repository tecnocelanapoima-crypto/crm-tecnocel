"""
Generador de PDF personalizable para órdenes de servicio.

Uso:
    from utils.pdf_orden import generar_pdf_orden
    buffer = generar_pdf_orden(orden, cliente, config)
    # buffer es un io.BytesIO listo para send_file o guardar en disco

Parámetros:
    orden   — sqlite3.Row de la tabla ordenes
    cliente — sqlite3.Row de la tabla clientes
    config  — dict con claves:
                nombre, telefono, direccion, logo_base64,
                plantilla ('moderno' | 'clasico' | 'minimalista'),
                color_principal (hex, ej. '#00bcd4'),
                mensaje_pie
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from datetime import datetime
import io
import base64


def _dibujar_logo(c, config, x, y):
    logo_data = config.get('logo_base64', '') or ''
    if not logo_data:
        return
    try:
        if ',' in logo_data:
            logo_data = logo_data.split(',', 1)[1]
        img_bytes = base64.b64decode(logo_data)
        img = ImageReader(io.BytesIO(img_bytes))
        c.drawImage(img, x, y, width=3 * cm, height=3 * cm,
                    preserveAspectRatio=True, anchor='c', mask='auto')
    except Exception:
        pass


def generar_pdf_orden(orden, cliente, config):
    """Genera un PDF de orden de servicio y devuelve un BytesIO."""
    buffer = io.BytesIO()
    ancho, alto = letter
    c = canvas.Canvas(buffer, pagesize=letter)

    plantilla       = config.get('plantilla', 'moderno')
    color_hex       = config.get('color_principal', '#00bcd4')
    ACENTO          = colors.HexColor(color_hex)
    NEGRO           = colors.HexColor('#1a1a1a')
    BORDE           = colors.HexColor('#dddddd')
    margen          = 2 * cm
    numero_orden    = orden['numero_orden']

    # ── PLANTILLA MODERNA ─────────────────────────────────────────────────
    if plantilla == 'moderno':
        c.setFillColor(NEGRO)
        c.rect(0, alto - 4.5 * cm, ancho, 4.5 * cm, fill=1, stroke=0)
        _dibujar_logo(c, config, margen, alto - 4 * cm)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 18)
        c.drawString(6 * cm, alto - 2.2 * cm, config.get('nombre', 'Tecnocel'))
        c.setFont('Helvetica', 9)
        c.setFillColor(ACENTO)
        c.drawString(6 * cm, alto - 3.2 * cm,
                     f"{config.get('telefono', '')}  |  {config.get('direccion', '')}")
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 12)
        c.drawRightString(ancho - margen, alto - 2 * cm, numero_orden)
        c.setFont('Helvetica', 9)
        c.setFillColor(ACENTO)
        c.drawRightString(ancho - margen, alto - 2.8 * cm,
                          f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        y = alto - 5.5 * cm

        def titulo_seccion(texto, y_pos):
            c.setFillColor(ACENTO)
            c.rect(margen, y_pos - 0.5 * cm,
                   ancho - 2 * margen, 0.6 * cm, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont('Helvetica-Bold', 10)
            c.drawString(margen + 0.3 * cm, y_pos - 0.32 * cm, texto.upper())
            return y_pos - 1.2 * cm

    # ── PLANTILLA CLÁSICA ─────────────────────────────────────────────────
    elif plantilla == 'clasico':
        c.setStrokeColor(ACENTO)
        c.setLineWidth(3)
        c.line(0, alto - 0.3 * cm, ancho, alto - 0.3 * cm)
        c.setLineWidth(1)
        _dibujar_logo(c, config, margen, alto - 4 * cm)
        c.setFillColor(NEGRO)
        c.setFont('Helvetica-Bold', 20)
        c.drawString(6 * cm, alto - 2 * cm, config.get('nombre', 'Tecnocel'))
        c.setFont('Helvetica', 9)
        c.setFillColor(colors.grey)
        c.drawString(6 * cm, alto - 2.8 * cm,
                     f"{config.get('telefono', '')}  |  {config.get('direccion', '')}")
        c.setFillColor(NEGRO)
        c.setFont('Helvetica-Bold', 11)
        c.drawRightString(ancho - margen, alto - 2 * cm, numero_orden)
        c.setFont('Helvetica', 9)
        c.setFillColor(colors.grey)
        c.drawRightString(ancho - margen, alto - 2.8 * cm,
                          f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        c.setStrokeColor(ACENTO)
        c.setLineWidth(2)
        c.line(margen, alto - 4.5 * cm, ancho - margen, alto - 4.5 * cm)
        c.setLineWidth(1)
        y = alto - 5.5 * cm

        def titulo_seccion(texto, y_pos):
            c.setFillColor(NEGRO)
            c.setFont('Helvetica-Bold', 10)
            c.drawString(margen, y_pos, texto.upper())
            c.setStrokeColor(ACENTO)
            c.line(margen, y_pos - 0.2 * cm, ancho - margen, y_pos - 0.2 * cm)
            return y_pos - 0.9 * cm

    # ── PLANTILLA MINIMALISTA ─────────────────────────────────────────────
    else:
        _dibujar_logo(c, config, margen, alto - 3.5 * cm)
        c.setFillColor(NEGRO)
        c.setFont('Helvetica-Bold', 16)
        c.drawString(6 * cm, alto - 1.8 * cm, config.get('nombre', 'Tecnocel'))
        c.setFont('Helvetica', 8)
        c.setFillColor(colors.grey)
        c.drawString(6 * cm, alto - 2.5 * cm,
                     f"{config.get('telefono', '')}  |  {config.get('direccion', '')}")
        c.setFillColor(NEGRO)
        c.setFont('Helvetica', 10)
        c.drawRightString(ancho - margen, alto - 1.8 * cm, numero_orden)
        c.setFont('Helvetica', 8)
        c.setFillColor(colors.grey)
        c.drawRightString(ancho - margen, alto - 2.5 * cm,
                          datetime.now().strftime('%d/%m/%Y'))
        c.setStrokeColor(NEGRO)
        c.setLineWidth(0.5)
        c.line(margen, alto - 3.5 * cm, ancho - margen, alto - 3.5 * cm)
        y = alto - 4.5 * cm

        def titulo_seccion(texto, y_pos):
            c.setFillColor(NEGRO)
            c.setFont('Helvetica-Bold', 9)
            c.drawString(margen, y_pos, texto.upper())
            c.setStrokeColor(BORDE)
            c.line(margen, y_pos - 0.15 * cm, ancho - margen, y_pos - 0.15 * cm)
            return y_pos - 0.8 * cm

    # ── HELPER CAMPO ──────────────────────────────────────────────────────
    def campo(etiqueta, valor, x, y_pos):
        c.setFillColor(NEGRO)
        c.setFont('Helvetica-Bold', 9)
        c.drawString(x, y_pos, f"{etiqueta}:")
        c.setFont('Helvetica', 9)
        c.drawString(x + 3.5 * cm, y_pos, str(valor or '—'))

    # ── SECCIÓN: CLIENTE ──────────────────────────────────────────────────
    y = titulo_seccion('Datos del cliente', y)
    campo('Nombre',   cliente['nombre'],            margen,           y)
    campo('Teléfono', cliente['telefono'] or '—',   ancho / 2 + cm,   y)
    y -= 0.7 * cm
    campo('Cédula',   cliente['cedula']  or '—',    margen,           y)
    campo('Ciudad',   cliente['ciudad']  or '—',    ancho / 2 + cm,   y)
    y -= 0.9 * cm

    # ── SECCIÓN: EQUIPO ───────────────────────────────────────────────────
    y = titulo_seccion('Datos del equipo', y)
    campo('Marca/Modelo', orden['marca_modelo'],         margen,         y)
    campo('Estado',       orden['estado'].upper(),       ancho / 2 + cm, y)
    y -= 0.7 * cm
    campo('Problema',     orden['problema'],             margen,         y)
    y -= 0.7 * cm
    campo('Fecha recibido', orden['fecha_recibido'],     margen,         y)
    if orden['fecha_listo']:
        campo('Fecha listo', orden['fecha_listo'],       ancho / 2 + cm, y)
    y -= 0.9 * cm

    # ── SECCIÓN: COSTOS ───────────────────────────────────────────────────
    y = titulo_seccion('Información de costos', y)
    costo_est  = int(orden['costo_estimado']  or 0)
    abono_val  = int(orden['abono']           or 0)
    saldo_val  = int(orden['saldo_pendiente'] or 0)
    costo_fin  = int(orden['costo_final']     or costo_est)
    tipo_pago  = orden['tipo_pago_abono'] or 'Efectivo'

    campo('Costo estimado',  f"$ {costo_est:,}".replace(',', '.'),  margen,         y)
    campo('Abono recibido',
          f"$ {abono_val:,}  ({tipo_pago})".replace(',', '.'),      ancho / 2 + cm, y)
    y -= 0.7 * cm
    campo('Saldo pendiente', f"$ {saldo_val:,}".replace(',', '.'),  margen,         y)
    if orden['costo_final']:
        campo('Costo final', f"$ {costo_fin:,}".replace(',', '.'),  ancho / 2 + cm, y)
    y -= 0.9 * cm

    # ── SECCIÓN: NOTAS DEL TÉCNICO ────────────────────────────────────────
    if orden['notas_tecnico']:
        y = titulo_seccion('Notas del técnico', y)
        c.setFillColor(NEGRO)
        c.setFont('Helvetica', 9)
        notas     = str(orden['notas_tecnico'])
        max_chars = 90
        while notas:
            linea = notas[:max_chars]
            if len(notas) > max_chars:
                corte = linea.rfind(' ')
                if corte > 0:
                    linea = notas[:corte]
                    notas = notas[corte + 1:]
                else:
                    notas = notas[max_chars:]
            else:
                notas = ''
            c.drawString(margen, y, linea)
            y -= 0.5 * cm
        y -= 0.4 * cm

    # ── PIE DE PÁGINA ─────────────────────────────────────────────────────
    msg_pie = config.get('mensaje_pie',
              'Gracias por confiar en nosotros. '
              'No nos hacemos responsables por daños previos no reportados.')
    c.setStrokeColor(BORDE)
    c.setLineWidth(0.5)
    c.line(margen, 2.5 * cm, ancho - margen, 2.5 * cm)
    c.setFillColor(colors.grey)
    c.setFont('Helvetica', 7.5)
    ancho_texto = c.stringWidth(msg_pie, 'Helvetica', 7.5)
    x_msg = max(margen, (ancho - ancho_texto) / 2)
    c.drawString(x_msg, 2 * cm, msg_pie)

    c.save()
    buffer.seek(0)
    return buffer

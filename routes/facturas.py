"""
Rutas para generación de facturas PDF
Diseño oscuro con paleta neón Tecnocel:
  Negro #000000 / #050D1A — Cyan #00CFFF — Azul #0088CC
"""

import os
from flask import Blueprint, send_file, flash, redirect, url_for, render_template
from database.db import get_db
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, HRFlowable, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

facturas_bp = Blueprint('facturas', __name__)

# ── Rutas ────────────────────────────────────────────
LOGO_PATH    = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'img', 'logo.png')
FACTURAS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'facturas_pdf')

# ── Paleta de colores Tecnocel (neón oscuro) ─────────
C_BLACK   = colors.HexColor('#000000')
C_DARK    = colors.HexColor('#050D1A')
C_DARK2   = colors.HexColor('#0A1628')
C_DARK3   = colors.HexColor('#0D1E35')
C_CYAN    = colors.HexColor('#00CFFF')
C_CYAN_DIM= colors.HexColor('#0088AA')
C_BLUE    = colors.HexColor('#0066BB')
C_WHITE   = colors.white
C_LGRAY   = colors.HexColor('#A0C4D8')   # texto secundario sobre oscuro
C_MGRAY   = colors.HexColor('#4A6A80')   # bordes sutiles


def fondo_oscuro(canvas, doc):
    """Pinta el fondo de cada página en negro profundo."""
    canvas.saveState()
    canvas.setFillColor(C_DARK)
    canvas.rect(0, 0, A4[0], A4[1], fill=True, stroke=False)
    canvas.restoreState()


def asegurar_carpeta_facturas():
    if not os.path.exists(FACTURAS_DIR):
        os.makedirs(FACTURAS_DIR)


def generar_pdf(venta, cliente):
    """
    Genera la factura PDF con diseño oscuro Tecnocel.
    Retorna (ruta_absoluta, nombre_archivo).
    """
    asegurar_carpeta_facturas()

    nombre_archivo = f'factura_{venta["id"]:04d}.pdf'
    ruta_pdf       = os.path.join(FACTURAS_DIR, nombre_archivo)

    # ── Documento ────────────────────────────────────
    doc = SimpleDocTemplate(
        ruta_pdf,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    W = A4[0] - 3.6 * cm   # ancho útil

    # ── Estilos de texto ─────────────────────────────
    estilos = getSampleStyleSheet()

    def estilo(nombre, **kw):
        base = kw.pop('base', 'Normal')
        p = ParagraphStyle(nombre, parent=estilos[base], **kw)
        return p

    st_sub   = estilo('sub',    fontSize=9,  textColor=C_LGRAY, alignment=TA_CENTER, spaceAfter=1)
    st_label = estilo('lbl',    fontSize=9,  textColor=C_LGRAY, fontName='Helvetica-Bold')
    st_val   = estilo('val',    fontSize=10, textColor=C_WHITE)
    st_sec   = estilo('sec',    fontSize=9,  textColor=C_CYAN,  fontName='Helvetica-Bold', spaceAfter=0)
    st_foot  = estilo('foot',   fontSize=8,  textColor=C_LGRAY, alignment=TA_CENTER, spaceAfter=2)
    st_total = estilo('tot',    fontSize=13, textColor=C_CYAN,  fontName='Helvetica-Bold', alignment=TA_RIGHT)
    st_cyan  = estilo('cyan',   fontSize=10, textColor=C_CYAN,  fontName='Helvetica-Bold')

    contenido = []

    # ══════════════════════════════════════════════════
    # BLOQUE 1 — ENCABEZADO: logo + nombre del negocio
    # ══════════════════════════════════════════════════
    if os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=8.5 * cm, height=2.2 * cm)
        logo_cell = logo
    else:
        logo_cell = Paragraph('<b><font color="#00CFFF" size="22">TECNOCEL</font></b>', estilos['Title'])

    sub1 = Paragraph('Venta y soporte de celulares', st_sub)
    sub2 = Paragraph('tecnocel.negocio@gmail.com', st_sub)

    header_data = [[logo_cell], [sub1], [sub2]]
    header_table = Table(header_data, colWidths=[W])
    header_table.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, -1), C_BLACK),
        ('ALIGN',       (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',  (0, 0), (-1,  0), 14),
        ('BOTTOMPADDING',(0,-1),(-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',(0, 0), (-1, -1), 8),
        ('LINEBELOW',   (0, -1), (-1, -1), 2, C_CYAN),
    ]))
    contenido.append(header_table)
    contenido.append(Spacer(1, 0.4 * cm))

    # ══════════════════════════════════════════════════
    # BLOQUE 2 — NÚMERO DE FACTURA + FECHA + TIPO PAGO
    # ══════════════════════════════════════════════════
    n_factura = Paragraph(f'<font color="#00CFFF"><b>FACTURA #{venta["id"]:04d}</b></font>',
                          estilo('nf', fontSize=16, textColor=C_CYAN, fontName='Helvetica-Bold'))
    fecha_lbl = Paragraph('Fecha', st_label)
    fecha_val = Paragraph(venta["fecha"], st_val)
    pago_lbl  = Paragraph('Tipo de pago', st_label)
    pago_val  = Paragraph(venta["tipo_pago"].upper(),
                          estilo('pv', fontSize=10, textColor=C_CYAN, fontName='Helvetica-Bold'))

    meta_data = [
        [n_factura,   '',    fecha_lbl,  pago_lbl],
        ['',          '',    fecha_val,  pago_val],
    ]
    meta_col = [W * 0.38, W * 0.08, W * 0.27, W * 0.27]
    meta_table = Table(meta_data, colWidths=meta_col, rowHeights=[None, None])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), C_DARK2),
        ('SPAN',         (0, 0), (1, 1)),
        ('ALIGN',        (0, 0), (1, 1), 'LEFT'),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE',     (0, 0), (-1, -1), 10),
        ('TOPPADDING',   (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 8),
        ('LEFTPADDING',  (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('LINEBEFORE',   (2, 0), (2, -1), 1, C_MGRAY),
        ('LINEBEFORE',   (3, 0), (3, -1), 1, C_MGRAY),
        ('BOX',          (0, 0), (-1, -1), 1, C_CYAN_DIM),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
    ]))
    contenido.append(meta_table)
    contenido.append(Spacer(1, 0.5 * cm))

    # ══════════════════════════════════════════════════
    # BLOQUE 3 — DATOS DEL CLIENTE
    # ══════════════════════════════════════════════════
    # Encabezado de sección
    sec_cliente = Table(
        [[Paragraph('  ▌  DATOS DEL CLIENTE', st_sec)]],
        colWidths=[W]
    )
    sec_cliente.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), C_DARK3),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
        ('LEFTPADDING',  (0, 0), (-1, -1), 8),
        ('LINEBEFORE',   (0, 0), (0, -1), 3, C_CYAN),
        ('LINEBELOW',    (0, -1), (-1, -1), 0.5, C_MGRAY),
    ]))
    contenido.append(sec_cliente)
    contenido.append(Spacer(1, 0.15 * cm))

    # Datos del cliente en dos columnas
    def fila_cliente(label, valor):
        return [Paragraph(label, st_label), Paragraph(valor or '—', st_val)]

    filas_cliente = [
        fila_cliente('Nombre completo', cliente["nombre"]),
        fila_cliente('N° Cédula',       cliente["cedula"]),
        fila_cliente('Teléfono',         cliente["telefono"]),
        fila_cliente('Dirección',        cliente["direccion"]),
        fila_cliente('Ciudad',           cliente["ciudad"]),
    ]
    tabla_cliente = Table(filas_cliente, colWidths=[W * 0.28, W * 0.72])
    tabla_cliente.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), C_DARK2),
        ('ROWBACKGROUNDS',(0,0),(-1,-1), [C_DARK2, C_DARK3]),
        ('TOPPADDING',   (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 7),
        ('LEFTPADDING',  (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX',          (0, 0), (-1, -1), 1, C_CYAN_DIM),
        ('LINEBELOW',    (0, 0), (-1, -2), 0.3, C_MGRAY),
    ]))
    contenido.append(tabla_cliente)
    contenido.append(Spacer(1, 0.5 * cm))

    # ══════════════════════════════════════════════════
    # BLOQUE 4 — DETALLE DEL PRODUCTO
    # ══════════════════════════════════════════════════
    sec_prod = Table(
        [[Paragraph('  ▌  DETALLE DE LA COMPRA', st_sec)]],
        colWidths=[W]
    )
    sec_prod.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), C_DARK3),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
        ('LEFTPADDING',  (0, 0), (-1, -1), 8),
        ('LINEBEFORE',   (0, 0), (0, -1), 3, C_CYAN),
        ('LINEBELOW',    (0, -1), (-1, -1), 0.5, C_MGRAY),
    ]))
    contenido.append(sec_prod)
    contenido.append(Spacer(1, 0.15 * cm))

    # Tabla de producto
    th = estilo('th', fontSize=9, textColor=C_CYAN, fontName='Helvetica-Bold')
    td = estilo('td', fontSize=10, textColor=C_WHITE)
    td_r = estilo('tdr', fontSize=10, textColor=C_WHITE, alignment=TA_RIGHT)
    tc = estilo('tdc', fontSize=10, textColor=C_WHITE)

    col_w = [W * 0.45, W * 0.13, W * 0.21, W * 0.21]
    filas_prod = [
        [Paragraph('Descripción', th),
         Paragraph('Cant.', estilo('thc', fontSize=9, textColor=C_CYAN, fontName='Helvetica-Bold', alignment=TA_CENTER)),
         Paragraph('Precio Unit.', estilo('thr', fontSize=9, textColor=C_CYAN, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
         Paragraph('Total', estilo('thr2', fontSize=9, textColor=C_CYAN, fontName='Helvetica-Bold', alignment=TA_RIGHT))],
        [Paragraph(venta["producto"], td),
         Paragraph('1', estilo('tc2', fontSize=10, textColor=C_WHITE, alignment=TA_CENTER)),
         Paragraph(f'$ {venta["precio"]:,.0f}', td_r),
         Paragraph(f'$ {venta["precio"]:,.0f}', td_r)],
    ]
    if venta["notas"]:
        nota_st = estilo('nota', fontSize=9, textColor=C_LGRAY)
        filas_prod.append([
            Paragraph(f'Nota: {venta["notas"]}', nota_st),
            '', '', ''
        ])

    tabla_prod = Table(filas_prod, colWidths=col_w)
    tabla_prod.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND',   (0, 0), (-1, 0), C_BLACK),
        ('LINEBELOW',    (0, 0), (-1, 0), 1.5, C_CYAN),
        # Cuerpo
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [C_DARK2, C_DARK3]),
        ('ALIGN',        (1, 0), (1, -1), 'CENTER'),
        ('ALIGN',        (2, 0), (-1, -1), 'RIGHT'),
        ('ALIGN',        (0, 0), (0, -1), 'LEFT'),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',   (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 9),
        ('LEFTPADDING',  (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('BOX',          (0, 0), (-1, -1), 1, C_CYAN_DIM),
        ('LINEBELOW',    (0, 1), (-1, -2), 0.3, C_MGRAY),
    ]))
    contenido.append(tabla_prod)
    contenido.append(Spacer(1, 0.4 * cm))

    # ══════════════════════════════════════════════════
    # BLOQUE 5 — TOTALES
    # ══════════════════════════════════════════════════
    sub_lbl = estilo('slbl', fontSize=9,  textColor=C_LGRAY, fontName='Helvetica-Bold', alignment=TA_RIGHT)
    sub_val = estilo('sval', fontSize=9,  textColor=C_WHITE, alignment=TA_RIGHT)
    tot_lbl = estilo('tlbl', fontSize=12, textColor=C_CYAN,  fontName='Helvetica-Bold', alignment=TA_RIGHT)
    tot_val = estilo('tval', fontSize=12, textColor=C_CYAN,  fontName='Helvetica-Bold', alignment=TA_RIGHT)

    filas_total = [
        ['', Paragraph('Subtotal:',     sub_lbl), Paragraph(f'$ {venta["precio"]:,.0f}', sub_val)],
        ['', Paragraph('Descuento:',    sub_lbl), Paragraph('$ 0',                        sub_val)],
        ['', Paragraph('TOTAL A PAGAR:', tot_lbl), Paragraph(f'$ {venta["precio"]:,.0f}', tot_val)],
    ]
    tabla_total = Table(filas_total, colWidths=[W * 0.45, W * 0.3, W * 0.25])
    tabla_total.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1,  1), C_DARK2),
        ('BACKGROUND',    (0, 2), (-1,  2), C_BLACK),
        ('LINEABOVE',     (1, 2), (-1,  2), 1.5, C_CYAN),
        ('LINEBELOW',     (1, 2), (-1,  2), 1.5, C_CYAN),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX',           (1, 0), (-1, -1), 1, C_CYAN_DIM),
    ]))
    contenido.append(tabla_total)
    contenido.append(Spacer(1, 0.8 * cm))

    # ══════════════════════════════════════════════════
    # BLOQUE 6 — PIE DE PÁGINA
    # ══════════════════════════════════════════════════
    contenido.append(HRFlowable(width='100%', thickness=1.5, color=C_CYAN))
    contenido.append(Spacer(1, 0.25 * cm))

    pie_data = [[
        Paragraph('¡Gracias por comprar en <font color="#00CFFF"><b>Tecnocel</b></font>!'
                  ' — Su satisfacción es nuestra prioridad.', st_foot),
    ], [
        Paragraph('Este comprobante es válido para reclamaciones. Consérvelo.',
                  estilo('fp2', fontSize=8, textColor=C_MGRAY, alignment=TA_CENTER)),
    ]]
    pie_table = Table(pie_data, colWidths=[W])
    pie_table.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), C_BLACK),
        ('TOPPADDING',   (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 6),
        ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
    ]))
    contenido.append(pie_table)

    # ── Build con fondo oscuro en cada página ─────────
    doc.build(contenido, onFirstPage=fondo_oscuro, onLaterPages=fondo_oscuro)
    return ruta_pdf, nombre_archivo


# ── Rutas Flask ───────────────────────────────────────

@facturas_bp.route('/<int:venta_id>')
def generar(venta_id):
    """Vista previa de la factura antes de descargar"""
    db = get_db()
    venta = db.execute('''
        SELECT v.*, c.nombre, c.cedula, c.telefono, c.direccion, c.ciudad
        FROM ventas v JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ?
    ''', (venta_id,)).fetchone()
    db.close()

    if not venta:
        flash('Venta no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))

    return render_template('facturas/previa.html', venta=venta)


@facturas_bp.route('/<int:venta_id>/descargar')
def descargar(venta_id):
    """Genera y descarga la factura en PDF"""
    db = get_db()
    venta = db.execute('''
        SELECT v.*, c.nombre, c.cedula, c.telefono, c.direccion, c.ciudad
        FROM ventas v JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ?
    ''', (venta_id,)).fetchone()
    db.close()

    if not venta:
        flash('Venta no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))

    try:
        ruta_pdf, nombre_archivo = generar_pdf(venta, venta)
        return send_file(
            ruta_pdf,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'Error al generar la factura: {str(e)}', 'danger')
        return redirect(url_for('ventas.lista'))

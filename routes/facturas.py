"""
Facturas — igual que antes pero con verificación negocio_id
"""

import os
from flask import Blueprint, send_file, flash, redirect, url_for, render_template, session
from database.db import get_db
from routes.auth import login_required
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

LOGO_PATH    = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'img', 'logo.png')
FACTURAS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'facturas_pdf')

C_BLACK   = colors.HexColor('#000000')
C_DARK    = colors.HexColor('#050D1A')
C_DARK2   = colors.HexColor('#0A1628')
C_DARK3   = colors.HexColor('#0D1E35')
C_CYAN    = colors.HexColor('#00CFFF')
C_CYAN_DIM= colors.HexColor('#0088AA')
C_BLUE    = colors.HexColor('#0066BB')
C_WHITE   = colors.white
C_LGRAY   = colors.HexColor('#A0C4D8')
C_MGRAY   = colors.HexColor('#4A6A80')


def fondo_oscuro(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(C_DARK)
    canvas.rect(0, 0, A4[0], A4[1], fill=True, stroke=False)
    canvas.restoreState()


def asegurar_carpeta_facturas():
    if not os.path.exists(FACTURAS_DIR):
        os.makedirs(FACTURAS_DIR)


def generar_pdf(venta, cliente):
    """Genera la factura PDF — sin cambios respecto a la versión original."""
    asegurar_carpeta_facturas()
    producto_slug = venta["producto"].strip().lower()
    producto_slug = ''.join(c if c.isalnum() or c in (' ', '-') else '' for c in producto_slug)
    producto_slug = producto_slug.replace(' ', '_')[:30]
    nombre_archivo = f'factura_{venta["id"]:04d}_{producto_slug}.pdf'
    ruta_pdf       = os.path.join(FACTURAS_DIR, nombre_archivo)

    doc = SimpleDocTemplate(ruta_pdf, pagesize=A4,
                            rightMargin=1.8*cm, leftMargin=1.8*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    W = A4[0] - 3.6*cm
    estilos = getSampleStyleSheet()

    def estilo(nombre, **kw):
        base = kw.pop('base', 'Normal')
        return ParagraphStyle(nombre, parent=estilos[base], **kw)

    st_sub  = estilo('sub',  fontSize=9,  textColor=C_LGRAY, alignment=TA_CENTER, spaceAfter=1)
    st_label= estilo('lbl',  fontSize=9,  textColor=C_LGRAY, fontName='Helvetica-Bold')
    st_val  = estilo('val',  fontSize=10, textColor=C_WHITE)
    st_sec  = estilo('sec',  fontSize=9,  textColor=C_CYAN,  fontName='Helvetica-Bold', spaceAfter=0)
    st_foot = estilo('foot', fontSize=8,  textColor=C_LGRAY, alignment=TA_CENTER, spaceAfter=2)
    st_cyan = estilo('cyan', fontSize=10, textColor=C_CYAN,  fontName='Helvetica-Bold')

    contenido = []

    # Encabezado
    if os.path.exists(LOGO_PATH):
        logo_cell = Image(LOGO_PATH, width=8.5*cm, height=2.2*cm)
    else:
        logo_cell = Paragraph('<b><font color="#00CFFF" size="22">TECNOCEL</font></b>', estilos['Title'])

    header_data = [[logo_cell],
                   [Paragraph('Venta y soporte de celulares', st_sub)],
                   [Paragraph('tecnocel.negocio@gmail.com', st_sub)]]
    ht = Table(header_data, colWidths=[W])
    ht.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),C_BLACK),('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,0),14),
        ('BOTTOMPADDING',(0,-1),(-1,-1),10),('LEFTPADDING',(0,0),(-1,-1),8),
        ('RIGHTPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,-1),(-1,-1),2,C_CYAN),
    ]))
    contenido += [ht, Spacer(1,0.4*cm)]

    # Número de factura
    n_factura = Paragraph(f'<font color="#00CFFF"><b>FACTURA #{venta["id"]:04d}</b></font>',
                          estilo('nf', fontSize=16, textColor=C_CYAN, fontName='Helvetica-Bold'))
    meta_data = [[n_factura,'',Paragraph('Fecha',st_label),Paragraph('Tipo de pago',st_label)],
                 ['','',Paragraph(venta["fecha"],st_val),
                  Paragraph(venta["tipo_pago"].upper(),
                            estilo('pv',fontSize=10,textColor=C_CYAN,fontName='Helvetica-Bold'))]]
    mt = Table(meta_data, colWidths=[W*.38,W*.08,W*.27,W*.27])
    mt.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),C_DARK2),('SPAN',(0,0),(1,1)),
        ('ALIGN',(0,0),(1,1),'LEFT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
        ('LINEBEFORE',(2,0),(2,-1),1,C_MGRAY),('LINEBEFORE',(3,0),(3,-1),1,C_MGRAY),
        ('BOX',(0,0),(-1,-1),1,C_CYAN_DIM),('ROUNDEDCORNERS',[6,6,6,6]),
    ]))
    contenido += [mt, Spacer(1,0.5*cm)]

    # Cliente
    sec_c = Table([[Paragraph('  ▌  DATOS DEL CLIENTE', st_sec)]], colWidths=[W])
    sec_c.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),C_DARK3),('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),8),
        ('LINEBEFORE',(0,0),(0,-1),3,C_CYAN),('LINEBELOW',(0,-1),(-1,-1),.5,C_MGRAY),
    ]))
    contenido += [sec_c, Spacer(1,0.15*cm)]

    filas_c = [[Paragraph(l,st_label), Paragraph(v or '—', st_val)] for l,v in [
        ('Nombre completo', cliente["nombre"]),('N° Cédula',cliente["cedula"]),
        ('Teléfono',cliente["telefono"]),('Dirección',cliente["direccion"]),
        ('Ciudad',cliente["ciudad"]),
    ]]
    tc = Table(filas_c, colWidths=[W*.28, W*.72])
    tc.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),C_DARK2),('ROWBACKGROUNDS',(0,0),(-1,-1),[C_DARK2,C_DARK3]),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BOX',(0,0),(-1,-1),1,C_CYAN_DIM),
        ('LINEBELOW',(0,0),(-1,-2),.3,C_MGRAY),
    ]))
    contenido += [tc, Spacer(1,0.5*cm)]

    # Producto
    sec_p = Table([[Paragraph('  ▌  DETALLE DE LA COMPRA', st_sec)]], colWidths=[W])
    sec_p.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),C_DARK3),('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),('LEFTPADDING',(0,0),(-1,-1),8),
        ('LINEBEFORE',(0,0),(0,-1),3,C_CYAN),('LINEBELOW',(0,-1),(-1,-1),.5,C_MGRAY),
    ]))
    contenido += [sec_p, Spacer(1,0.15*cm)]

    th = estilo('th', fontSize=9, textColor=C_CYAN, fontName='Helvetica-Bold')
    td = estilo('td', fontSize=10, textColor=C_WHITE)
    td_r = estilo('tdr', fontSize=10, textColor=C_WHITE, alignment=TA_RIGHT)
    col_w = [W*.45, W*.13, W*.21, W*.21]
    filas_p = [
        [Paragraph('Descripción',th),
         Paragraph('Cant.',estilo('thc',fontSize=9,textColor=C_CYAN,fontName='Helvetica-Bold',alignment=TA_CENTER)),
         Paragraph('Precio Unit.',estilo('thr',fontSize=9,textColor=C_CYAN,fontName='Helvetica-Bold',alignment=TA_RIGHT)),
         Paragraph('Total',estilo('thr2',fontSize=9,textColor=C_CYAN,fontName='Helvetica-Bold',alignment=TA_RIGHT))],
        [Paragraph(venta["producto"],td),
         Paragraph('1',estilo('tc2',fontSize=10,textColor=C_WHITE,alignment=TA_CENTER)),
         Paragraph(f'$ {venta["precio"]:,.0f}',td_r),
         Paragraph(f'$ {venta["precio"]:,.0f}',td_r)],
    ]
    if venta["notas"]:
        filas_p.append([Paragraph(f'Nota: {venta["notas"]}',estilo('nota',fontSize=9,textColor=C_LGRAY)),'','',''])

    tp = Table(filas_p, colWidths=col_w)
    tp.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),C_BLACK),('LINEBELOW',(0,0),(-1,0),1.5,C_CYAN),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[C_DARK2,C_DARK3]),
        ('ALIGN',(1,0),(1,-1),'CENTER'),('ALIGN',(2,0),(-1,-1),'RIGHT'),('ALIGN',(0,0),(0,-1),'LEFT'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),
        ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
        ('BOX',(0,0),(-1,-1),1,C_CYAN_DIM),('LINEBELOW',(0,1),(-1,-2),.3,C_MGRAY),
    ]))
    contenido += [tp, Spacer(1,0.4*cm)]

    # Totales
    sub_lbl = estilo('slbl',fontSize=9,textColor=C_LGRAY,fontName='Helvetica-Bold',alignment=TA_RIGHT)
    sub_val = estilo('sval',fontSize=9,textColor=C_WHITE,alignment=TA_RIGHT)
    tot_lbl = estilo('tlbl',fontSize=12,textColor=C_CYAN,fontName='Helvetica-Bold',alignment=TA_RIGHT)
    tot_val = estilo('tval',fontSize=12,textColor=C_CYAN,fontName='Helvetica-Bold',alignment=TA_RIGHT)

    filas_t = [
        ['',Paragraph('Subtotal:',sub_lbl),Paragraph(f'$ {venta["precio"]:,.0f}',sub_val)],
        ['',Paragraph('Descuento:',sub_lbl),Paragraph('$ 0',sub_val)],
        ['',Paragraph('TOTAL A PAGAR:',tot_lbl),Paragraph(f'$ {venta["precio"]:,.0f}',tot_val)],
    ]
    tt = Table(filas_t, colWidths=[W*.45,W*.3,W*.25])
    tt.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,1),C_DARK2),('BACKGROUND',(0,2),(-1,2),C_BLACK),
        ('LINEABOVE',(1,2),(-1,2),1.5,C_CYAN),('LINEBELOW',(1,2),(-1,2),1.5,C_CYAN),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),10),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BOX',(1,0),(-1,-1),1,C_CYAN_DIM),
    ]))
    contenido += [tt, Spacer(1,0.8*cm)]

    # Pie
    contenido.append(HRFlowable(width='100%', thickness=1.5, color=C_CYAN))
    contenido.append(Spacer(1,0.25*cm))
    pie_data = [[Paragraph('¡Gracias por comprar en <font color="#00CFFF"><b>Tecnocel</b></font>! — Su satisfacción es nuestra prioridad.', st_foot)],
                [Paragraph('Este comprobante es válido para reclamaciones. Consérvelo.',
                           estilo('fp2',fontSize=8,textColor=C_MGRAY,alignment=TA_CENTER))]]
    pie_t = Table(pie_data, colWidths=[W])
    pie_t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),C_BLACK),('TOPPADDING',(0,0),(-1,-1),6),
        ('BOTTOMPADDING',(0,0),(-1,-1),6),('ALIGN',(0,0),(-1,-1),'CENTER'),
    ]))
    contenido.append(pie_t)

    doc.build(contenido, onFirstPage=fondo_oscuro, onLaterPages=fondo_oscuro)
    return ruta_pdf, nombre_archivo


@facturas_bp.route('/<int:venta_id>')
@login_required
def generar(venta_id):
    nid = session['negocio_id']
    db  = get_db()
    venta = db.execute('''
        SELECT v.*, c.nombre, c.cedula, c.telefono, c.direccion, c.ciudad
        FROM ventas v JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ? AND v.negocio_id = ?
    ''', (venta_id, nid)).fetchone()

    if not venta:
        flash('Factura no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))

    return render_template('facturas/previa.html', venta=venta)


@facturas_bp.route('/<int:venta_id>/descargar')
@login_required
def descargar(venta_id):
    nid = session['negocio_id']
    db  = get_db()
    venta = db.execute('''
        SELECT v.*, c.nombre, c.cedula, c.telefono, c.direccion, c.ciudad
        FROM ventas v JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ? AND v.negocio_id = ?
    ''', (venta_id, nid)).fetchone()

    if not venta:
        flash('Factura no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))

    try:
        ruta_pdf, nombre_archivo = generar_pdf(venta, venta)
        return send_file(ruta_pdf, as_attachment=True,
                         download_name=nombre_archivo, mimetype='application/pdf')
    except Exception as e:
        flash(f'Error al generar la factura: {str(e)}', 'danger')
        return redirect(url_for('ventas.lista'))

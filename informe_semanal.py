"""
informe_semanal.py — Tecnocel CRM
Genera automáticamente un informe PDF con el resumen de la semana anterior.
Se ejecuta cada lunes via el Programador de Tareas de Windows.
"""

import sqlite3
import os
import sys
from datetime import datetime, timedelta, date

# ── ReportLab ──────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, KeepTogether)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# ── Configuración ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'tecnocel.db')

MESES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

DIAS_ES = {
    0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves',
    4: 'Viernes', 5: 'Sábado', 6: 'Domingo'
}


def fmt_moneda(valor):
    """Formatea un número como moneda colombiana."""
    if valor is None:
        return '$ 0'
    return '$ ' + f'{int(valor):,}'.replace(',', '.')


def calcular_semana_anterior():
    """Calcula el lunes y domingo de la semana anterior."""
    hoy = date.today()
    # Lunes de esta semana
    lunes_esta = hoy - timedelta(days=hoy.weekday())
    # Lunes y domingo de la semana anterior
    lunes_ant  = lunes_esta - timedelta(days=7)
    domingo_ant = lunes_esta - timedelta(days=1)
    return lunes_ant, domingo_ant


def obtener_datos(conn, negocio_id, fecha_ini, fecha_fin):
    """Consulta todos los datos de la semana para un negocio."""
    fi = fecha_ini.isoformat()
    ff = fecha_fin.isoformat()

    # Ventas de accesorios (no servicios)
    ventas = conn.execute('''
        SELECT v.producto, v.precio, v.tipo_pago, v.fecha,
               c.nombre AS cliente
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.negocio_id = ?
          AND v.fecha BETWEEN ? AND ?
          AND v.producto NOT LIKE 'Servicio: %'
        ORDER BY v.fecha
    ''', (negocio_id, fi, ff)).fetchall()

    # Reparaciones entregadas
    reparaciones = conn.execute('''
        SELECT o.numero_orden, o.marca_modelo, o.problema,
               o.costo_final, o.abono, o.saldo_pendiente,
               o.fecha_entregado, c.nombre AS cliente
        FROM ordenes o
        JOIN clientes c ON o.cliente_id = c.id
        WHERE o.negocio_id = ?
          AND o.estado = 'entregado'
          AND o.fecha_entregado BETWEEN ? AND ?
        ORDER BY o.fecha_entregado
    ''', (negocio_id, fi, ff)).fetchall()

    # Órdenes recibidas en la semana
    ordenes_recibidas = conn.execute('''
        SELECT COUNT(*) as total
        FROM ordenes
        WHERE negocio_id = ? AND fecha_recibido BETWEEN ? AND ?
    ''', (negocio_id, fi, ff)).fetchone()[0]

    # Órdenes pendientes (no entregadas)
    ordenes_pendientes = conn.execute('''
        SELECT COUNT(*) as total
        FROM ordenes
        WHERE negocio_id = ? AND estado != 'entregado'
    ''', (negocio_id,)).fetchone()[0]

    # Egresos de la semana
    egresos = conn.execute('''
        SELECT concepto, monto, fecha, notas
        FROM egresos
        WHERE negocio_id = ? AND fecha BETWEEN ? AND ?
        ORDER BY fecha
    ''', (negocio_id, fi, ff)).fetchall()

    return ventas, reparaciones, ordenes_recibidas, ordenes_pendientes, egresos


def generar_pdf(negocio, ventas, reparaciones, ordenes_recibidas,
                ordenes_pendientes, egresos, fecha_ini, fecha_fin):
    """Genera el PDF del informe semanal y lo guarda en la carpeta correcta."""

    ahora = datetime.now()
    anio  = ahora.strftime('%Y')
    mes   = MESES_ES[ahora.month]
    dia   = ahora.strftime('%d')
    hora  = ahora.strftime('%H-%M-%S')

    # Carpeta: informes/2026/Abril/06/
    carpeta = os.path.join(BASE_DIR, 'informes', anio, mes, dia)
    os.makedirs(carpeta, exist_ok=True)

    semana_label = (f"{fecha_ini.strftime('%d/%m/%Y')} — "
                    f"{fecha_fin.strftime('%d/%m/%Y')}")
    nombre_archivo = f"informe_semanal_{fecha_ini.strftime('%Y%m%d')}_{hora}.pdf"
    ruta = os.path.join(carpeta, nombre_archivo)

    doc = SimpleDocTemplate(ruta, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    # ── Estilos ──────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()
    s_titulo  = ParagraphStyle('titulo', fontSize=22, alignment=TA_CENTER,
                               fontName='Helvetica-Bold', spaceAfter=2,
                               textColor=colors.HexColor('#1a73e8'))
    s_sub     = ParagraphStyle('sub', fontSize=10, alignment=TA_CENTER,
                               textColor=colors.grey, spaceAfter=2)
    s_seccion = ParagraphStyle('seccion', fontSize=13, fontName='Helvetica-Bold',
                               textColor=colors.HexColor('#1a73e8'),
                               spaceBefore=14, spaceAfter=6)
    s_normal  = ParagraphStyle('normal', fontSize=10, spaceAfter=4)
    s_pie     = ParagraphStyle('pie', fontSize=8, alignment=TA_CENTER,
                               textColor=colors.grey, spaceBefore=20)
    s_total   = ParagraphStyle('total', fontSize=12, fontName='Helvetica-Bold',
                               alignment=TA_RIGHT, textColor=colors.HexColor('#1a73e8'))

    nombre_negocio   = negocio['nombre_negocio'] if negocio else 'Tecnocel'
    telefono_negocio = negocio['telefono'] if negocio else ''

    contenido = []

    # ── Encabezado ───────────────────────────────────────────────────────
    contenido.append(Paragraph(nombre_negocio.upper(), s_titulo))
    if telefono_negocio:
        contenido.append(Paragraph(f'Tel: {telefono_negocio}', s_sub))
    contenido.append(Paragraph('INFORME SEMANAL DE FACTURACIÓN', s_sub))
    contenido.append(Paragraph(f'Semana: {semana_label}', s_sub))
    contenido.append(Paragraph(
        f'Generado: {ahora.strftime("%d/%m/%Y %H:%M")}', s_sub))
    contenido.append(Spacer(1, 0.3*cm))
    contenido.append(HRFlowable(width='100%', thickness=2,
                                color=colors.HexColor('#1a73e8')))
    contenido.append(Spacer(1, 0.4*cm))

    # ── Resumen ejecutivo ────────────────────────────────────────────────
    total_ventas_acc  = sum(v['precio'] for v in ventas)
    total_reparaciones = sum(r['costo_final'] or 0 for r in reparaciones)
    total_egresos     = sum(e['monto'] for e in egresos)
    total_ingresos    = total_ventas_acc + total_reparaciones
    balance_semana    = total_ingresos - total_egresos

    color_balance = colors.HexColor('#1a7a4a') if balance_semana >= 0 else colors.red

    resumen_data = [
        ['CONCEPTO', 'CANTIDAD', 'VALOR'],
        ['Accesorios vendidos', str(len(ventas)), fmt_moneda(total_ventas_acc)],
        ['Reparaciones entregadas', str(len(reparaciones)), fmt_moneda(total_reparaciones)],
        ['Total ingresos', '', fmt_moneda(total_ingresos)],
        ['Total egresos', str(len(egresos)), fmt_moneda(total_egresos)],
        ['BALANCE NETO', '', fmt_moneda(balance_semana)],
        ['Equipos recibidos (semana)', str(ordenes_recibidas), ''],
        ['Equipos pendientes (acumulado)', str(ordenes_pendientes), ''],
    ]

    tabla_resumen = Table(resumen_data, colWidths=[9*cm, 3.5*cm, 4.5*cm])
    tabla_resumen.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND',   (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
        ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, 0), 10),
        ('ALIGN',        (1, 0), (-1, 0), 'CENTER'),
        # Filas pares/impares
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor('#f0f5ff')]),
        ('FONTSIZE',     (0, 1), (-1, -1), 10),
        ('TOPPADDING',   (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 7),
        ('LEFTPADDING',  (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN',        (1, 1), (-1, -1), 'CENTER'),
        ('ALIGN',        (2, 1), (-1, -1), 'RIGHT'),
        # Fila Total ingresos
        ('FONTNAME',     (0, 3), (-1, 3), 'Helvetica-Bold'),
        ('BACKGROUND',   (0, 3), (-1, 3), colors.HexColor('#e8f5e9')),
        # Fila Total egresos
        ('FONTNAME',     (0, 4), (-1, 4), 'Helvetica-Bold'),
        ('BACKGROUND',   (0, 4), (-1, 4), colors.HexColor('#fff3e0')),
        # Fila Balance
        ('FONTNAME',     (0, 5), (-1, 5), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 5), (-1, 5), 11),
        ('BACKGROUND',   (0, 5), (-1, 5), colors.HexColor('#e3f2fd')),
        ('TEXTCOLOR',    (2, 5), (2, 5), color_balance),
        # Bordes
        ('GRID',         (0, 0), (-1, -1), 0.3, colors.HexColor('#d0d0d0')),
        ('BOX',          (0, 0), (-1, -1), 1, colors.HexColor('#1a73e8')),
    ]))

    contenido.append(Paragraph('RESUMEN EJECUTIVO', s_seccion))
    contenido.append(tabla_resumen)
    contenido.append(Spacer(1, 0.5*cm))

    # ── Detalle de Reparaciones ──────────────────────────────────────────
    if reparaciones:
        contenido.append(HRFlowable(width='100%', thickness=0.5,
                                    color=colors.lightgrey))
        contenido.append(Paragraph('REPARACIONES ENTREGADAS', s_seccion))

        rep_data = [['Orden', 'Cliente', 'Equipo', 'Fecha', 'Costo Final']]
        for r in reparaciones:
            rep_data.append([
                r['numero_orden'],
                r['cliente'].title()[:20],
                r['marca_modelo'][:22],
                r['fecha_entregado'] or '',
                fmt_moneda(r['costo_final'])
            ])

        tabla_rep = Table(rep_data,
                          colWidths=[3*cm, 4*cm, 4.5*cm, 2.5*cm, 3*cm])
        tabla_rep.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [colors.white, colors.HexColor('#f0f5ff')]),
            ('TOPPADDING',   (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
            ('LEFTPADDING',  (0, 0), (-1, -1), 6),
            ('ALIGN',        (4, 1), (4, -1), 'RIGHT'),
            ('GRID',         (0, 0), (-1, -1), 0.3, colors.HexColor('#d0d0d0')),
        ]))
        contenido.append(tabla_rep)
        contenido.append(Spacer(1, 0.4*cm))

    # ── Detalle de Ventas de Accesorios ──────────────────────────────────
    if ventas:
        contenido.append(HRFlowable(width='100%', thickness=0.5,
                                    color=colors.lightgrey))
        contenido.append(Paragraph('VENTAS DE ACCESORIOS', s_seccion))

        ven_data = [['Producto', 'Cliente', 'Fecha', 'Pago', 'Precio']]
        for v in ventas:
            ven_data.append([
                v['producto'][:28],
                v['cliente'].title()[:20],
                v['fecha'] or '',
                v['tipo_pago'].title(),
                fmt_moneda(v['precio'])
            ])

        tabla_ven = Table(ven_data,
                          colWidths=[4.5*cm, 3.5*cm, 2.5*cm, 2.5*cm, 4*cm])
        tabla_ven.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [colors.white, colors.HexColor('#f0f5ff')]),
            ('TOPPADDING',   (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
            ('LEFTPADDING',  (0, 0), (-1, -1), 6),
            ('ALIGN',        (4, 1), (4, -1), 'RIGHT'),
            ('GRID',         (0, 0), (-1, -1), 0.3, colors.HexColor('#d0d0d0')),
        ]))
        contenido.append(tabla_ven)
        contenido.append(Spacer(1, 0.4*cm))

    # ── Detalle de Egresos ───────────────────────────────────────────────
    if egresos:
        contenido.append(HRFlowable(width='100%', thickness=0.5,
                                    color=colors.lightgrey))
        contenido.append(Paragraph('EGRESOS DE LA SEMANA', s_seccion))

        egr_data = [['Concepto', 'Categoría / Notas', 'Fecha', 'Monto']]
        for e in egresos:
            egr_data.append([
                e['concepto'][:30],
                (e['notas'] or '')[:25],
                e['fecha'] or '',
                fmt_moneda(e['monto'])
            ])

        tabla_egr = Table(egr_data,
                          colWidths=[5*cm, 4.5*cm, 2.5*cm, 5*cm])
        tabla_egr.setStyle(TableStyle([
            ('BACKGROUND',   (0, 0), (-1, 0), colors.HexColor('#e53935')),
            ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
            ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [colors.white, colors.HexColor('#fff3f3')]),
            ('TOPPADDING',   (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
            ('LEFTPADDING',  (0, 0), (-1, -1), 6),
            ('ALIGN',        (3, 1), (3, -1), 'RIGHT'),
            ('GRID',         (0, 0), (-1, -1), 0.3, colors.HexColor('#d0d0d0')),
        ]))
        contenido.append(tabla_egr)
        contenido.append(Spacer(1, 0.4*cm))

    # ── Pie de página ────────────────────────────────────────────────────
    contenido.append(HRFlowable(width='100%', thickness=1,
                                color=colors.HexColor('#1a73e8')))
    contenido.append(Paragraph(
        f'Informe generado automáticamente por Tecnocel CRM — '
        f'{ahora.strftime("%d/%m/%Y %H:%M:%S")}',
        s_pie))

    doc.build(contenido)
    return ruta, nombre_archivo


def main():
    print("=" * 55)
    print("  Tecnocel CRM — Generador de Informe Semanal")
    print("=" * 55)

    if not os.path.exists(DB_PATH):
        print(f"ERROR: No se encontró la base de datos en {DB_PATH}")
        sys.exit(1)

    fecha_ini, fecha_fin = calcular_semana_anterior()
    print(f"  Semana: {fecha_ini.strftime('%d/%m/%Y')} — "
          f"{fecha_fin.strftime('%d/%m/%Y')}")

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row

    negocios = conn.execute(
        "SELECT * FROM negocios WHERE activo = 1"
    ).fetchall()

    if not negocios:
        print("  No hay negocios activos en la base de datos.")
        conn.close()
        sys.exit(0)

    informes_generados = []

    for negocio in negocios:
        nid = negocio['id']
        nombre = negocio['nombre_negocio']
        print(f"\n  Procesando: {nombre} (ID {nid})")

        ventas, reparaciones, ord_recibidas, ord_pendientes, egresos = \
            obtener_datos(conn, nid, fecha_ini, fecha_fin)

        print(f"    Ventas accesorios : {len(ventas)}")
        print(f"    Reparaciones      : {len(reparaciones)}")
        print(f"    Egresos           : {len(egresos)}")

        ruta, nombre_archivo = generar_pdf(
            negocio, ventas, reparaciones,
            ord_recibidas, ord_pendientes, egresos,
            fecha_ini, fecha_fin
        )

        informes_generados.append(ruta)
        print(f"    PDF generado: {ruta}")

    conn.close()

    # Abrir la carpeta con los informes en Windows Explorer
    if informes_generados and sys.platform == 'win32':
        import subprocess
        carpeta = os.path.dirname(informes_generados[0])
        subprocess.Popen(['explorer', carpeta])

    print(f"\n  ✅ {len(informes_generados)} informe(s) generado(s) correctamente.")
    print("=" * 55)


if __name__ == '__main__':
    main()

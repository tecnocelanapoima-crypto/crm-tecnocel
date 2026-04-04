"""
Finanzas — control de ingresos, egresos y balance del negocio.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db
from routes.auth import login_required
from datetime import datetime

finanzas_bp = Blueprint('finanzas', __name__)


@finanzas_bp.route('/')
@login_required
def lista():
    nid = session['negocio_id']
    db  = get_db()

    # Filtros opcionales por mes y año
    hoy    = datetime.now()
    mes    = request.args.get('mes', str(hoy.month).zfill(2))
    anio   = request.args.get('anio', str(hoy.year))
    filtro = f"{anio}-{mes}"

    # Ingresos totales (histórico)
    ingresos_total = db.execute(
        'SELECT COALESCE(SUM(precio), 0) FROM ventas WHERE negocio_id = ?', (nid,)
    ).fetchone()[0]

    # Ingresos del mes seleccionado
    ingresos_mes = db.execute(
        "SELECT COALESCE(SUM(precio), 0) FROM ventas WHERE negocio_id = ? AND strftime('%Y-%m', fecha) = ?",
        (nid, filtro)
    ).fetchone()[0]

    # Egresos totales (histórico)
    egresos_total = db.execute(
        'SELECT COALESCE(SUM(monto), 0) FROM egresos WHERE negocio_id = ?', (nid,)
    ).fetchone()[0]

    # Egresos del mes seleccionado
    egresos_mes = db.execute(
        "SELECT COALESCE(SUM(monto), 0) FROM egresos WHERE negocio_id = ? AND strftime('%Y-%m', fecha) = ?",
        (nid, filtro)
    ).fetchone()[0]

    # Lista de egresos del mes seleccionado
    egresos = db.execute(
        "SELECT * FROM egresos WHERE negocio_id = ? AND strftime('%Y-%m', fecha) = ? ORDER BY fecha DESC, fecha_creacion DESC",
        (nid, filtro)
    ).fetchall()

    # Ventas del mes seleccionado
    ventas_mes = db.execute('''
        SELECT v.fecha, v.producto, v.precio, v.tipo_pago, c.nombre AS cliente_nombre
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.negocio_id = ? AND strftime('%Y-%m', v.fecha) = ?
        ORDER BY v.fecha DESC
    ''', (nid, filtro)).fetchall()

    balance_total = ingresos_total - egresos_total
    balance_mes   = ingresos_mes - egresos_mes

    # Generar lista de meses disponibles para el selector
    meses_disponibles = [
        {'valor': str(m).zfill(2), 'nombre': datetime(2000, m, 1).strftime('%B').capitalize()}
        for m in range(1, 13)
    ]

    db.close()

    return render_template('finanzas/lista.html',
                           ingresos_total=ingresos_total,
                           egresos_total=egresos_total,
                           balance_total=balance_total,
                           ingresos_mes=ingresos_mes,
                           egresos_mes=egresos_mes,
                           balance_mes=balance_mes,
                           egresos=egresos,
                           ventas_mes=ventas_mes,
                           hoy=hoy.strftime('%Y-%m-%d'),
                           mes_actual=mes,
                           anio_actual=anio,
                           filtro=filtro,
                           meses_disponibles=meses_disponibles,
                           anio_min=2024,
                           anio_max=hoy.year + 1)


@finanzas_bp.route('/egreso/crear', methods=['POST'])
@login_required
def crear_egreso():
    nid      = session['negocio_id']
    concepto = request.form.get('concepto', '').strip()
    notas    = request.form.get('notas', '').strip()
    fecha    = request.form.get('fecha', '').strip()

    errores = []
    if not concepto:
        errores.append('El concepto del gasto es obligatorio.')
    if not fecha:
        errores.append('La fecha es obligatoria.')

    try:
        monto = float(request.form.get('monto', 0))
        if monto <= 0:
            errores.append('El monto debe ser mayor a cero.')
    except (ValueError, TypeError):
        errores.append('El monto debe ser un número válido.')
        monto = 0

    if errores:
        for e in errores:
            flash(e, 'danger')
        return redirect(url_for('finanzas.lista'))

    db = get_db()
    db.execute('''
        INSERT INTO egresos (negocio_id, concepto, monto, fecha, notas)
        VALUES (?, ?, ?, ?, ?)
    ''', (nid, concepto, monto, fecha, notas))
    db.commit()
    db.close()
    flash(f'Gasto "{concepto}" por $ {monto:,.0f} registrado correctamente.', 'success')
    return redirect(url_for('finanzas.lista'))


@finanzas_bp.route('/egreso/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_egreso(id):
    nid = session['negocio_id']
    db  = get_db()
    egreso = db.execute(
        'SELECT concepto, monto FROM egresos WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()

    if egreso:
        db.execute('DELETE FROM egresos WHERE id = ? AND negocio_id = ?', (id, nid))
        db.commit()
        flash(f'Gasto "{egreso["concepto"]}" eliminado.', 'success')
    else:
        flash('Gasto no encontrado.', 'danger')

    db.close()
    return redirect(url_for('finanzas.lista'))

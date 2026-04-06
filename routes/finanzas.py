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

    ingresos_total = db.execute(
        'SELECT COALESCE(SUM(precio), 0) FROM ventas WHERE negocio_id = ?', (nid,)
    ).fetchone()[0]

    egresos = db.execute(
        'SELECT * FROM egresos WHERE negocio_id = ? ORDER BY fecha DESC, fecha_creacion DESC',
        (nid,)
    ).fetchall()

    egresos_total = db.execute(
        'SELECT COALESCE(SUM(monto), 0) FROM egresos WHERE negocio_id = ?', (nid,)
    ).fetchone()[0]

    balance_total = ingresos_total - egresos_total

    return render_template('finanzas/lista.html',
                           ingresos_total=ingresos_total,
                           egresos_total=egresos_total,
                           balance_total=balance_total,
                           egresos=egresos,
                           hoy=datetime.now().strftime('%Y-%m-%d'))


@finanzas_bp.route('/egreso/crear', methods=['POST'])
@login_required
def crear_egreso():
    nid      = session['negocio_id']
    concepto = request.form.get('concepto', '').strip()
    monto    = request.form.get('monto', 0)
    fecha    = request.form.get('fecha', '')
    notas    = request.form.get('notas', '').strip()

    if not concepto or not monto or not fecha:
        flash('Concepto, monto y fecha son obligatorios', 'danger')
        return redirect(url_for('finanzas.lista'))

    db = get_db()
    db.execute('''
        INSERT INTO egresos (negocio_id, concepto, monto, fecha, notas)
        VALUES (?, ?, ?, ?, ?)
    ''', (nid, concepto, float(monto), fecha, notas))
    db.commit()
    flash('Gasto registrado correctamente.', 'success')
    return redirect(url_for('finanzas.lista'))


@finanzas_bp.route('/egreso/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_egreso(id):
    nid = session['negocio_id']
    db  = get_db()
    db.execute('DELETE FROM egresos WHERE id = ? AND negocio_id = ?', (id, nid))
    db.commit()
    flash('Gasto eliminado.', 'success')
    return redirect(url_for('finanzas.lista'))

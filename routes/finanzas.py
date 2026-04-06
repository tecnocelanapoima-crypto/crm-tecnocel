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

    ventas = db.execute(
        'SELECT * FROM ventas WHERE negocio_id = ? ORDER BY fecha DESC, id DESC',
        (nid,)
    ).fetchall()

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
                           ventas=ventas,
                           egresos=egresos,
                           hoy=datetime.now().strftime('%Y-%m-%d'))


@finanzas_bp.route('/egreso/crear', methods=['POST'])
@login_required
def crear_egreso():
    nid       = session['negocio_id']
    concepto  = request.form.get('concepto', '').strip()
    monto     = request.form.get('monto', 0)
    fecha     = request.form.get('fecha', '')
    notas     = request.form.get('notas', '').strip()
    categoria = request.form.get('categoria', '').strip()

    if not concepto or not monto or not fecha:
        flash('Concepto, monto y fecha son obligatorios', 'danger')
        return redirect(url_for('finanzas.lista'))

    db = get_db()
    # Migración automática: agregar columna categoria si no existe
    try:
        db.execute('ALTER TABLE egresos ADD COLUMN categoria TEXT DEFAULT ""')
        db.commit()
    except Exception:
        pass  # La columna ya existe

    db.execute('''
        INSERT INTO egresos (negocio_id, concepto, monto, fecha, notas, categoria)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (nid, concepto, float(monto), fecha, notas, categoria))
    db.commit()
    flash('Gasto registrado correctamente.', 'success')
    return redirect(url_for('finanzas.lista'))


@finanzas_bp.route('/venta/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_venta(id):
    nid = session['negocio_id']
    db  = get_db()
    db.execute('DELETE FROM ventas WHERE id = ? AND negocio_id = ?', (id, nid))
    db.commit()
    flash('Venta eliminada.', 'success')
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

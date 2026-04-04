from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import get_db
from datetime import datetime

finanzas_bp = Blueprint('finanzas', __name__)

@finanzas_bp.route('/')
def lista():
    db = get_db()
    
    # Calcular suma total de ingresos (todas las ventas registradas con cliente válido)
    ingresos_total = db.execute('SELECT COALESCE(SUM(v.precio), 0) FROM ventas v JOIN clientes c ON v.cliente_id = c.id').fetchone()[0]
    
    # Obtener lista de egresos y suma total
    egresos = db.execute('SELECT * FROM egresos ORDER BY fecha DESC, fecha_creacion DESC').fetchall()
    egresos_total = db.execute('SELECT COALESCE(SUM(monto), 0) FROM egresos').fetchone()[0]
    
    balance_total = ingresos_total - egresos_total
    
    db.close()
    return render_template(
        'finanzas/lista.html', 
        ingresos_total=ingresos_total,
        egresos_total=egresos_total,
        balance_total=balance_total,
        egresos=egresos,
        hoy=datetime.now().strftime('%Y-%m-%d')
    )

@finanzas_bp.route('/egreso/crear', methods=['POST'])
def crear_egreso():
    concepto = request.form.get('concepto', '').strip()
    monto = request.form.get('monto', 0)
    fecha = request.form.get('fecha', '')
    notas = request.form.get('notas', '').strip()
    
    if not concepto or not monto or not fecha:
        flash('Concepto, monto y fecha son obligatorios', 'danger')
        return redirect(url_for('finanzas.lista'))
        
    db = get_db()
    db.execute('''
        INSERT INTO egresos (concepto, monto, fecha, notas)
        VALUES (?, ?, ?, ?)
    ''', (concepto, float(monto), fecha, notas))
    db.commit()
    db.close()
    
    flash('Gasto registrado correctamente.', 'success')
    return redirect(url_for('finanzas.lista'))

@finanzas_bp.route('/egreso/<int:id>/eliminar', methods=['POST'])
def eliminar_egreso(id):
    db = get_db()
    db.execute('DELETE FROM egresos WHERE id = ?', (id,))
    db.commit()
    db.close()
    
    flash('Gasto eliminado.', 'success')
    return redirect(url_for('finanzas.lista'))

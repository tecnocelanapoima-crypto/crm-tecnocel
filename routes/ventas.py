"""
Rutas para gestión de ventas
Permite registrar, ver y eliminar ventas asociadas a clientes
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import get_db
from datetime import date

ventas_bp = Blueprint('ventas', __name__)


@ventas_bp.route('/')
def lista():
    """Lista todas las ventas con filtro opcional por cliente"""
    db = get_db()
    cliente_id = request.args.get('cliente_id', '')

    if cliente_id:
        ventas = db.execute('''
            SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ventas v
            JOIN clientes c ON v.cliente_id = c.id
            WHERE v.cliente_id = ?
            ORDER BY v.fecha DESC
        ''', (cliente_id,)).fetchall()
    else:
        ventas = db.execute('''
            SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ventas v
            JOIN clientes c ON v.cliente_id = c.id
            ORDER BY v.fecha_creacion DESC
        ''').fetchall()

    # Total de ingresos filtrados
    total_ingresos = sum(v['precio'] for v in ventas)
    db.close()

    return render_template('ventas/lista.html',
                           ventas=ventas,
                           total_ingresos=total_ingresos)


@ventas_bp.route('/crear', methods=['GET', 'POST'])
def crear():
    """Formulario y procesamiento para registrar una nueva venta"""
    db = get_db()

    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id', '').strip()
        producto = request.form.get('producto', '').strip()
        precio = request.form.get('precio', '').strip()
        tipo_pago = request.form.get('tipo_pago', 'contado').strip()
        fecha = request.form.get('fecha', '').strip()
        notas = request.form.get('notas', '').strip()

        # Validaciones
        errores = []
        if not cliente_id:
            errores.append('Debe seleccionar un cliente.')
        if not producto:
            errores.append('El producto es obligatorio.')
        if not precio:
            errores.append('El precio es obligatorio.')
        else:
            try:
                precio = float(precio)
                if precio <= 0:
                    errores.append('El precio debe ser mayor a 0.')
            except ValueError:
                errores.append('El precio debe ser un número válido.')
        if not fecha:
            errores.append('La fecha es obligatoria.')

        if errores:
            for error in errores:
                flash(error, 'danger')
            clientes = db.execute('SELECT id, nombre, telefono FROM clientes ORDER BY nombre').fetchall()
            db.close()
            return render_template('ventas/form.html',
                                   clientes=clientes,
                                   form=request.form,
                                   hoy=date.today().isoformat())

        db.execute('''
            INSERT INTO ventas (cliente_id, producto, precio, tipo_pago, fecha, notas)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (cliente_id, producto, precio, tipo_pago, fecha, notas))
        db.commit()

        # Obtener el ID de la venta recién creada
        venta_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.close()

        flash(f'Venta de "{producto}" registrada exitosamente.', 'success')
        return redirect(url_for('facturas.generar', venta_id=venta_id))

    # Asegurar que exista 'CLIENTE EXPRÉS'
    cliente_expres = db.execute('SELECT id FROM clientes WHERE UPPER(nombre) LIKE "%EXPR_S%" OR UPPER(nombre) LIKE "%EXPRES%"').fetchone()
    if not cliente_expres:
        db.execute('INSERT INTO clientes (nombre, telefono) VALUES (?, ?)', ('CLIENTE EXPRÉS', '0000000000'))
        db.commit()
        cliente_expres = db.execute('SELECT id FROM clientes WHERE UPPER(nombre) LIKE "%EXPRES%" OR UPPER(nombre) LIKE "%EXPR_S%"').fetchone()

    clientes = db.execute('SELECT id, nombre, telefono FROM clientes ORDER BY nombre').fetchall()
    db.close()

    # Pasar cliente preseleccionado si viene de la URL (o Cliente Exprés por defecto)
    cliente_preseleccionado = request.args.get('cliente_id', cliente_expres['id'] if cliente_expres else '')

    return render_template('ventas/form.html',
                           clientes=clientes,
                           form={'cliente_id': str(cliente_preseleccionado)},
                           hoy=date.today().isoformat())


@ventas_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
def editar(id):
    db = get_db()
    venta = db.execute('SELECT * FROM ventas WHERE id = ?', (id,)).fetchone()
    
    if not venta:
        db.close()
        flash('Venta no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))
        
    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id', '').strip()
        producto = request.form.get('producto', '').strip()
        precio = request.form.get('precio', '').strip()
        tipo_pago = request.form.get('tipo_pago', 'contado').strip()
        fecha = request.form.get('fecha', '').strip()
        notas = request.form.get('notas', '').strip()

        errores = []
        if not cliente_id: errores.append('Debe seleccionar un cliente.')
        if not producto: errores.append('El producto es obligatorio.')
        if not precio:
            errores.append('El precio es obligatorio.')
        else:
            try:
                precio = float(precio)
            except ValueError:
                errores.append('El precio debe ser un número válido.')
        if not fecha: errores.append('La fecha es obligatoria.')

        if errores:
            for error in errores:
                flash(error, 'danger')
            clientes = db.execute('SELECT id, nombre FROM clientes ORDER BY nombre').fetchall()
            db.close()
            venta_dict = dict(venta)
            venta_dict.update(request.form)
            return render_template('ventas/form.html', clientes=clientes, form=venta_dict, accion='Editar')

        db.execute('''
            UPDATE ventas 
            SET cliente_id=?, producto=?, precio=?, tipo_pago=?, fecha=?, notas=?
            WHERE id=?
        ''', (cliente_id, producto, precio, tipo_pago, fecha, notas, id))
        db.commit()
        db.close()

        flash('Venta actualizada correctamente.', 'success')
        # Redirigir al panel referer si es que venía de ahí, o a la lista de ventas
        referer = request.headers.get("Referer")
        if referer and ("ventas" not in referer) and ("editar" not in referer):
            return redirect(url_for('index'))
        return redirect(url_for('index')) # We fallback to index because the dashboard invokes this mainly

    clientes = db.execute('SELECT id, nombre, telefono FROM clientes ORDER BY nombre').fetchall()
    db.close()
    return render_template('ventas/form.html', clientes=clientes, form=dict(venta), accion='Editar', hoy=venta['fecha'])

@ventas_bp.route('/<int:id>/eliminar', methods=['POST'])
def eliminar(id):
    """Elimina una venta por su ID"""
    db = get_db()
    venta = db.execute('SELECT producto FROM ventas WHERE id = ?', (id,)).fetchone()

    if venta:
        db.execute('DELETE FROM ventas WHERE id = ?', (id,))
        db.commit()
        flash(f'Venta de "{venta["producto"]}" eliminada.', 'success')
    else:
        flash('Venta no encontrada.', 'danger')

    db.close()
    return redirect(url_for('ventas.lista'))

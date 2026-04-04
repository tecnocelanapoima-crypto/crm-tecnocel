from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db
from routes.auth import login_required
from datetime import date

ventas_bp = Blueprint('ventas', __name__)


@ventas_bp.route('/')
@login_required
def lista():
    nid = session['negocio_id']
    db  = get_db()
    cliente_id = request.args.get('cliente_id', '')

    if cliente_id:
        ventas = db.execute('''
            SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ventas v JOIN clientes c ON v.cliente_id = c.id
            WHERE v.negocio_id = ? AND v.cliente_id = ?
            ORDER BY v.fecha DESC
        ''', (nid, cliente_id)).fetchall()
    else:
        ventas = db.execute('''
            SELECT v.*, c.nombre as cliente_nombre, c.telefono as cliente_telefono
            FROM ventas v JOIN clientes c ON v.cliente_id = c.id
            WHERE v.negocio_id = ?
            ORDER BY v.fecha_creacion DESC
        ''', (nid,)).fetchall()

    total_ingresos = sum(v['precio'] for v in ventas)
    db.close()
    return render_template('ventas/lista.html', ventas=ventas, total_ingresos=total_ingresos)


@ventas_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear():
    nid = session['negocio_id']
    db  = get_db()

    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id', '').strip()
        producto   = request.form.get('producto', '').strip()
        precio     = request.form.get('precio', '').strip()
        tipo_pago  = request.form.get('tipo_pago', 'contado').strip()
        fecha      = request.form.get('fecha', '').strip()
        notas      = request.form.get('notas', '').strip()

        errores = []
        if not cliente_id: errores.append('Debe seleccionar un cliente.')
        if not producto:   errores.append('El producto es obligatorio.')
        if not fecha:      errores.append('La fecha es obligatoria.')
        if not precio:
            errores.append('El precio es obligatorio.')
        else:
            try:
                precio = float(precio)
                if precio <= 0: errores.append('El precio debe ser mayor a 0.')
            except ValueError:
                errores.append('El precio debe ser un número válido.')

        # Verificar que el cliente pertenece a este negocio
        if cliente_id:
            cli = db.execute(
                'SELECT id FROM clientes WHERE id = ? AND negocio_id = ?',
                (cliente_id, nid)
            ).fetchone()
            if not cli: errores.append('Cliente no válido.')

        if errores:
            for e in errores: flash(e, 'danger')
            clientes = db.execute(
                'SELECT id, nombre, telefono FROM clientes WHERE negocio_id = ? ORDER BY nombre',
                (nid,)
            ).fetchall()
            db.close()
            return render_template('ventas/form.html', clientes=clientes,
                                   form=request.form, hoy=date.today().isoformat())

        db.execute('''
            INSERT INTO ventas (negocio_id, cliente_id, producto, precio, tipo_pago, fecha, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nid, cliente_id, producto, precio, tipo_pago, fecha, notas))
        db.commit()
        venta_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.close()
        flash(f'Venta de "{producto}" registrada exitosamente.', 'success')
        return redirect(url_for('facturas.generar', venta_id=venta_id))

    # Asegurar Cliente Exprés para este negocio
    expres = db.execute(
        "SELECT id FROM clientes WHERE negocio_id = ? AND UPPER(nombre) LIKE '%EXPRES%'",
        (nid,)
    ).fetchone()
    if not expres:
        db.execute(
            'INSERT INTO clientes (negocio_id, nombre, telefono) VALUES (?, ?, ?)',
            (nid, 'CLIENTE EXPRÉS', '0000000000')
        )
        db.commit()
        expres = db.execute(
            "SELECT id FROM clientes WHERE negocio_id = ? AND UPPER(nombre) LIKE '%EXPRES%'",
            (nid,)
        ).fetchone()

    clientes = db.execute(
        'SELECT id, nombre, telefono FROM clientes WHERE negocio_id = ? ORDER BY nombre',
        (nid,)
    ).fetchall()
    db.close()

    cliente_preseleccionado = request.args.get('cliente_id', expres['id'] if expres else '')
    return render_template('ventas/form.html', clientes=clientes,
                           form={'cliente_id': str(cliente_preseleccionado)},
                           hoy=date.today().isoformat())


@ventas_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    nid = session['negocio_id']
    db  = get_db()
    venta = db.execute(
        'SELECT * FROM ventas WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()

    if not venta:
        db.close()
        flash('Venta no encontrada.', 'danger')
        return redirect(url_for('ventas.lista'))

    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id', '').strip()
        producto   = request.form.get('producto', '').strip()
        precio     = request.form.get('precio', '').strip()
        tipo_pago  = request.form.get('tipo_pago', 'contado').strip()
        fecha      = request.form.get('fecha', '').strip()
        notas      = request.form.get('notas', '').strip()

        errores = []
        if not cliente_id: errores.append('Debe seleccionar un cliente.')
        if not producto:   errores.append('El producto es obligatorio.')
        if not fecha:      errores.append('La fecha es obligatoria.')
        if not precio:
            errores.append('El precio es obligatorio.')
        else:
            try: precio = float(precio)
            except ValueError: errores.append('El precio debe ser un número válido.')

        if errores:
            for e in errores: flash(e, 'danger')
            clientes = db.execute(
                'SELECT id, nombre FROM clientes WHERE negocio_id = ? ORDER BY nombre', (nid,)
            ).fetchall()
            db.close()
            vd = dict(venta); vd.update(request.form)
            return render_template('ventas/form.html', clientes=clientes, form=vd, accion='Editar')

        db.execute('''
            UPDATE ventas
            SET cliente_id=?, producto=?, precio=?, tipo_pago=?, fecha=?, notas=?
            WHERE id=? AND negocio_id=?
        ''', (cliente_id, producto, precio, tipo_pago, fecha, notas, id, nid))
        db.commit()
        db.close()
        flash('Venta actualizada correctamente.', 'success')
        return redirect(url_for('index'))

    clientes = db.execute(
        'SELECT id, nombre, telefono FROM clientes WHERE negocio_id = ? ORDER BY nombre', (nid,)
    ).fetchall()
    db.close()
    return render_template('ventas/form.html', clientes=clientes,
                           form=dict(venta), accion='Editar', hoy=venta['fecha'])


@ventas_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar(id):
    nid = session['negocio_id']
    db  = get_db()
    venta = db.execute(
        'SELECT producto FROM ventas WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()
    if venta:
        db.execute('DELETE FROM ventas WHERE id = ? AND negocio_id = ?', (id, nid))
        db.commit()
        flash(f'Venta de "{venta["producto"]}" eliminada.', 'success')
    else:
        flash('Venta no encontrada.', 'danger')
    db.close()
    return redirect(url_for('ventas.lista'))

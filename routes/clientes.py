from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db
from routes.auth import login_required

clientes_bp = Blueprint('clientes', __name__)


@clientes_bp.route('/')
@login_required
def lista():
    nid = session['negocio_id']
    db  = get_db()
    busqueda = request.args.get('q', '').strip()

    if busqueda:
        clientes = db.execute('''
            SELECT c.*, COUNT(v.id) as total_compras,
                   COALESCE(SUM(v.precio), 0) as total_gastado
            FROM clientes c
            LEFT JOIN ventas v ON v.cliente_id = c.id AND v.negocio_id = ?
            WHERE c.negocio_id = ?
              AND (c.nombre LIKE ? OR c.cedula LIKE ? OR c.telefono LIKE ?)
            GROUP BY c.id ORDER BY c.nombre
        ''', (nid, nid, f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%')).fetchall()
    else:
        clientes = db.execute('''
            SELECT c.*, COUNT(v.id) as total_compras,
                   COALESCE(SUM(v.precio), 0) as total_gastado
            FROM clientes c
            LEFT JOIN ventas v ON v.cliente_id = c.id AND v.negocio_id = ?
            WHERE c.negocio_id = ?
            GROUP BY c.id ORDER BY c.fecha_creacion DESC
        ''', (nid, nid)).fetchall()

    return render_template('clientes/lista.html', clientes=clientes, busqueda=busqueda)


@clientes_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear():
    nid = session['negocio_id']
    if request.method == 'POST':
        nombre   = request.form.get('nombre', '').strip()
        cedula   = request.form.get('cedula', '').strip()
        telefono = request.form.get('telefono', '').strip()
        direccion= request.form.get('direccion', '').strip()
        ciudad   = request.form.get('ciudad', '').strip()
        notas    = request.form.get('notas', '').strip()

        if not nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
            return render_template('clientes/form.html', accion='Crear', cliente=request.form)

        db = get_db()
        db.execute('''
            INSERT INTO clientes (negocio_id, nombre, cedula, telefono, direccion, ciudad, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nid, nombre, cedula, telefono, direccion, ciudad, notas))
        db.commit()
        flash(f'Cliente "{nombre}" creado exitosamente.', 'success')
        return redirect(url_for('clientes.lista'))

    return render_template('clientes/form.html', accion='Crear', cliente={})


@clientes_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    nid = session['negocio_id']
    db  = get_db()
    cliente = db.execute(
        'SELECT * FROM clientes WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()

    if not cliente:
        db.close()
        flash('Cliente no encontrado.', 'danger')
        return redirect(url_for('clientes.lista'))

    if request.method == 'POST':
        nombre   = request.form.get('nombre', '').strip()
        cedula   = request.form.get('cedula', '').strip()
        telefono = request.form.get('telefono', '').strip()
        direccion= request.form.get('direccion', '').strip()
        ciudad   = request.form.get('ciudad', '').strip()
        notas    = request.form.get('notas', '').strip()

        if not nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
            return render_template('clientes/form.html', accion='Editar', cliente=request.form)

        db.execute('''
            UPDATE clientes
            SET nombre=?, cedula=?, telefono=?, direccion=?, ciudad=?, notas=?
            WHERE id=? AND negocio_id=?
        ''', (nombre, cedula, telefono, direccion, ciudad, notas, id, nid))
        db.commit()
        flash(f'Cliente "{nombre}" actualizado.', 'success')
        return redirect(url_for('clientes.lista'))

    return render_template('clientes/form.html', accion='Editar', cliente=cliente)


@clientes_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar(id):
    nid = session['negocio_id']
    db  = get_db()
    cliente = db.execute(
        'SELECT nombre FROM clientes WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()
    if cliente:
        db.execute('DELETE FROM clientes WHERE id = ? AND negocio_id = ?', (id, nid))
        db.commit()
        flash(f'Cliente "{cliente["nombre"]}" eliminado.', 'success')
    else:
        flash('Cliente no encontrado.', 'danger')
    return redirect(url_for('clientes.lista'))


@clientes_bp.route('/<int:id>/detalle')
@login_required
def detalle(id):
    nid = session['negocio_id']
    db  = get_db()
    cliente = db.execute(
        'SELECT * FROM clientes WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()

    if not cliente:
        db.close()
        flash('Cliente no encontrado.', 'danger')
        return redirect(url_for('clientes.lista'))

    ventas = db.execute('''
        SELECT * FROM ventas
        WHERE cliente_id = ? AND negocio_id = ?
        ORDER BY fecha DESC
    ''', (id, nid)).fetchall()

    total_gastado = sum(v['precio'] for v in ventas)
    return render_template('clientes/detalle.html',
                           cliente=cliente, ventas=ventas,
                           total_gastado=total_gastado)

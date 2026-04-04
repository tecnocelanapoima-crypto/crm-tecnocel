"""
Rutas para gestión de clientes
CRUD completo: Crear, Leer, Actualizar, Eliminar
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from database.db import get_db

clientes_bp = Blueprint('clientes', __name__)


@clientes_bp.route('/')
def lista():
    """Lista todos los clientes con opción de búsqueda"""
    db = get_db()
    busqueda = request.args.get('q', '').strip()

    if busqueda:
        # Buscar por nombre, cédula o teléfono
        clientes = db.execute('''
            SELECT c.*, COUNT(v.id) as total_compras,
                   COALESCE(SUM(v.precio), 0) as total_gastado
            FROM clientes c
            LEFT JOIN ventas v ON v.cliente_id = c.id
            WHERE c.nombre LIKE ? OR c.cedula LIKE ? OR c.telefono LIKE ?
            GROUP BY c.id
            ORDER BY c.nombre
        ''', (f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%')).fetchall()
    else:
        clientes = db.execute('''
            SELECT c.*, COUNT(v.id) as total_compras,
                   COALESCE(SUM(v.precio), 0) as total_gastado
            FROM clientes c
            LEFT JOIN ventas v ON v.cliente_id = c.id
            GROUP BY c.id
            ORDER BY c.fecha_creacion DESC
        ''').fetchall()

    db.close()
    return render_template('clientes/lista.html', clientes=clientes, busqueda=busqueda)


@clientes_bp.route('/crear', methods=['GET', 'POST'])
def crear():
    """Formulario y procesamiento para crear un nuevo cliente"""
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        cedula = request.form.get('cedula', '').strip()
        telefono = request.form.get('telefono', '').strip()
        direccion = request.form.get('direccion', '').strip()
        ciudad = request.form.get('ciudad', '').strip()
        notas = request.form.get('notas', '').strip()

        # Validación básica
        if not nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
            return render_template('clientes/form.html', accion='Crear', cliente=request.form)

        db = get_db()
        db.execute('''
            INSERT INTO clientes (nombre, cedula, telefono, direccion, ciudad, notas)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nombre, cedula, telefono, direccion, ciudad, notas))
        db.commit()
        db.close()

        flash(f'Cliente "{nombre}" creado exitosamente.', 'success')
        return redirect(url_for('clientes.lista'))

    return render_template('clientes/form.html', accion='Crear', cliente={})


@clientes_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
def editar(id):
    """Formulario y procesamiento para editar un cliente existente"""
    db = get_db()
    cliente = db.execute('SELECT * FROM clientes WHERE id = ?', (id,)).fetchone()

    if not cliente:
        db.close()
        flash('Cliente no encontrado.', 'danger')
        return redirect(url_for('clientes.lista'))

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        cedula = request.form.get('cedula', '').strip()
        telefono = request.form.get('telefono', '').strip()
        direccion = request.form.get('direccion', '').strip()
        ciudad = request.form.get('ciudad', '').strip()
        notas = request.form.get('notas', '').strip()

        if not nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
            return render_template('clientes/form.html', accion='Editar', cliente=request.form)

        db.execute('''
            UPDATE clientes
            SET nombre=?, cedula=?, telefono=?, direccion=?, ciudad=?, notas=?
            WHERE id=?
        ''', (nombre, cedula, telefono, direccion, ciudad, notas, id))
        db.commit()
        db.close()

        flash(f'Cliente "{nombre}" actualizado correctamente.', 'success')
        return redirect(url_for('clientes.lista'))

    db.close()
    return render_template('clientes/form.html', accion='Editar', cliente=cliente)


@clientes_bp.route('/<int:id>/eliminar', methods=['POST'])
def eliminar(id):
    """Elimina un cliente y sus ventas asociadas"""
    db = get_db()
    cliente = db.execute('SELECT nombre FROM clientes WHERE id = ?', (id,)).fetchone()

    if cliente:
        db.execute('DELETE FROM clientes WHERE id = ?', (id,))
        db.commit()
        flash(f'Cliente "{cliente["nombre"]}" eliminado.', 'success')
    else:
        flash('Cliente no encontrado.', 'danger')

    db.close()
    return redirect(url_for('clientes.lista'))


@clientes_bp.route('/<int:id>/detalle')
def detalle(id):
    """Muestra el detalle de un cliente con su historial de compras"""
    db = get_db()
    cliente = db.execute('SELECT * FROM clientes WHERE id = ?', (id,)).fetchone()

    if not cliente:
        db.close()
        flash('Cliente no encontrado.', 'danger')
        return redirect(url_for('clientes.lista'))

    ventas = db.execute('''
        SELECT * FROM ventas
        WHERE cliente_id = ?
        ORDER BY fecha DESC
    ''', (id,)).fetchall()

    total_gastado = sum(v['precio'] for v in ventas)
    db.close()

    return render_template('clientes/detalle.html',
                           cliente=cliente,
                           ventas=ventas,
                           total_gastado=total_gastado)

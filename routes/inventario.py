"""
Inventario — gestión de productos y stock.
"""

import os
import uuid
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from werkzeug.utils import secure_filename
from database.db import get_db
from routes.auth import login_required

logger = logging.getLogger(__name__)

inventario_bp = Blueprint('inventario', __name__)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_FILE_SIZE_MB = 5


def allowed_file(filename):
    """Verifica que la extensión del archivo sea permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _guardar_foto(file):
    """Guarda una foto de producto y retorna el nombre del archivo, o None si falla."""
    if not file or file.filename == '' or not allowed_file(file.filename):
        return None
    try:
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'productos')
        os.makedirs(upload_folder, exist_ok=True)
        file.save(os.path.join(upload_folder, filename))
        return filename
    except Exception as e:
        logger.error(f"Error al guardar foto de producto: {e}")
        return None


def _eliminar_foto(filename):
    """Elimina un archivo de foto del servidor si existe."""
    if not filename:
        return
    try:
        ruta = os.path.join(current_app.root_path, 'static', 'uploads', 'productos', filename)
        if os.path.exists(ruta):
            os.remove(ruta)
    except Exception as e:
        logger.warning(f"No se pudo eliminar la foto '{filename}': {e}")


@inventario_bp.route('/')
@login_required
def lista():
    nid = session['negocio_id']
    db  = get_db()
    busqueda = request.args.get('q', '').strip()

    if busqueda:
        productos = db.execute('''
            SELECT * FROM productos
            WHERE negocio_id = ? AND (nombre LIKE ? OR marca LIKE ? OR categoria LIKE ?)
            ORDER BY nombre
        ''', (nid, f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%')).fetchall()
    else:
        productos = db.execute(
            'SELECT * FROM productos WHERE negocio_id = ? ORDER BY fecha_creacion DESC', (nid,)
        ).fetchall()

    # Estadísticas del inventario
    stats = db.execute('''
        SELECT
            COUNT(*) AS total_productos,
            COALESCE(SUM(stock), 0) AS total_unidades,
            COALESCE(SUM(precio * stock), 0) AS valor_total,
            SUM(CASE WHEN stock = 0 THEN 1 ELSE 0 END) AS sin_stock,
            SUM(CASE WHEN stock > 0 AND stock < 3 THEN 1 ELSE 0 END) AS stock_bajo
        FROM productos WHERE negocio_id = ?
    ''', (nid,)).fetchone()

    db.close()
    return render_template('inventario/lista.html',
                           productos=productos,
                           busqueda=busqueda,
                           stats=stats)


@inventario_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear():
    nid = session['negocio_id']
    if request.method == 'POST':
        nombre      = request.form.get('nombre', '').strip()
        marca       = request.form.get('marca', '').strip()
        categoria   = request.form.get('categoria', '').strip()
        descripcion = request.form.get('descripcion', '').strip()

        errores = []
        if not nombre:
            errores.append('El nombre del producto es obligatorio.')

        try:
            precio = float(request.form.get('precio', 0))
            if precio < 0:
                errores.append('El precio no puede ser negativo.')
        except (ValueError, TypeError):
            errores.append('El precio debe ser un número válido.')
            precio = 0

        try:
            stock = int(request.form.get('stock', 0))
            if stock < 0:
                errores.append('El stock no puede ser negativo.')
        except (ValueError, TypeError):
            errores.append('El stock debe ser un número entero.')
            stock = 0

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('inventario/form.html', accion='Crear', producto=request.form)

        foto_filename = _guardar_foto(request.files.get('foto'))

        db = get_db()
        db.execute('''
            INSERT INTO productos (negocio_id, nombre, marca, categoria, precio, stock, descripcion, foto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nid, nombre, marca, categoria, precio, stock, descripcion, foto_filename))
        db.commit()
        db.close()
        flash(f'Producto "{nombre}" creado exitosamente.', 'success')
        return redirect(url_for('inventario.lista'))

    return render_template('inventario/form.html', accion='Crear', producto={})


@inventario_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def editar(id):
    nid = session['negocio_id']
    db  = get_db()
    producto = db.execute(
        'SELECT * FROM productos WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()

    if not producto:
        db.close()
        flash('Producto no encontrado.', 'danger')
        return redirect(url_for('inventario.lista'))

    if request.method == 'POST':
        nombre       = request.form.get('nombre', '').strip()
        marca        = request.form.get('marca', '').strip()
        categoria    = request.form.get('categoria', '').strip()
        descripcion  = request.form.get('descripcion', '').strip()
        eliminar_foto = request.form.get('eliminar_foto') == 'true'

        errores = []
        if not nombre:
            errores.append('El nombre del producto es obligatorio.')

        try:
            precio = float(request.form.get('precio', 0))
            if precio < 0:
                errores.append('El precio no puede ser negativo.')
        except (ValueError, TypeError):
            errores.append('El precio debe ser un número válido.')
            precio = 0

        try:
            stock = int(request.form.get('stock', 0))
            if stock < 0:
                errores.append('El stock no puede ser negativo.')
        except (ValueError, TypeError):
            errores.append('El stock debe ser un número entero.')
            stock = 0

        if errores:
            for e in errores:
                flash(e, 'danger')
            db.close()
            return render_template('inventario/form.html', accion='Editar', producto=request.form)

        foto_filename = producto['foto']

        if eliminar_foto and foto_filename:
            _eliminar_foto(foto_filename)
            foto_filename = None

        nueva_foto = _guardar_foto(request.files.get('foto'))
        if nueva_foto:
            if foto_filename:
                _eliminar_foto(foto_filename)
            foto_filename = nueva_foto

        db.execute('''
            UPDATE productos
            SET nombre=?, marca=?, categoria=?, precio=?, stock=?, descripcion=?, foto=?
            WHERE id=? AND negocio_id=?
        ''', (nombre, marca, categoria, precio, stock, descripcion, foto_filename, id, nid))
        db.commit()
        db.close()
        flash(f'Producto "{nombre}" actualizado correctamente.', 'success')
        return redirect(url_for('inventario.lista'))

    db.close()
    return render_template('inventario/form.html', accion='Editar', producto=producto)


@inventario_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar(id):
    nid = session['negocio_id']
    db  = get_db()
    producto = db.execute(
        'SELECT nombre, foto FROM productos WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()

    if producto:
        _eliminar_foto(producto['foto'])
        db.execute('DELETE FROM productos WHERE id = ? AND negocio_id = ?', (id, nid))
        db.commit()
        flash(f'Producto "{producto["nombre"]}" eliminado.', 'success')
    else:
        flash('Producto no encontrado.', 'danger')

    db.close()
    return redirect(url_for('inventario.lista'))


@inventario_bp.route('/<int:id>/ajustar-stock', methods=['POST'])
@login_required
def ajustar_stock(id):
    """Permite ajustar rápidamente el stock de un producto (entrada/salida)."""
    nid = session['negocio_id']
    db  = get_db()
    producto = db.execute(
        'SELECT id, nombre, stock FROM productos WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()

    if not producto:
        db.close()
        flash('Producto no encontrado.', 'danger')
        return redirect(url_for('inventario.lista'))

    try:
        cantidad  = int(request.form.get('cantidad', 0))
        operacion = request.form.get('operacion', 'entrada')  # 'entrada' o 'salida'

        nuevo_stock = producto['stock'] + cantidad if operacion == 'entrada' else producto['stock'] - cantidad
        if nuevo_stock < 0:
            flash('El stock no puede quedar negativo.', 'warning')
            db.close()
            return redirect(url_for('inventario.lista'))

        db.execute('UPDATE productos SET stock = ? WHERE id = ? AND negocio_id = ?',
                   (nuevo_stock, id, nid))
        db.commit()
        accion_txt = 'agregadas' if operacion == 'entrada' else 'descontadas'
        flash(f'{cantidad} unidades {accion_txt} de "{producto["nombre"]}". Stock actual: {nuevo_stock}.', 'success')
    except (ValueError, TypeError):
        flash('Cantidad inválida.', 'danger')

    db.close()
    return redirect(url_for('inventario.lista'))

import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from werkzeug.utils import secure_filename
from database.db import get_db
from routes.auth import login_required

inventario_bp = Blueprint('inventario', __name__)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
    db.close()
    return render_template('inventario/lista.html', productos=productos, busqueda=busqueda)


@inventario_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear():
    nid = session['negocio_id']
    if request.method == 'POST':
        nombre      = request.form.get('nombre', '').strip()
        marca       = request.form.get('marca', '').strip()
        categoria   = request.form.get('categoria', '').strip()
        precio      = request.form.get('precio', 0)
        stock       = request.form.get('stock', 1)
        descripcion = request.form.get('descripcion', '').strip()

        if not nombre or not precio:
            flash('Nombre y precio son obligatorios', 'danger')
            return render_template('inventario/form.html', accion='Crear', producto=request.form)

        foto_filename = None
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{ext}"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'productos')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                foto_filename = filename

        db = get_db()
        db.execute('''
            INSERT INTO productos (negocio_id, nombre, marca, categoria, precio, stock, descripcion, foto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nid, nombre, marca, categoria, float(precio), int(stock), descripcion, foto_filename))
        db.commit()
        db.close()
        flash('Producto creado exitosamente.', 'success')
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
        precio       = request.form.get('precio', 0)
        stock        = request.form.get('stock', 1)
        descripcion  = request.form.get('descripcion', '').strip()
        eliminar_foto= request.form.get('eliminar_foto') == 'true'
        foto_filename= producto['foto']

        if eliminar_foto and foto_filename:
            old = os.path.join(current_app.root_path, 'static', 'uploads', 'productos', foto_filename)
            if os.path.exists(old): os.remove(old)
            foto_filename = None

        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '' and allowed_file(file.filename):
                if foto_filename and not eliminar_foto:
                    old = os.path.join(current_app.root_path, 'static', 'uploads', 'productos', foto_filename)
                    if os.path.exists(old): os.remove(old)
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4().hex}.{ext}"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'productos')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                foto_filename = filename

        db.execute('''
            UPDATE productos
            SET nombre=?, marca=?, categoria=?, precio=?, stock=?, descripcion=?, foto=?
            WHERE id=? AND negocio_id=?
        ''', (nombre, marca, categoria, float(precio), int(stock), descripcion, foto_filename, id, nid))
        db.commit()
        db.close()
        flash('Producto actualizado correctamente.', 'success')
        return redirect(url_for('inventario.lista'))

    db.close()
    return render_template('inventario/form.html', accion='Editar', producto=producto)


@inventario_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar(id):
    nid = session['negocio_id']
    db  = get_db()
    producto = db.execute(
        'SELECT foto FROM productos WHERE id = ? AND negocio_id = ?', (id, nid)
    ).fetchone()
    if producto:
        if producto['foto']:
            old = os.path.join(current_app.root_path, 'static', 'uploads', 'productos', producto['foto'])
            if os.path.exists(old): os.remove(old)
        db.execute('DELETE FROM productos WHERE id = ? AND negocio_id = ?', (id, nid))
        db.commit()
        flash('Producto eliminado.', 'success')
    db.close()
    return redirect(url_for('inventario.lista'))

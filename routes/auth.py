"""
Autenticación — registro, login y logout
"""

import hashlib
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import get_db

auth_bp = Blueprint('auth', __name__)


def hash_password(password):
    """Hash SHA-256 simple. En producción usar bcrypt."""
    return hashlib.sha256(password.encode()).hexdigest()


def login_required(f):
    """Decorador: redirige al login si no hay sesión activa."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('negocio_id'):
            flash('Debes iniciar sesión para continuar.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if session.get('negocio_id'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        nombre_negocio = request.form.get('nombre_negocio', '').strip()
        email          = request.form.get('email', '').strip().lower()
        password       = request.form.get('password', '')
        confirmar      = request.form.get('confirmar', '')
        telefono       = request.form.get('telefono', '').strip()
        ciudad         = request.form.get('ciudad', '').strip()

        errores = []
        if not nombre_negocio: errores.append('El nombre del negocio es obligatorio.')
        if not email:          errores.append('El correo es obligatorio.')
        if len(password) < 6:  errores.append('La contraseña debe tener al menos 6 caracteres.')
        if password != confirmar: errores.append('Las contraseñas no coinciden.')

        if errores:
            for e in errores:
                flash(e, 'danger')
            return render_template('auth/registro.html', form=request.form)

        db = get_db()
        existente = db.execute('SELECT id FROM negocios WHERE email = ?', (email,)).fetchone()
        if existente:
            db.close()
            flash('Ese correo ya está registrado. Inicia sesión.', 'danger')
            return render_template('auth/registro.html', form=request.form)

        db.execute('''
            INSERT INTO negocios (nombre_negocio, email, password_hash, telefono, ciudad)
            VALUES (?, ?, ?, ?, ?)
        ''', (nombre_negocio, email, hash_password(password), telefono, ciudad))
        db.commit()

        negocio = db.execute('SELECT id FROM negocios WHERE email = ?', (email,)).fetchone()
        db.close()

        session['negocio_id']     = negocio['id']
        session['negocio_nombre'] = nombre_negocio
        session['negocio_email']  = email

        flash(f'¡Bienvenido a Tecnocel CRM, {nombre_negocio}! 🎉', 'success')
        return redirect(url_for('index'))

    return render_template('auth/registro.html', form={})


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('negocio_id'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        db = get_db()
        negocio = db.execute(
            'SELECT * FROM negocios WHERE email = ? AND activo = 1',
            (email,)
        ).fetchone()
        db.close()

        if not negocio or negocio['password_hash'] != hash_password(password):
            flash('Correo o contraseña incorrectos.', 'danger')
            return render_template('auth/login.html', email=email)

        session['negocio_id']     = negocio['id']
        session['negocio_nombre'] = negocio['nombre_negocio']
        session['negocio_email']  = negocio['email']

        flash(f'¡Bienvenido, {negocio["nombre_negocio"]}!', 'success')
        return redirect(url_for('index'))

    return render_template('auth/login.html', email='')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))

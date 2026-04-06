"""
Tecnocel CRM — Versión SaaS
Sistema multi-tenant: cada negocio ve solo sus datos.
"""

import os
import logging
import secrets
from flask import Flask, render_template, redirect, url_for, session, g, flash
from database.db import init_db, get_db

# ── Configuración de logging ───────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Clave secreta segura ───────────────────────────────────
# En producción, establece la variable de entorno SECRET_KEY con un valor seguro.
# Ejemplo: export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# ── Inicializar base de datos ──────────────────────────────
with app.app_context():
    init_db()


# ── Manejo automático de conexión a la BD ─────────────────
def get_db_conn():
    """Retorna la conexión a la BD del contexto actual de la petición."""
    if 'db' not in g:
        g.db = get_db()
    return g.db


@app.teardown_appcontext
def close_db(error):
    """Cierra la conexión a la BD automáticamente al finalizar cada petición."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


# ── Blueprints ─────────────────────────────────────────────
from routes.auth       import auth_bp
from routes.clientes   import clientes_bp
from routes.ventas     import ventas_bp
from routes.facturas   import facturas_bp
from routes.whatsapp   import whatsapp_bp
from routes.inventario import inventario_bp
from routes.finanzas   import finanzas_bp

app.register_blueprint(auth_bp)
app.register_blueprint(clientes_bp,   url_prefix='/clientes')
app.register_blueprint(ventas_bp,     url_prefix='/ventas')
app.register_blueprint(facturas_bp,   url_prefix='/facturas')
app.register_blueprint(whatsapp_bp,   url_prefix='/whatsapp')
app.register_blueprint(inventario_bp, url_prefix='/inventario')
app.register_blueprint(finanzas_bp,   url_prefix='/finanzas')


# ── Inyección de datos del negocio en todos los templates ──
@app.context_processor
def inject_negocio():
    """Disponible en todos los templates."""
    return {
        'negocio_nombre': session.get('negocio_nombre', ''),
        'negocio_email':  session.get('negocio_email',  ''),
        'negocio_id':     session.get('negocio_id'),
    }


# ── Manejadores de errores globales ───────────────────────
@app.errorhandler(500)
def internal_error(error):
    logger.error('Error 500: %s', error)
    return render_template('errors/500.html'), 500


@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404


# ── Ruta principal: Dashboard ──────────────────────────────
@app.route('/')
def index():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))

    nid = session['negocio_id']
    db  = get_db()

    total_clientes = db.execute(
        'SELECT COUNT(*) FROM clientes WHERE negocio_id = ?', (nid,)
    ).fetchone()[0]

    total_ventas = db.execute(
        'SELECT COUNT(*) FROM ventas WHERE negocio_id = ?', (nid,)
    ).fetchone()[0]

    total_ingresos = db.execute(
        'SELECT COALESCE(SUM(precio), 0) FROM ventas WHERE negocio_id = ?', (nid,)
    ).fetchone()[0]

    total_egresos = db.execute(
        'SELECT COALESCE(SUM(monto), 0) FROM egresos WHERE negocio_id = ?', (nid,)
    ).fetchone()[0]

    balance_neto = total_ingresos - total_egresos

    ventas_recientes = db.execute('''
        SELECT v.id, v.producto, v.precio, v.tipo_pago, v.fecha,
               c.nombre AS cliente_nombre
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.negocio_id = ?
        ORDER BY v.fecha_creacion DESC
        LIMIT 5
    ''', (nid,)).fetchall()

    todas_ventas = db.execute('''
        SELECT v.id, v.producto, v.precio, v.tipo_pago, v.fecha,
               c.nombre AS cliente_nombre
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.negocio_id = ?
        ORDER BY v.fecha_creacion DESC
    ''', (nid,)).fetchall()

    clientes_recientes = db.execute('''
        SELECT id, nombre, telefono, ciudad
        FROM clientes
        WHERE negocio_id = ?
        ORDER BY fecha_creacion DESC
        LIMIT 5
    ''', (nid,)).fetchall()

    # Productos con stock bajo (menos de 3 unidades)
    stock_bajo = db.execute('''
        SELECT nombre, stock, categoria
        FROM productos
        WHERE negocio_id = ? AND stock < 3
        ORDER BY stock ASC
        LIMIT 5
    ''', (nid,)).fetchall()

    db.close()

    return render_template(
        'index.html',
        total_clientes=total_clientes,
        total_ventas=total_ventas,
        total_ingresos=total_ingresos,
        total_egresos=total_egresos,
        balance_neto=balance_neto,
        ventas_recientes=ventas_recientes,
        clientes_recientes=clientes_recientes,
        todas_ventas=todas_ventas,
        stock_bajo=stock_bajo,
    )


# ── Ruta de reset para pruebas (TEMPORAL) ─────────────────
@app.route('/reset-datos', methods=['POST'])
def reset_datos():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))
    nid = session['negocio_id']
    db = get_db()
    db.execute('DELETE FROM ventas WHERE negocio_id = ?', (nid,))
    db.execute('DELETE FROM clientes WHERE negocio_id = ?', (nid,))
    db.execute('DELETE FROM productos WHERE negocio_id = ?', (nid,))
    db.execute('DELETE FROM egresos WHERE negocio_id = ?', (nid,))
    db.commit()
    db.close()
    flash('Datos reseteados correctamente.', 'success')
    return redirect(url_for('index'))


if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("  Tecnocel CRM SaaS iniciado")
    print("  Accede en: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)

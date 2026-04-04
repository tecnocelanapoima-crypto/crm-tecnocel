"""
Tecnocel CRM — Versión SaaS
Sistema multi-tenant: cada negocio ve solo sus datos
"""

import os
from flask import Flask, render_template, redirect, url_for, session
from database.db import init_db, get_db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tecnocel-saas-secret-2024-cambiar-en-produccion')

with app.app_context():
    init_db()

# ── Blueprints ─────────────────────────────────────────
from routes.auth      import auth_bp
from routes.clientes  import clientes_bp
from routes.ventas    import ventas_bp
from routes.facturas  import facturas_bp
from routes.whatsapp  import whatsapp_bp
from routes.inventario import inventario_bp
from routes.finanzas  import finanzas_bp

app.register_blueprint(auth_bp)
app.register_blueprint(clientes_bp,  url_prefix='/clientes')
app.register_blueprint(ventas_bp,    url_prefix='/ventas')
app.register_blueprint(facturas_bp,  url_prefix='/facturas')
app.register_blueprint(whatsapp_bp,  url_prefix='/whatsapp')
app.register_blueprint(inventario_bp, url_prefix='/inventario')
app.register_blueprint(finanzas_bp,  url_prefix='/finanzas')


@app.context_processor
def inject_negocio():
    """Disponible en todos los templates."""
    return {
        'negocio_nombre': session.get('negocio_nombre', ''),
        'negocio_email':  session.get('negocio_email',  ''),
        'negocio_id':     session.get('negocio_id'),
    }


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

    ventas_recientes = db.execute('''
        SELECT v.id, v.producto, v.precio, v.tipo_pago, v.fecha,
               c.nombre as cliente_nombre
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.negocio_id = ?
        ORDER BY v.fecha_creacion DESC
        LIMIT 5
    ''', (nid,)).fetchall()

    todas_ventas = db.execute('''
        SELECT v.id, v.producto, v.precio, v.tipo_pago, v.fecha,
               c.nombre as cliente_nombre
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

    db.close()

    return render_template(
        'index.html',
        total_clientes=total_clientes,
        total_ventas=total_ventas,
        total_ingresos=total_ingresos,
        ventas_recientes=ventas_recientes,
        clientes_recientes=clientes_recientes,
        todas_ventas=todas_ventas
    )


if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print("  Tecnocel CRM SaaS iniciado")
    print("  Accede en: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)

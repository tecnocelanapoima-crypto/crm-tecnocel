"""
Tecnocel CRM - Aplicación principal
Sistema de gestión de clientes y ventas para Tecnocel
"""

from flask import Flask, render_template, redirect, url_for
from database.db import init_db, get_db

# Crear la aplicación Flask
app = Flask(__name__)
app.secret_key = 'tecnocel-crm-secret-2024'

# Registrar blueprints (módulos de rutas)
from routes.clientes import clientes_bp
from routes.ventas import ventas_bp
from routes.facturas import facturas_bp
from routes.whatsapp import whatsapp_bp
from routes.inventario import inventario_bp
from routes.finanzas import finanzas_bp

app.register_blueprint(clientes_bp, url_prefix='/clientes')
app.register_blueprint(ventas_bp, url_prefix='/ventas')
app.register_blueprint(facturas_bp, url_prefix='/facturas')
app.register_blueprint(whatsapp_bp, url_prefix='/whatsapp')
app.register_blueprint(inventario_bp, url_prefix='/inventario')
app.register_blueprint(finanzas_bp, url_prefix='/finanzas')


@app.route('/')
def index():
    """Panel principal - muestra estadísticas generales"""
    db = get_db()

    # Estadísticas para el dashboard
    total_clientes = db.execute('SELECT COUNT(*) FROM clientes').fetchone()[0]
    total_ventas = db.execute('SELECT COUNT(v.id) FROM ventas v JOIN clientes c ON v.cliente_id = c.id').fetchone()[0]
    total_ingresos = db.execute('SELECT SUM(v.precio) FROM ventas v JOIN clientes c ON v.cliente_id = c.id').fetchone()[0] or 0

    # Últimas 5 ventas
    ventas_recientes = db.execute('''
        SELECT v.id, v.producto, v.precio, v.tipo_pago, v.fecha,
               c.nombre as cliente_nombre
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        ORDER BY v.fecha_creacion DESC
        LIMIT 5
    ''').fetchall()

    # Todas las ventas para desglose en Dashboard
    todas_ventas = db.execute('''
        SELECT v.id, v.producto, v.precio, v.tipo_pago, v.fecha,
               c.nombre as cliente_nombre
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        ORDER BY v.fecha_creacion DESC
    ''').fetchall()

    # Últimos 5 clientes registrados
    clientes_recientes = db.execute('''
        SELECT id, nombre, telefono, ciudad
        FROM clientes
        ORDER BY fecha_creacion DESC
        LIMIT 5
    ''').fetchall()

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
    # Inicializar la base de datos al arrancar
    init_db()
    print("=" * 50)
    print("  Tecnocel CRM iniciado correctamente")
    print("  Accede en: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)

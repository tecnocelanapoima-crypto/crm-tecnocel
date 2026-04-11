"""
Tecnocel CRM — Versión SaaS
Sistema multi-tenant: cada negocio ve solo sus datos
"""

import json
import os
import socket
from flask import Flask, render_template, redirect, url_for, session, request, flash, jsonify, send_from_directory, make_response
from database.db import init_db, get_db, close_db
from datetime import date


def _get_local_ip() -> str:
    """Devuelve la IP local de red (LAN), no 127.0.0.1."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', '7e9c0c0e-c760-4b6e-8c1b-2dad20c8fc35-tecnocel-prod')
app.teardown_appcontext(close_db)

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
from routes.ordenes   import ordenes_bp
from routes.admin          import admin_bp
from routes.configuracion  import configuracion_bp

app.register_blueprint(auth_bp)
app.register_blueprint(clientes_bp,  url_prefix='/clientes')
app.register_blueprint(ventas_bp,    url_prefix='/ventas')
app.register_blueprint(facturas_bp,  url_prefix='/facturas')
app.register_blueprint(whatsapp_bp,  url_prefix='/whatsapp')
app.register_blueprint(inventario_bp, url_prefix='/inventario')
app.register_blueprint(finanzas_bp,  url_prefix='/finanzas')
app.register_blueprint(ordenes_bp,  url_prefix='/ordenes')
app.register_blueprint(admin_bp,         url_prefix='/admin')
app.register_blueprint(configuracion_bp, url_prefix='/configuracion')


# ── Filtro de moneda Jinja2 ──────────────────────────────────────────────
@app.template_filter('moneda')
def formato_moneda(valor):
    """Formatea un número como moneda colombiana: $ 150.000"""
    if valor is None:
        return '$ 0'
    return '$ ' + f'{int(valor):,}'.replace(',', '.')


@app.context_processor
def inject_negocio():
    """Inyecta datos del negocio y config de factura en todos los templates."""
    from routes.configuracion import DEFAULT_FACTURA_CONFIG
    nid = session.get('negocio_id')
    logo_base64      = None
    negocio_slogan   = ''
    negocio_telefono = ''
    factura_config   = DEFAULT_FACTURA_CONFIG.copy()
    if nid:
        try:
            db  = get_db()
            row = db.execute(
                'SELECT logo_base64, slogan, telefono, factura_config FROM negocios WHERE id = ?',
                (nid,)
            ).fetchone()
            if row:
                logo_base64      = row['logo_base64']
                negocio_slogan   = row['slogan'] or ''
                negocio_telefono = row['telefono'] or ''
                if row['factura_config']:
                    try:
                        factura_config.update(json.loads(row['factura_config']))
                    except Exception:
                        pass
        except Exception:
            pass
    return {
        'negocio_nombre':   session.get('negocio_nombre', ''),
        'negocio_email':    session.get('negocio_email',  ''),
        'negocio_id':       nid,
        'negocio_logo':     logo_base64,
        'negocio_slogan':   negocio_slogan,
        'negocio_telefono': negocio_telefono,
        'factura_config':   factura_config,
    }


@app.route('/')
def index():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))

    nid = session['negocio_id']
    db  = get_db()
    hoy = date.today().isoformat()

    # ── Tarjetas de resumen — TOTALES ACUMULADOS ───────────────────────────────

    # Total equipos recibidos (todas las órdenes)
    try:
        equipos_hoy = db.execute(
            "SELECT COUNT(*) FROM ordenes WHERE negocio_id = ?", (nid,)
        ).fetchone()[0]
    except Exception: equipos_hoy = 0

    # Equipos listos para entregar
    try:
        equipos_listos = db.execute(
            "SELECT COUNT(*) FROM ordenes WHERE negocio_id = ? AND estado = 'listo'", (nid,)
        ).fetchone()[0]
    except Exception: equipos_listos = 0

    # Total ventas de accesorios/productos — excluye ventas de tipo servicio
    ventas_hoy = db.execute(
        "SELECT COUNT(*) FROM ventas WHERE negocio_id = ? AND producto NOT LIKE 'Servicio: %'", (nid,)
    ).fetchone()[0]

    # Total ingresos por ventas de accesorios/productos — excluye ventas de tipo servicio
    ingresos_ventas_hoy = db.execute(
        "SELECT COALESCE(SUM(precio), 0) FROM ventas WHERE negocio_id = ? AND producto NOT LIKE 'Servicio: %'", (nid,)
    ).fetchone()[0]

    # Total abonos recibidos en todas las órdenes (solo informativo)
    try:
        ingresos_abonos_hoy = db.execute(
            "SELECT COALESCE(SUM(abono), 0) FROM ordenes WHERE negocio_id = ?", (nid,)
        ).fetchone()[0]
    except Exception: ingresos_abonos_hoy = 0

    # Total cobrado en órdenes entregadas (costo_final completo)
    try:
        ingresos_ordenes_hoy = db.execute(
            "SELECT COALESCE(SUM(costo_final), 0) FROM ordenes WHERE negocio_id = ? AND estado = 'entregado'", (nid,)
        ).fetchone()[0]
    except Exception: ingresos_ordenes_hoy = 0

    # Total recaudado = ventas reales de accesorios + entregas de servicio efectivas (sin duplicados)
    recaudado_hoy = ingresos_ventas_hoy + ingresos_ordenes_hoy

    # ── Datos detallados (SaaS safe) ────────────────────────────────────────

    # Órdenes activas (no entregadas)
    try:
        ordenes_activas = db.execute('''
            SELECT o.id, o.numero_orden, o.marca_modelo, o.problema, o.estado, o.fecha_creacion, o.abono,
                   c.nombre AS cliente_nombre
            FROM ordenes o
            JOIN clientes c ON o.cliente_id = c.id
            WHERE o.negocio_id = ? AND o.estado != 'entregado'
            ORDER BY o.fecha_creacion DESC
            LIMIT 10
        ''', (nid,)).fetchall()

        # Detalle para la alerta de WhatsApp
        equipos_listos_detalle = db.execute('''
            SELECT o.numero_orden, o.marca_modelo, c.nombre AS cliente_nombre, c.telefono
            FROM ordenes o
            JOIN clientes c ON o.cliente_id = c.id
            WHERE o.negocio_id = ? AND o.estado = 'listo'
            ORDER BY o.fecha_creacion ASC
        ''', (nid,)).fetchall()
    except Exception:
        ordenes_activas = []
        equipos_listos_detalle = []

    # Ventas de accesorios recientes — excluye ventas de tipo servicio
    ventas_accesorios_recientes = db.execute('''
        SELECT v.id, v.producto, v.precio, v.tipo_pago, v.fecha_creacion,
               c.nombre AS cliente_nombre
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        WHERE v.negocio_id = ?
          AND v.producto NOT LIKE 'Servicio: %'
        ORDER BY v.fecha_creacion DESC
        LIMIT 5
    ''', (nid,)).fetchall()

    # Entregas recientes — tomadas directamente de órdenes entregadas (fuente única, sin duplicados)
    try:
        entregas_recientes = db.execute('''
            SELECT o.id,
                   (o.marca_modelo || ' - ' || o.problema) as producto,
                   o.costo_final as precio,
                   'contado' as tipo_pago,
                   o.fecha_entregado as fecha_creacion,
                   c.nombre AS cliente_nombre
            FROM ordenes o
            JOIN clientes c ON o.cliente_id = c.id
            WHERE o.negocio_id = ? AND o.estado = 'entregado'
            ORDER BY o.fecha_entregado DESC
            LIMIT 5
        ''', (nid,)).fetchall()
    except Exception:
        entregas_recientes = []

    return render_template(
        'index.html',
        equipos_hoy              = equipos_hoy,
        equipos_listos           = equipos_listos,
        equipos_listos_detalle   = equipos_listos_detalle,
        ventas_hoy               = ventas_hoy,
        recaudado_hoy            = recaudado_hoy,
        ingresos_ventas_hoy      = ingresos_ventas_hoy,
        ingresos_abonos_hoy      = ingresos_abonos_hoy,
        ingresos_ordenes_hoy     = ingresos_ordenes_hoy,
        ordenes_activas          = ordenes_activas,
        ventas_accesorios        = ventas_accesorios_recientes,
        entregas_recientes       = entregas_recientes,
        total_accesorios_hoy     = ingresos_ventas_hoy,
        total_entregas_hoy       = ingresos_ordenes_hoy,
        hoy                      = hoy
    )


@app.route('/completos')
def completos():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))

    nid = session['negocio_id']
    db  = get_db()

    # 1. Ventas de accesorios/productos — excluye TODOS los duplicados de servicios
    ventas = db.execute('''
        SELECT v.id as id, 'Venta' as tipo, v.producto as concepto, v.precio as valor,
               v.fecha as fecha_fin, c.nombre as cliente_nombre, 'success' as color
        FROM ventas v JOIN clientes c ON v.cliente_id = c.id
        WHERE v.negocio_id = ?
          AND v.producto NOT LIKE 'Servicio: %'
          AND (v.notas IS NULL OR v.notas NOT LIKE 'Orden %')
    ''', (nid,)).fetchall()

    # 2. Reparaciones entregadas — concepto unificado: marca_modelo + problema
    entregas = db.execute('''
        SELECT o.id as id,
               'Reparación' as tipo,
               (o.marca_modelo || ' — ' || o.problema) as concepto,
               o.costo_final as valor,
               o.fecha_entregado as fecha_fin,
               c.nombre as cliente_nombre,
               'primary' as color
        FROM ordenes o JOIN clientes c ON o.cliente_id = c.id
        WHERE o.negocio_id = ? AND o.estado = 'entregado'
    ''', (nid,)).fetchall()

    # Combinar y ordenar (más reciente primero)
    todo = list(ventas) + list(entregas)
    todo.sort(key=lambda x: x['fecha_fin'] if x['fecha_fin'] else '', reverse=True)

    total_recaudado = sum(item['valor'] for item in todo if item['valor'])

    return render_template('completos.html', lista=todo, total=total_recaudado)


# ── API: Stats del Dashboard (AJAX) ─────────────────────────────────────────
@app.route('/dashboard/stats')
def dashboard_stats():
    """Devuelve los contadores del Dashboard en JSON para refresco asíncrono."""
    if not session.get('negocio_id'):
        return jsonify({'error': 'no_auth'}), 401
    nid = session['negocio_id']
    db  = get_db()
    try:
        equipos_hoy    = db.execute("SELECT COUNT(*) FROM ordenes WHERE negocio_id = ?", (nid,)).fetchone()[0]
        equipos_listos = db.execute("SELECT COUNT(*) FROM ordenes WHERE negocio_id = ? AND estado = 'listo'", (nid,)).fetchone()[0]
        ventas_hoy     = db.execute("SELECT COUNT(*) FROM ventas WHERE negocio_id = ? AND producto NOT LIKE 'Servicio: %'", (nid,)).fetchone()[0]
        ingresos_ventas  = db.execute("SELECT COALESCE(SUM(precio), 0) FROM ventas WHERE negocio_id = ? AND producto NOT LIKE 'Servicio: %'", (nid,)).fetchone()[0]
        ingresos_abonos  = db.execute("SELECT COALESCE(SUM(abono), 0) FROM ordenes WHERE negocio_id = ?", (nid,)).fetchone()[0]
        ingresos_ordenes = db.execute("SELECT COALESCE(SUM(costo_final), 0) FROM ordenes WHERE negocio_id = ? AND estado = 'entregado'", (nid,)).fetchone()[0]
        # Total recaudado = ventas reales + entregas efectivas (sin duplicados)
        recaudado = ingresos_ventas + ingresos_ordenes
        return jsonify({
            'equipos_hoy':     equipos_hoy,
            'equipos_listos':  equipos_listos,
            'ventas_hoy':      ventas_hoy,
            'recaudado':       f'$ {int(recaudado):,}'.replace(',', '.'),
            'ingresos_ventas': f'$ {int(ingresos_ventas):,}'.replace(',', '.'),
            'ingresos_abonos': f'$ {int(ingresos_abonos):,}'.replace(',', '.'),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── API: Buscar cliente por teléfono (AJAX autocompletado) ───────────────────
@app.route('/api/cliente-por-telefono')
def cliente_por_telefono():
    """Busca un cliente por teléfono para autocompletar el nombre."""
    if not session.get('negocio_id'):
        return jsonify({'error': 'no_auth'}), 401
    nid = session['negocio_id']
    telefono = request.args.get('telefono', '').strip()
    if not telefono or len(telefono) < 7:
        return jsonify({'found': False})
    db = get_db()
    cliente = db.execute(
        "SELECT nombre FROM clientes WHERE negocio_id = ? AND telefono LIKE ?",
        (nid, f'%{telefono}%')
    ).fetchone()
    if cliente:
        return jsonify({'found': True, 'nombre': cliente['nombre']})
    return jsonify({'found': False})


@app.route('/abrir-carpeta-facturas')
def abrir_carpeta_facturas():
    import subprocess, platform, os
    from datetime import datetime
    ahora = datetime.now()
    meses_es = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    carpeta_hoy = os.path.abspath(os.path.join(
        'facturas',
        ahora.strftime('%Y'),
        meses_es[ahora.month],
        ahora.strftime('%d')
    ))
    carpeta = carpeta_hoy if os.path.exists(carpeta_hoy) else os.path.abspath('facturas')
    os.makedirs(carpeta, exist_ok=True)
    if platform.system() == 'Windows':
        subprocess.Popen(['explorer', carpeta])
    return '', 204


@app.route('/completos/eliminar', methods=['POST'])
def eliminar_completo():
    if not session.get('negocio_id'):
        return redirect(url_for('auth.login'))

    nid     = session['negocio_id']
    tipo    = request.form.get('tipo')
    item_id = request.form.get('id', type=int)
    db      = get_db()

    if tipo == 'Venta':
        db.execute('DELETE FROM ventas WHERE id = ? AND negocio_id = ?', (item_id, nid))
    elif tipo == 'Reparación':
        # Borrar también cualquier venta duplicada histórica asociada a esta orden
        orden = db.execute(
            'SELECT numero_orden FROM ordenes WHERE id = ? AND negocio_id = ?', (item_id, nid)
        ).fetchone()
        if orden:
            db.execute(
                "DELETE FROM ventas WHERE negocio_id = ? AND (notas = ? OR producto LIKE 'Servicio: %')",
                (nid, 'Orden ' + orden['numero_orden'])
            )
        db.execute('DELETE FROM ordenes WHERE id = ? AND negocio_id = ?', (item_id, nid))

    db.commit()
    flash('Registro eliminado correctamente.', 'success')
    return redirect(url_for('completos'))


# ── PWA: manifest y service worker servidos desde la raíz ────────────────────
@app.route('/manifest.json')
def pwa_manifest():
    return send_from_directory('static', 'manifest.json',
                               mimetype='application/manifest+json')


@app.route('/sw.js')
def service_worker():
    resp = make_response(send_from_directory('static', 'sw.js',
                                             mimetype='application/javascript'))
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return resp


@app.route('/offline.html')
def offline_page():
    return send_from_directory('static', 'offline.html')


# ── Página QR: muestra la IP local para conectar el celular ─────────────────
@app.route('/qr')
def qr_page():
    ip     = _get_local_ip()
    puerto = request.host.split(':')[1] if ':' in request.host else '5000'
    url    = f'http://{ip}:{puerto}'
    return render_template('qr.html', url_celular=url, ip=ip, puerto=puerto)


if __name__ == '__main__':
    ip_local = _get_local_ip()
    linea = "=" * 54
    print(linea)
    print("  Tecnocel CRM  —  Servidor iniciado")
    print(linea)
    print(f"  PC  (local):   http://localhost:5000")
    print(f"  Celular (LAN): http://{ip_local}:5000")
    print(f"  Codigo QR:     http://{ip_local}:5000/qr")
    print(linea)
    print("  Asegurate de que el celular este en el mismo WiFi")
    print(linea)
    app.run(debug=True, host='0.0.0.0', port=5000)

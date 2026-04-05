"""
Base de datos SQLite para Tecnocel CRM — Versión SaaS Multi-tenant.
Cada negocio tiene sus propios datos aislados por negocio_id.

La ruta de la base de datos puede configurarse con la variable de entorno DB_PATH.
En Railway u otros servicios con volúmenes persistentes, establece DB_PATH al
directorio montado, por ejemplo: /data/tecnocel.db
"""

import sqlite3
import os

# Permite configurar la ruta de la BD via variable de entorno para producción
# con almacenamiento persistente (Railway Volumes, Render Disks, etc.)
_default_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tecnocel.db')
DB_PATH = os.environ.get('DB_PATH', _default_path)


def get_db():
    """Abre y retorna una conexión a la base de datos SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')  # Mejor rendimiento en concurrencia
    return conn


def init_db():
    """Crea las tablas y los índices si no existen."""
    conn = get_db()
    c = conn.cursor()

    # ── Tabla de negocios (usuarios del SaaS) ─────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS negocios (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_negocio  TEXT    NOT NULL,
            email           TEXT    NOT NULL UNIQUE,
            password_hash   TEXT    NOT NULL,
            telefono        TEXT,
            ciudad          TEXT,
            plan            TEXT    NOT NULL DEFAULT 'basico',
            activo          INTEGER NOT NULL DEFAULT 1,
            fecha_creacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Productos (con negocio_id) ─────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            negocio_id      INTEGER NOT NULL,
            nombre          TEXT    NOT NULL,
            marca           TEXT,
            categoria       TEXT,
            precio          REAL    NOT NULL DEFAULT 0,
            stock           INTEGER NOT NULL DEFAULT 0,
            descripcion     TEXT,
            foto            TEXT,
            fecha_creacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE CASCADE
        )
    ''')

    # ── Clientes (con negocio_id) ──────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            negocio_id      INTEGER NOT NULL,
            nombre          TEXT    NOT NULL,
            cedula          TEXT,
            telefono        TEXT,
            direccion       TEXT,
            ciudad          TEXT,
            notas           TEXT,
            fecha_creacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE CASCADE
        )
    ''')

    # ── Ventas (con negocio_id) ────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            negocio_id      INTEGER NOT NULL,
            cliente_id      INTEGER NOT NULL,
            producto        TEXT    NOT NULL,
            precio          REAL    NOT NULL,
            tipo_pago       TEXT    NOT NULL DEFAULT 'contado',
            fecha           TEXT    NOT NULL,
            notas           TEXT,
            fecha_creacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE CASCADE,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
        )
    ''')

    # ── Egresos (con negocio_id) ───────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS egresos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            negocio_id      INTEGER NOT NULL,
            concepto        TEXT    NOT NULL,
            monto           REAL    NOT NULL,
            fecha           TEXT    NOT NULL,
            notas           TEXT,
            fecha_creacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE CASCADE
        )
    ''')

    # ── Índices para mejorar el rendimiento en consultas frecuentes ──
    c.execute('CREATE INDEX IF NOT EXISTS idx_clientes_negocio ON clientes(negocio_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_ventas_negocio   ON ventas(negocio_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_ventas_cliente   ON ventas(cliente_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_ventas_fecha     ON ventas(fecha_creacion DESC)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_productos_negocio ON productos(negocio_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_egresos_negocio  ON egresos(negocio_id)')

    conn.commit()
    conn.close()
    print("Base de datos SaaS inicializada correctamente.")


def negocio_existe(negocio_id):
    """Verifica si un negocio existe en la base de datos."""
    try:
        conn = get_db()
        row = conn.execute(
            'SELECT id FROM negocios WHERE id = ? AND activo = 1', (negocio_id,)
        ).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False

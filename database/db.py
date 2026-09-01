import sqlite3
import os
from flask import g

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tecnocel.db')

def get_db():
    if 'db' not in g:
        # check_same_thread=False permite usar la conexión en el mismo request de Flask
        # timeout ayuda a esperar si la base de datos está ocupada
        g.db = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
        # Modo WAL mejora el rendimiento y reduce errores de base de datos bloqueada
        g.db.execute('PRAGMA journal_mode = WAL')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # ── Tabla de negocios (SaaS) ──
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

    # ── Tabla de productos ──
    c.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            negocio_id      INTEGER NOT NULL,
            nombre          TEXT    NOT NULL,
            marca           TEXT,
            categoria       TEXT,
            precio          REAL    NOT NULL,
            stock           INTEGER NOT NULL DEFAULT 1,
            descripcion     TEXT,
            foto            TEXT,
            fecha_creacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE CASCADE
        )
    ''')

    # ── Tabla de clientes ──
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

    # ── Tabla de ventas ──
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

    # ── Tabla de egresos ──
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

    # ── Migraciones seguras para suscripción ──────────────────────────────
    migraciones = [
        "ALTER TABLE negocios ADD COLUMN fecha_vencimiento TEXT DEFAULT NULL",
        "ALTER TABLE negocios ADD COLUMN plan_nombre TEXT DEFAULT 'basico'",
        "ALTER TABLE negocios ADD COLUMN dias_gracia INTEGER DEFAULT 3",
        "ALTER TABLE negocios ADD COLUMN logo_base64 TEXT DEFAULT NULL",
        "ALTER TABLE negocios ADD COLUMN slogan TEXT DEFAULT NULL",
        "ALTER TABLE negocios ADD COLUMN tema TEXT DEFAULT 'cyan'",
    ]
    for sql in migraciones:
        try:
            c.execute(sql)
        except Exception:
            pass  # La columna ya existe

    # Dar 14 días de prueba gratis a negocios sin fecha_vencimiento
    from datetime import date, timedelta
    fecha_prueba = (date.today() + timedelta(days=14)).isoformat()
    c.execute('''
        UPDATE negocios
        SET fecha_vencimiento = ?, plan_nombre = 'prueba'
        WHERE fecha_vencimiento IS NULL
    ''', (fecha_prueba,))

    conn.commit()
    conn.close()
    print("Base de datos SaaS inicializada con modo WAL.")

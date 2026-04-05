"""
Base de datos SQLite para Tecnocel CRM - Versión SaaS Multi-tenant
Cada negocio tiene sus propios datos aislados por negocio_id
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tecnocel.db')


from flask import g

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
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
            precio          REAL    NOT NULL,
            stock           INTEGER NOT NULL DEFAULT 1,
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

    conn.commit()
    conn.close()
    print("Base de datos SaaS inicializada correctamente.")

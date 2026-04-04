"""
Base de datos SQLite para Tecnocel CRM
Contiene la inicialización y funciones de acceso a la BD
"""

import sqlite3
import os

# Ruta del archivo de base de datos
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tecnocel.db')


def get_db():
    """Retorna una conexión a la base de datos con filas como diccionarios"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permite acceder columnas por nombre
    conn.execute('PRAGMA foreign_keys = ON')  # Asegurar borrado en cascada
    return conn


def init_db():
    """Crea las tablas si no existen"""
    conn = get_db()
    cursor = conn.cursor()

    # Tabla de productos (Inventario)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre        TEXT    NOT NULL,
            marca         TEXT,
            categoria     TEXT,
            precio        REAL    NOT NULL,
            stock         INTEGER NOT NULL DEFAULT 1,
            descripcion   TEXT,
            foto          TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabla de clientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre        TEXT    NOT NULL,
            cedula        TEXT,
            telefono      TEXT,
            direccion     TEXT,
            ciudad        TEXT,
            notas         TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabla de ventas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id    INTEGER NOT NULL,
            producto      TEXT    NOT NULL,
            precio        REAL    NOT NULL,
            tipo_pago     TEXT    NOT NULL DEFAULT 'contado',
            fecha         TEXT    NOT NULL,
            notas         TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
        )
    ''')

    # Tabla de egresos (Finanzas)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS egresos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto      TEXT    NOT NULL,
            monto         REAL    NOT NULL,
            fecha         TEXT    NOT NULL,
            notas         TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente.")

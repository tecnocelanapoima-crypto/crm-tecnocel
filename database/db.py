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

    # ── Tabla de leads AnaMaya ──
    c.execute('''
        CREATE TABLE IF NOT EXISTS leads_anamaya (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT    NOT NULL,
            telefono        TEXT    NOT NULL,
            ciudad          TEXT    NOT NULL,
            origen          TEXT    NOT NULL DEFAULT 'Meta Ads',
            fecha_creacion  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Tabla de configuración por negocio (Capa 1) ──
    c.execute('''
        CREATE TABLE IF NOT EXISTS negocio_config (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            negocio_id              INTEGER NOT NULL UNIQUE,
            nombre_dueno            TEXT,
            correo_notificaciones   TEXT,
            telegram_chat_id        TEXT,
            whatsapp_dueno          TEXT,
            mensaje_bienvenida_lead TEXT,
            activo                  INTEGER NOT NULL DEFAULT 1,
            created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (negocio_id) REFERENCES negocios(id) ON DELETE CASCADE
        )
    ''')

    # Trigger para mantener updated_at actualizado automáticamente
    c.execute('''
        CREATE TRIGGER IF NOT EXISTS trg_negocio_config_updated_at
        AFTER UPDATE ON negocio_config
        FOR EACH ROW
        BEGIN
            UPDATE negocio_config SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    ''')

    # Semillas iniciales — INSERT OR IGNORE (no sobreescribe si ya existen)
    _semillas_config = [
        (
            1,
            'Andrés Urrego',
            'tecnocelanapoima@gmail.com',
            None,
            '573124837718',
            'Hola {nombre}, gracias por contactarnos en Tecnocel. '
            'En breve uno de nuestros asesores te atenderá. 📱',
        ),
        (
            6,
            'Abel',
            'tecnocelanapoima@gmail.com',
            None,
            '573155514708',
            'Hola {nombre}, bienvenido/a a AnaMaya Wellness 🌿. '
            'Pronto te contactaremos para agendar tu sesión.',
        ),
    ]
    for _s in _semillas_config:
        try:
            c.execute('''
                INSERT OR IGNORE INTO negocio_config
                    (negocio_id, nombre_dueno, correo_notificaciones,
                     telegram_chat_id, whatsapp_dueno, mensaje_bienvenida_lead)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', _s)
        except Exception:
            pass  # negocio_id no existe aún en esta DB

    # Migración: actualizar placeholders viejos si Railway ya tenía la tabla
    _actualizaciones_config = [
        (
            'Andrés Urrego', 'tecnocelanapoima@gmail.com', '573124837718',
            1, 'PLACEHOLDER_NOMBRE_DUENO_TECNOCEL',
        ),
        (
            'Abel', 'tecnocelanapoima@gmail.com', '573155514708',
            6, 'PLACEHOLDER_NOMBRE_DUENO_ANAMAYA',
        ),
    ]
    for _a in _actualizaciones_config:
        try:
            c.execute('''
                UPDATE negocio_config
                SET nombre_dueno=?, correo_notificaciones=?, whatsapp_dueno=?
                WHERE negocio_id=? AND nombre_dueno=?
            ''', _a)
        except Exception:
            pass

    # ── Migraciones seguras para suscripción ──────────────────────────────
    migraciones = [
        "ALTER TABLE negocios ADD COLUMN fecha_vencimiento TEXT DEFAULT NULL",
        "ALTER TABLE negocios ADD COLUMN plan_nombre TEXT DEFAULT 'basico'",
        "ALTER TABLE negocios ADD COLUMN dias_gracia INTEGER DEFAULT 3",
        "ALTER TABLE negocios ADD COLUMN logo_base64 TEXT DEFAULT NULL",
        "ALTER TABLE negocios ADD COLUMN slogan TEXT DEFAULT NULL",
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

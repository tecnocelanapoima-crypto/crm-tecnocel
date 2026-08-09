"""
Capa 1 — Captura y enrutamiento de leads
POST /webhook/lead  →  guarda lead, notifica al dueño y dispara n8n
"""

import json
import logging
import os
import smtplib
import sqlite3
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib import request as urllib_request

from flask import Blueprint, jsonify, request

from database.db import DB_PATH, get_db

webhook_bp = Blueprint('webhook', __name__)
logger = logging.getLogger(__name__)


# ── Helpers internos ──────────────────────────────────────────────────────────

def _log_evento(tipo, payload, error=None):
    """Persiste un evento en eventos_log con conexión propia (apto para threads)."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute(
            'INSERT INTO eventos_log (tipo, payload, error) VALUES (?, ?, ?)',
            (tipo, json.dumps(payload, default=str), str(error) if error else None),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.error('eventos_log write failed tipo=%s: %s', tipo, exc)


def _enviar_email(negocio_nombre, correo_destino, lead):
    """Envía email al dueño del negocio con los datos del nuevo lead."""
    smtp_host = os.environ.get('SMTP_HOST', '')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    smtp_from = os.environ.get('SMTP_FROM', smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass, correo_destino]):
        logger.warning('Email omitido — faltan variables SMTP o correo destino')
        _log_evento('email_omitido', lead, 'Faltan variables SMTP o correo_destino')
        return

    asunto = f"Nuevo lead — {negocio_nombre}"
    cuerpo = (
        f"Nuevo cliente interesado en {negocio_nombre}\n\n"
        f"Nombre:   {lead.get('nombre')}\n"
        f"Teléfono: {lead.get('telefono')}\n"
        f"Ciudad:   {lead.get('ciudad') or 'N/A'}\n"
        f"Origen:   {lead.get('origen') or 'N/A'}\n"
        f"Mensaje:  {lead.get('mensaje_inicial') or '—'}\n"
        f"Recibido: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Ver en CRM: {os.environ.get('APP_URL', 'https://tu-dominio.com')}/clientes\n"
    )
    msg = MIMEMultipart()
    msg['From']    = smtp_from
    msg['To']      = correo_destino
    msg['Subject'] = asunto
    msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as srv:
            srv.starttls()
            srv.login(smtp_user, smtp_pass)
            srv.sendmail(smtp_from, correo_destino, msg.as_string())
        logger.info('Email enviado a %s (negocio=%s)', correo_destino, negocio_nombre)
        _log_evento('email_ok', lead)
    except Exception as exc:
        logger.error('Error enviando email a %s: %s', correo_destino, exc)
        _log_evento('email_error', lead, exc)


def _disparar_n8n(payload):
    """Envía el payload del lead al webhook de n8n configurado."""
    url = os.environ.get('N8N_WEBHOOK_URL_LEAD_BIENVENIDA', '')
    if not url:
        logger.debug('N8N_WEBHOOK_URL_LEAD_BIENVENIDA no configurada, omitiendo')
        return

    body = json.dumps(payload, default=str).encode('utf-8')
    req = urllib_request.Request(
        url, data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as resp:
            logger.info('Webhook n8n disparado status=%s', resp.status)
        _log_evento('n8n_ok', payload)
    except Exception as exc:
        logger.error('Error webhook n8n: %s', exc)
        _log_evento('n8n_error', payload, exc)


# ── Endpoint ──────────────────────────────────────────────────────────────────

@webhook_bp.route('/lead', methods=['POST'])
def recibir_lead():
    # ── 1. Autenticación por header ────────────────────────────────────────
    token_esperado = os.environ.get('WEBHOOK_TOKEN', '')
    if token_esperado:
        if request.headers.get('X-Webhook-Token', '') != token_esperado:
            return jsonify({'error': 'No autorizado'}), 401
    else:
        logger.warning('WEBHOOK_TOKEN no configurado — endpoint desprotegido')

    # ── 2. Parsear y validar campos ────────────────────────────────────────
    data           = request.get_json(silent=True) or {}
    negocio_id     = data.get('negocio_id')
    nombre         = (data.get('nombre')          or '').strip()
    telefono       = (data.get('telefono')         or '').strip()
    ciudad         = (data.get('ciudad')           or '').strip()
    origen         = (data.get('origen')           or 'desconocido').strip()
    mensaje_inicial = (data.get('mensaje_inicial') or '').strip()

    if not negocio_id or not nombre or not telefono:
        return jsonify({'error': 'Campos requeridos: negocio_id, nombre, telefono'}), 400

    try:
        negocio_id = int(negocio_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'negocio_id debe ser un entero'}), 400

    db = get_db()

    # ── 3. Verificar que el negocio existe ─────────────────────────────────
    negocio = db.execute(
        'SELECT id, nombre_negocio FROM negocios WHERE id = ?', (negocio_id,)
    ).fetchone()
    if not negocio:
        return jsonify({'error': f'negocio_id {negocio_id} no existe'}), 404

    # ── 4. Detección de duplicados (teléfono + negocio) ────────────────────
    existente = db.execute(
        'SELECT id FROM clientes WHERE negocio_id = ? AND telefono = ?',
        (negocio_id, telefono),
    ).fetchone()
    if existente:
        return jsonify({
            'ok':        False,
            'duplicado': True,
            'mensaje':   'Lead ya registrado con ese teléfono',
            'cliente_id': existente['id'],
        }), 200

    # ── 5. Guardar lead como cliente ───────────────────────────────────────
    cursor = db.execute(
        '''INSERT INTO clientes (negocio_id, nombre, telefono, ciudad, origen, notas)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (negocio_id, nombre, telefono, ciudad, origen, mensaje_inicial or None),
    )
    db.commit()
    cliente_id = cursor.lastrowid

    # ── 6. Leer config del negocio ─────────────────────────────────────────
    config = db.execute(
        'SELECT * FROM negocio_config WHERE negocio_id = ? AND activo = 1',
        (negocio_id,),
    ).fetchone()

    # ── 7. Armar payload para notificaciones ──────────────────────────────
    bienvenida = ''
    if config and config['mensaje_bienvenida_lead']:
        try:
            bienvenida = config['mensaje_bienvenida_lead'].format(nombre=nombre)
        except (KeyError, IndexError):
            bienvenida = config['mensaje_bienvenida_lead']

    lead_payload = {
        'cliente_id':        cliente_id,
        'negocio_id':        negocio_id,
        'negocio_nombre':    negocio['nombre_negocio'],
        'nombre':            nombre,
        'telefono':          telefono,
        'ciudad':            ciudad,
        'origen':            origen,
        'mensaje_inicial':   mensaje_inicial,
        'mensaje_bienvenida': bienvenida,
    }

    # ── 8. Acciones asíncronas (no bloquean la respuesta) ─────────────────
    if config:
        threading.Thread(
            target=_enviar_email,
            args=(negocio['nombre_negocio'], config['correo_notificaciones'], lead_payload),
            daemon=True,
        ).start()
        threading.Thread(
            target=_disparar_n8n,
            args=(lead_payload,),
            daemon=True,
        ).start()

    return jsonify({'ok': True, 'cliente_id': cliente_id}), 201

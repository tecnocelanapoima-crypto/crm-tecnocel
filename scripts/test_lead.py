#!/usr/bin/env python3
"""
Script de QA rápido — Envía leads de prueba al endpoint POST /webhook/lead.

Uso:
    python scripts/test_lead.py                    # usa localhost:5000
    APP_URL=https://mi-app.railway.app python scripts/test_lead.py
    WEBHOOK_TOKEN=mi-token python scripts/test_lead.py

Variables de entorno:
    APP_URL        URL base del CRM  (default: http://localhost:5000)
    WEBHOOK_TOKEN  Token de autenticación (default: cadena vacía)
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

BASE_URL = os.environ.get('APP_URL', 'http://localhost:5000').rstrip('/')
TOKEN    = os.environ.get('WEBHOOK_TOKEN', '')
ENDPOINT = f'{BASE_URL}/webhook/lead'

# ── Casos de prueba ───────────────────────────────────────────────────────────

CASOS = [
    {
        '_descripcion': 'Lead válido — AnaMaya Anapoima (negocio_id=6)',
        'negocio_id':    6,
        'nombre':        f'Test Lead {datetime.now().strftime("%H:%M:%S")}',
        'telefono':      '3190000001',
        'ciudad':        'Anapoima',
        'origen':        'Meta Ads',
        'mensaje_inicial': 'Quiero información sobre los masajes',
    },
    {
        '_descripcion': 'Lead válido — Tecnocel (negocio_id=1)',
        'negocio_id':    1,
        'nombre':        f'Test Lead {datetime.now().strftime("%H:%M:%S")}',
        'telefono':      '3190000002',
        'ciudad':        'Anapoima',
        'origen':        'Referido',
    },
    {
        '_descripcion': 'Duplicado — mismo teléfono AnaMaya',
        'negocio_id':    6,
        'nombre':        'Duplicado Test',
        'telefono':      '3190000001',   # mismo que el primer caso
        'origen':        'Meta Ads',
    },
    {
        '_descripcion': 'Token inválido → debe dar 401',
        '_token_override': 'token-incorrecto',
        'negocio_id':    6,
        'nombre':        'Sin acceso',
        'telefono':      '3190000099',
        'origen':        'Meta Ads',
    },
    {
        '_descripcion': 'Campos faltantes (sin telefono) → debe dar 400',
        'negocio_id':    6,
        'nombre':        'Sin Telefono',
        'origen':        'Meta Ads',
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

VERDE   = '\033[92m'
ROJO    = '\033[91m'
AMARILLO = '\033[93m'
RESET   = '\033[0m'
NEGRITA = '\033[1m'


def _color(texto, color):
    return f'{color}{texto}{RESET}' if sys.stdout.isatty() else texto


def enviar(payload, token_override=None):
    token = token_override if token_override is not None else TOKEN
    body  = json.dumps({k: v for k, v in payload.items() if not k.startswith('_')})
    req   = urllib.request.Request(
        ENDPOINT,
        data=body.encode('utf-8'),
        headers={
            'Content-Type':    'application/json',
            'X-Webhook-Token': token,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except Exception:
            return e.code, {'error': str(e)}
    except urllib.error.URLError as e:
        return None, {'error': f'No se pudo conectar: {e.reason}'}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(_color(f'\n{"═" * 60}', NEGRITA))
    print(_color(f'  QA — POST {ENDPOINT}', NEGRITA))
    if TOKEN:
        print(f'  Token: {TOKEN[:8]}{"*" * (len(TOKEN) - 8)}')
    else:
        print(_color('  ⚠  WEBHOOK_TOKEN no configurado', AMARILLO))
    print(_color(f'{"═" * 60}\n', NEGRITA))

    errores = 0
    for i, caso in enumerate(CASOS, 1):
        desc   = caso.get('_descripcion', f'Caso {i}')
        t_over = caso.get('_token_override')
        print(f'{_color(f"[{i}]", NEGRITA)} {desc}')

        status, resp = enviar(caso, token_override=t_over)

        if status is None:
            print(_color(f'     ✗ ERROR DE CONEXIÓN: {resp["error"]}', ROJO))
            errores += 1
        else:
            es_ok = (
                (status == 201 and resp.get('ok'))
                or (status == 200 and resp.get('duplicado'))
                or (status in (400, 401, 404) and 'error' in resp)
            )
            icono = _color('✓', VERDE) if es_ok else _color('✗', ROJO)
            color = VERDE if es_ok else ROJO
            print(f'     {icono} {_color(str(status), color)}  {json.dumps(resp, ensure_ascii=False)}')
            if not es_ok:
                errores += 1
        print()

    print(_color(f'{"─" * 60}', NEGRITA))
    if errores == 0:
        print(_color(f'  Todos los casos pasaron ({len(CASOS)}/{len(CASOS)})', VERDE))
    else:
        print(_color(f'  {errores} caso(s) fallaron', ROJO))
    print(_color(f'{"─" * 60}\n', NEGRITA))

    sys.exit(0 if errores == 0 else 1)


if __name__ == '__main__':
    main()

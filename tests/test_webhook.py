"""
Tests unitarios — POST /webhook/lead (Capa 1)

Cómo ejecutar:
    python -m pytest tests/ -v
    python tests/test_webhook.py
"""

import json
import os
import smtplib
import tempfile
import unittest
from unittest.mock import patch

# ── Entorno de test (DEBE ir antes de importar la app) ────────────────────────
_db_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_db_tmp.close()
os.environ.setdefault('TECNOCEL_DB_PATH', _db_tmp.name)
os.environ['WEBHOOK_TOKEN'] = 'test-token-secret'

from app import app          # noqa: E402
from database.db import get_db  # noqa: E402

_TOKEN      = 'test-token-secret'
_NEGOCIO_ID = 99


class _SyncThread:
    """
    Reemplaza threading.Thread en tests: ejecuta el target sincrónicamente
    y captura excepciones igual que un hilo daemon real.
    """
    def __init__(self, *, target, args=(), daemon=False, **kw):
        self._target = target
        self._args   = args

    def start(self):
        try:
            self._target(*self._args)
        except Exception:
            pass  # imita el silencio de los hilos daemon


class TestWebhookLead(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        cls.client = app.test_client()

    def setUp(self):
        """Crea negocio y config de prueba, limpia clientes y logs."""
        with app.app_context():
            db = get_db()
            db.execute('DELETE FROM clientes      WHERE negocio_id = ?', (_NEGOCIO_ID,))
            db.execute('DELETE FROM eventos_log')
            db.execute('DELETE FROM negocio_config WHERE negocio_id = ?', (_NEGOCIO_ID,))
            db.execute('DELETE FROM negocios       WHERE id = ?',         (_NEGOCIO_ID,))
            db.execute(
                'INSERT INTO negocios (id, nombre_negocio, email, password_hash) '
                'VALUES (?, ?, ?, ?)',
                (_NEGOCIO_ID, 'Negocio Test', 'test@test.com', 'hash_test'),
            )
            db.execute(
                'INSERT INTO negocio_config '
                '  (negocio_id, correo_notificaciones, whatsapp_dueno, mensaje_bienvenida_lead) '
                'VALUES (?, ?, ?, ?)',
                (_NEGOCIO_ID, 'admin@test.com', '573001111111', 'Hola {nombre}, bienvenido!'),
            )
            db.commit()

    def tearDown(self):
        with app.app_context():
            db = get_db()
            db.execute('DELETE FROM clientes       WHERE negocio_id = ?', (_NEGOCIO_ID,))
            db.execute('DELETE FROM eventos_log')
            db.execute('DELETE FROM negocio_config WHERE negocio_id = ?', (_NEGOCIO_ID,))
            db.execute('DELETE FROM negocios        WHERE id = ?',        (_NEGOCIO_ID,))
            db.commit()

    def _post(self, data, token=_TOKEN):
        headers = {'Content-Type': 'application/json'}
        if token is not None:
            headers['X-Webhook-Token'] = token
        return self.client.post(
            '/webhook/lead',
            data=json.dumps(data),
            headers=headers,
        )

    # ── Test 1: Lead nuevo con notificación exitosa ───────────────────────────

    @patch('routes.webhook.threading.Thread', _SyncThread)
    @patch('routes.webhook._enviar_email')
    @patch('routes.webhook._disparar_n8n')
    def test_lead_nuevo_notificacion_exitosa(self, mock_n8n, mock_email):
        resp = self._post({
            'negocio_id': _NEGOCIO_ID,
            'nombre':     'Ana García',
            'telefono':   '3001234567',
            'ciudad':     'Anapoima',
            'origen':     'Meta Ads',
        })

        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        self.assertTrue(body['ok'])
        self.assertIn('cliente_id', body)

        # Ambas notificaciones deben haberse disparado
        mock_email.assert_called_once()
        mock_n8n.assert_called_once()

        # El mensaje de bienvenida del payload incluye el nombre
        n8n_payload = mock_n8n.call_args[0][0]
        self.assertIn('Ana García', n8n_payload['mensaje_bienvenida'])

    # ── Test 2: Fallo de correo → responde 201 igual ──────────────────────────

    @patch('routes.webhook.threading.Thread', _SyncThread)
    @patch('routes.webhook._disparar_n8n')
    def test_lead_fallo_email_responde_201(self, mock_n8n):
        with patch('routes.webhook.smtplib.SMTP',
                   side_effect=smtplib.SMTPException('Servidor SMTP caído')), \
             patch.dict(os.environ, {
                 'SMTP_HOST': 'smtp.test.com',
                 'SMTP_PORT': '587',
                 'SMTP_USER': 'user@test.com',
                 'SMTP_PASS': 'password',
             }):
            resp = self._post({
                'negocio_id': _NEGOCIO_ID,
                'nombre':     'Pedro Fallo',
                'telefono':   '3002222222',
                'origen':     'Meta Ads',
            })

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.get_json()['ok'])

    # ── Test 3: Fallo de webhook n8n → responde 201 igual ────────────────────

    @patch('routes.webhook.threading.Thread', _SyncThread)
    @patch('routes.webhook._enviar_email')
    def test_lead_fallo_n8n_responde_201(self, mock_email):
        from urllib.error import URLError
        with patch('routes.webhook.urllib_request.urlopen',
                   side_effect=URLError('n8n caído')), \
             patch.dict(os.environ, {
                 'N8N_WEBHOOK_URL_LEAD_BIENVENIDA': 'http://n8n.test/webhook/abc',
             }):
            resp = self._post({
                'negocio_id': _NEGOCIO_ID,
                'nombre':     'Luis Fallo',
                'telefono':   '3003333333',
                'origen':     'Meta Ads',
            })

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.get_json()['ok'])

    # ── Test 4: Lead duplicado no dispara notificaciones ─────────────────────

    @patch('routes.webhook.threading.Thread', _SyncThread)
    @patch('routes.webhook._enviar_email')
    @patch('routes.webhook._disparar_n8n')
    def test_lead_duplicado_sin_notificaciones(self, mock_n8n, mock_email):
        # Primera inserción
        self._post({
            'negocio_id': _NEGOCIO_ID,
            'nombre':     'María Dup',
            'telefono':   '3004444444',
            'origen':     'Meta Ads',
        })
        mock_email.reset_mock()
        mock_n8n.reset_mock()

        # Segunda inserción con el mismo teléfono
        resp = self._post({
            'negocio_id': _NEGOCIO_ID,
            'nombre':     'María Dup',
            'telefono':   '3004444444',
            'origen':     'Meta Ads',
        })

        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body['duplicado'])
        self.assertFalse(body['ok'])
        mock_email.assert_not_called()
        mock_n8n.assert_not_called()

    # ── Tests de validación (extras) ──────────────────────────────────────────

    def test_token_invalido_retorna_401(self):
        resp = self._post(
            {'negocio_id': _NEGOCIO_ID, 'nombre': 'X', 'telefono': '3005555555'},
            token='token-incorrecto',
        )
        self.assertEqual(resp.status_code, 401)

    def test_sin_token_retorna_401(self):
        resp = self._post(
            {'negocio_id': _NEGOCIO_ID, 'nombre': 'X', 'telefono': '3005555555'},
            token=None,
        )
        self.assertEqual(resp.status_code, 401)

    def test_sin_telefono_retorna_400(self):
        resp = self._post({'negocio_id': _NEGOCIO_ID, 'nombre': 'Solo Nombre'})
        self.assertEqual(resp.status_code, 400)

    def test_negocio_inexistente_retorna_404(self):
        resp = self._post({
            'negocio_id': 9999,
            'nombre':     'Nadie',
            'telefono':   '3006666666',
        })
        self.assertEqual(resp.status_code, 404)


if __name__ == '__main__':
    unittest.main(verbosity=2)

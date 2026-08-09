# Tecnocel CRM

Sistema de gestión de clientes, ventas, inventario y finanzas para el negocio **Tecnocel**. Versión SaaS multi-tenant: cada negocio ve únicamente sus propios datos.

---

## Tecnologías

| Componente | Tecnología |
|---|---|
| Backend | Python 3.9+ / Flask 3.0 |
| Base de datos | SQLite (WAL mode + índices + foreign keys) |
| Generación de PDF | ReportLab |
| Servidor de producción | Gunicorn |
| Frontend | Bootstrap 5.3 + Bootstrap Icons |

---

## Instalación y ejecución

### Paso 1 — Verificar Python

```bash
python --version
# Se requiere Python 3.9 o superior
```

### Paso 2 — Clonar o descargar el proyecto

```bash
git clone <url-del-repositorio>
cd crm-tecnocel
```

### Paso 3 — Crear entorno virtual (recomendado)

```bash
python -m venv venv
```

| Sistema | Comando de activación |
|---|---|
| Windows CMD | `venv\Scripts\activate` |
| Windows PowerShell | `venv\Scripts\Activate.ps1` |
| Git Bash / Linux / Mac | `source venv/bin/activate` |

### Paso 4 — Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 5 — Configurar variables de entorno (importante en producción)

```bash
# Linux / Mac / Git Bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Windows CMD
python -c "import secrets; print(secrets.token_hex(32))"
set SECRET_KEY=<el_valor_generado>
```

> **Importante:** En producción, NUNCA uses la clave por defecto. Siempre establece `SECRET_KEY` como variable de entorno.

### Paso 6 — Ejecutar el servidor

**Desarrollo:**
```bash
python app.py
```

**Producción (con Gunicorn):**
```bash
gunicorn app:app --bind 0.0.0.0:5000 --workers 2
```

Accede en: `http://localhost:5000`

---

## Estructura del proyecto

```
crm-tecnocel/
├── app.py                    # Aplicación principal Flask
├── requirements.txt          # Dependencias Python
├── Procfile                  # Configuración para Heroku/Railway
├── tecnocel.db               # Base de datos SQLite (se crea automáticamente)
├── database/
│   └── db.py                 # BD con índices, WAL mode y foreign keys
├── routes/
│   ├── auth.py               # Registro, login y logout (PBKDF2-SHA256)
│   ├── clientes.py           # CRUD de clientes con búsqueda
│   ├── ventas.py             # CRUD de ventas
│   ├── facturas.py           # Generación de facturas PDF
│   ├── inventario.py         # CRUD de productos y ajuste rápido de stock
│   ├── finanzas.py           # Ingresos, egresos y balance por mes
│   └── whatsapp.py           # Envío de comprobante por WhatsApp Web
├── templates/
│   ├── base.html             # Plantilla base con navegación responsiva
│   ├── index.html            # Dashboard con estadísticas y alertas
│   ├── auth/                 # Login y registro
│   ├── clientes/             # Lista, formulario y detalle de clientes
│   ├── ventas/               # Lista y formulario de ventas
│   ├── facturas/             # Vista previa de facturas
│   ├── inventario/           # Lista y formulario de productos
│   └── finanzas/             # Panel de finanzas con filtro por mes
├── static/
│   ├── css/style.css         # Estilos personalizados
│   ├── js/main.js            # JavaScript del frontend
│   └── img/                  # Logos e imágenes
└── facturas_pdf/             # PDFs generados (se crea automáticamente)
```

---

## Funcionalidades

| Módulo | Descripción |
|---|---|
| **Dashboard** | Estadísticas en tiempo real: clientes, ventas, ingresos, balance neto y alertas de stock bajo |
| **Clientes** | Crear, editar, eliminar y buscar clientes con historial de compras |
| **Ventas** | Registrar ventas con producto, precio, tipo de pago y notas |
| **Facturas PDF** | Generar facturas profesionales en PDF con diseño oscuro corporativo |
| **WhatsApp** | Abrir WhatsApp Web con mensaje prellenado y datos de la compra |
| **Inventario** | Gestión de productos con fotos, stock, categorías y ajuste rápido de unidades |
| **Finanzas** | Control de egresos, balance histórico y filtro de ingresos/egresos por mes |

---

## Seguridad

- Las contraseñas se almacenan con hashing **PBKDF2-SHA256** (werkzeug). Las contraseñas antiguas en SHA-256 se migran automáticamente al primer inicio de sesión.
- La clave secreta de sesión se genera aleatoriamente si no se proporciona `SECRET_KEY`.
- Todas las consultas SQL usan parámetros enlazados para prevenir inyección SQL.
- Cada negocio solo puede acceder a sus propios datos (aislamiento por `negocio_id`).

---

## Envío por WhatsApp

El sistema abre **WhatsApp Web** automáticamente con el número del cliente preseleccionado y un mensaje con los detalles de la compra ya escrito.

**Para adjuntar el PDF:**
1. En WhatsApp Web, haz clic en el ícono de adjunto
2. Selecciona el PDF desde la carpeta `facturas_pdf/`
3. Envíalo al cliente

> El número debe estar en formato colombiano (10 dígitos, ej: `3001234567`). El sistema agrega automáticamente el prefijo `+57`.

---

## Capa 1 — Captura y enrutamiento de leads

### Flujo completo

```
[Meta Ads / n8n / cualquier fuente]
          │
          │  POST /webhook/lead
          │  Header: X-Webhook-Token: <WEBHOOK_TOKEN>
          │  Body: { negocio_id, nombre, telefono, ciudad, origen }
          ▼
    ┌─────────────┐
    │  Flask CRM  │
    └──────┬──────┘
           │
           ├─ ¿Token inválido? ──────────────────────────→ 401 Unauthorized
           │
           ├─ ¿Campos faltantes? ────────────────────────→ 400 Bad Request
           │
           ├─ ¿negocio_id no existe? ────────────────────→ 404 Not Found
           │
           ├─ ¿Teléfono ya registrado (mismo negocio)? ──→ 200 { duplicado: true }
           │                                               (sin notificaciones)
           │
           ├─ Guarda en tabla clientes (con campo origen)
           │
           ├──── Thread 1 (async) ────→ Email al dueño vía SMTP
           │                                  └─→ eventos_log { email_ok | email_error }
           │
           └──── Thread 2 (async) ────→ POST a N8N_WEBHOOK_URL_LEAD_BIENVENIDA
                                              └─→ eventos_log { n8n_ok | n8n_error }
                                              │
                                              ▼
                                        [Workflow n8n]
                                              │
                                              └─→ WhatsApp al cliente
                                                  (mensaje_bienvenida del negocio)

    Respuesta al emisor: 201 { ok: true, cliente_id: N }
    (independientemente del resultado de las notificaciones)
```

### Configurar las variables de entorno

Copia `.env.example` a `.env` y ajusta los valores:

```bash
cp .env.example .env
```

Variables obligatorias para producción:

| Variable | Descripción |
|---|---|
| `WEBHOOK_TOKEN` | Token secreto para autenticar el webhook entrante |
| `SMTP_HOST` | Servidor SMTP (ej: `smtp.gmail.com`) |
| `SMTP_PORT` | Puerto SMTP (ej: `587` para TLS) |
| `SMTP_USER` | Usuario / correo remitente |
| `SMTP_PASS` | Contraseña o App Password de Gmail |
| `SMTP_FROM` | Nombre y correo que aparece en el "De:" |
| `N8N_WEBHOOK_URL_LEAD_BIENVENIDA` | URL del webhook en n8n que envía el WhatsApp |
| `APP_URL` | URL pública del CRM (se incluye en el email) |

En **Railway**: ve a tu proyecto → Variables → agrega cada una.

### Probar localmente con curl

**Lead válido (AnaMaya, negocio_id=6):**
```bash
curl -X POST http://localhost:5000/webhook/lead \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: $WEBHOOK_TOKEN" \
  -d '{
    "negocio_id": 6,
    "nombre": "María López",
    "telefono": "3109876543",
    "ciudad": "Anapoima",
    "origen": "Meta Ads",
    "mensaje_inicial": "Quiero información sobre masajes"
  }'
# Esperado: 201 { "ok": true, "cliente_id": N }
```

**Duplicado (mismo teléfono):**
```bash
curl -X POST http://localhost:5000/webhook/lead \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: $WEBHOOK_TOKEN" \
  -d '{"negocio_id": 6, "nombre": "María López", "telefono": "3109876543", "origen": "Meta Ads"}'
# Esperado: 200 { "ok": false, "duplicado": true }
```

**Token inválido:**
```bash
curl -X POST http://localhost:5000/webhook/lead \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: token-incorrecto" \
  -d '{"negocio_id": 6, "nombre": "X", "telefono": "3000000000"}'
# Esperado: 401
```

**Script de QA rápido** (más cómodo que curl):
```bash
python scripts/test_lead.py
```

### Simular un fallo de notificación

Para probar que el endpoint responde 201 aunque el correo falle:

```bash
# Configura un SMTP falso
SMTP_HOST=smtp.inexistente.com SMTP_USER=a SMTP_PASS=b \
python -c "
from app import app
with app.test_client() as c:
    r = c.post('/webhook/lead',
        json={'negocio_id': 6, 'nombre': 'Test', 'telefono': '3199999999', 'origen': 'test'},
        headers={'X-Webhook-Token': 'token-aqui'})
    print(r.status_code, r.get_json())
"
# Esperado: 201 (el fallo SMTP queda en eventos_log, no rompe la respuesta)
```

Para inspeccionar `eventos_log` después de un fallo:
```bash
sqlite3 tecnocel.db "SELECT tipo, error, created_at FROM eventos_log ORDER BY created_at DESC LIMIT 10;"
```

### Correr los tests unitarios

```bash
# Con unittest (sin dependencias extra)
python -m unittest discover tests/ -v

# O con pytest si lo tienes instalado
python -m pytest tests/ -v
```

---

## Solución de problemas

| Error | Solución |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Ejecuta: `pip install -r requirements.txt` |
| `Address already in use` | Cambia el puerto: `app.run(port=5001)` |
| El PDF no se genera | Verifica: `pip install reportlab` |
| WhatsApp no abre | Verifica que tengas un navegador predeterminado configurado |
| Error de permisos en `facturas_pdf/` | Crea la carpeta: `mkdir facturas_pdf` |

---

## Despliegue en producción (Railway / Render / Heroku)

1. Establece la variable de entorno `SECRET_KEY` con un valor seguro.
2. El archivo `Procfile` ya está configurado para Gunicorn.
3. Asegúrate de que el directorio `facturas_pdf/` sea persistente.

---

*Tecnocel CRM — Desarrollado para la gestión eficiente de negocios de tecnología.*

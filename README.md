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

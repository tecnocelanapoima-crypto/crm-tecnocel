# 📱 Tecnocel CRM

Sistema de gestión de clientes y ventas para el negocio **Tecnocel**.

---

## 🚀 Instalación y ejecución paso a paso

### Paso 1 — Verificar Python

Asegúrate de tener Python 3.9 o superior instalado:

```bash
python --version
```

Si no tienes Python, descárgalo en: https://www.python.org/downloads/

---

### Paso 2 — Abrir terminal en la carpeta del proyecto

En Windows: abre la carpeta `tecnocel-crm`, haz clic derecho y selecciona **"Abrir en Terminal"** o **"Git Bash"**.

O desde CMD:
```cmd
cd C:\Users\TECNOCEL\tecnocel-crm
```

---

### Paso 3 — Crear entorno virtual (recomendado)

```bash
python -m venv venv
```

Activar el entorno:
- **Windows CMD:**    `venv\Scripts\activate`
- **Windows PowerShell:** `venv\Scripts\Activate.ps1`
- **Git Bash:** `source venv/Scripts/activate`

---

### Paso 4 — Instalar dependencias

```bash
pip install -r requirements.txt
```

---

### Paso 5 — Ejecutar el servidor

```bash
python app.py
```

Verás este mensaje:
```
==================================================
  Tecnocel CRM iniciado correctamente
  Accede en: http://localhost:5000
==================================================
```

---

### Paso 6 — Abrir en el navegador

Abre tu navegador y ve a:

```
http://localhost:5000
```

¡Listo! El CRM está funcionando.

---

## 📂 Estructura del proyecto

```
tecnocel-crm/
├── app.py                    # Aplicación principal Flask
├── requirements.txt          # Dependencias Python
├── tecnocel.db               # Base de datos SQLite (se crea automáticamente)
├── database/
│   └── db.py                 # Configuración de la base de datos
├── routes/
│   ├── clientes.py           # Rutas de gestión de clientes
│   ├── ventas.py             # Rutas de gestión de ventas
│   ├── facturas.py           # Generación de facturas PDF
│   └── whatsapp.py           # Envío por WhatsApp Web
├── templates/
│   ├── base.html             # Plantilla base con navegación
│   ├── index.html            # Dashboard principal
│   ├── clientes/
│   │   ├── lista.html        # Lista de clientes
│   │   ├── form.html         # Formulario crear/editar cliente
│   │   └── detalle.html      # Detalle del cliente con historial
│   ├── ventas/
│   │   ├── lista.html        # Lista de ventas
│   │   └── form.html         # Formulario nueva venta
│   └── facturas/
│       └── previa.html       # Vista previa de la factura
├── static/
│   ├── css/style.css         # Estilos personalizados
│   └── js/main.js            # JavaScript del frontend
└── facturas_pdf/             # PDFs generados (se crea automáticamente)
```

---

## 💡 Funcionalidades

| Función | Descripción |
|---|---|
| **Clientes** | Crear, editar, eliminar y buscar clientes |
| **Ventas** | Registrar ventas con producto, precio y tipo de pago |
| **Facturas PDF** | Generar facturas profesionales en PDF con un clic |
| **WhatsApp** | Abrir WhatsApp Web con mensaje prellenado para el cliente |

---

## 📲 Envío por WhatsApp

El sistema abre **WhatsApp Web** automáticamente con:
- El número del cliente preseleccionado
- Un mensaje con los detalles de la compra ya escrito

**Para adjuntar el PDF:**
1. En WhatsApp Web, haz clic en el ícono de adjunto 📎
2. Selecciona el PDF desde la carpeta `facturas_pdf/`
3. Envíalo al cliente

> **Nota:** El número debe estar guardado con formato colombiano (10 dígitos, ej: `3001234567`). El sistema agrega automáticamente el prefijo `+57`.

---

## ⚠️ Solución de problemas

**Error: `ModuleNotFoundError: No module named 'flask'`**
→ Ejecuta: `pip install -r requirements.txt`

**Error: `Address already in use`**
→ El puerto 5000 está ocupado. Cambia el puerto en `app.py`:
```python
app.run(debug=True, port=5001)
```

**El PDF no se genera**
→ Verifica que `reportlab` esté instalado: `pip install reportlab`

**WhatsApp no abre**
→ Verifica que tengas un navegador predeterminado configurado.

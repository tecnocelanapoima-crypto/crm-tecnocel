# Bugs encontrados — NO corregir en este PR

Este archivo registra bugs pre-existentes detectados durante el desarrollo de la
Capa 1. Deben atenderse en PRs separados para no mezclar contextos.

---

## BUG-001 — `db.close()` prematuro en routes/whatsapp.py

**Archivo:** `routes/whatsapp.py`  
**Líneas:** 29 y 73  
**Severidad:** Baja (no rompe en producción actualmente)

**Descripción:**  
En las funciones `enviar()` y `abrir_chat()`, se llama a `db.close()` inmediatamente
después de un `fetchone()`, antes de terminar de usar el resultado. Ejemplo en línea 29:

```python
venta = db.execute('SELECT ...').fetchone()
db.close()          # ← cierra aquí

if not venta:       # ← pero el resultado se usa después
    ...
```

Con `sqlite3.Row`, los datos ya están en memoria al hacer `fetchone()`, por lo que
no falla en la práctica. Sin embargo, es inconsistente con el patrón del resto del
CRM (que usa `teardown_appcontext` para cerrar via `close_db`) y podría ser fuente
de confusión o bugs si el código evoluciona.

**Solución recomendada:** Eliminar los `db.close()` manuales en whatsapp.py y dejar
que `teardown_appcontext` los maneje, igual que el resto de los blueprints.

---

## BUG-002 — Backslash en expresiones f-string en routes/ordenes.py ✅ CORREGIDO

**Archivo:** `routes/ordenes.py`  
**Líneas originales:** 492, 505  
**Severidad:** Alta — impedía arrancar la app en Python < 3.12

**Descripción:**  
Dos f-strings usaban `\n\n` dentro de la expresión `{...}`, inválido en Python < 3.12:

```python
# Inválido en Python 3.11
f"{'texto' + '\n\n' if condicion else '\n\n'}"
```

**Solución aplicada:** Variables locales `_costo_linea` y `_valor_linea` antes del
bloque `mensaje = (...)`. Compatible con Python 3.9+.

---

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

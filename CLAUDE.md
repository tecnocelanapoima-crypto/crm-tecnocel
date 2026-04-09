# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Development:**
```bash
python -m venv venv && source venv/bin/activate  # create/activate virtualenv (Linux/Mac)
pip install -r requirements.txt
python app.py  # runs Flask dev server with debug=True
```

**Production:**
```bash
gunicorn app:app --bind 0.0.0.0:5000 --workers 2
```

No build step, test suite, or linter is configured in this project.

## Architecture

**Multi-tenant SaaS CRM** built with Flask + SQLite (no ORM) + Jinja2 server-side rendering. Every piece of business data is isolated by `negocio_id` — this column is on every table and must be included in all queries.

**Entry point:** `app.py` registers all Blueprints, sets up context processors (injects `negocio` data like logo/slogan into all templates), and defines the dashboard route.

**Blueprints** (`routes/`): `auth`, `clientes`, `ventas`, `ordenes`, `inventario`, `facturas`, `finanzas`, `whatsapp`, `admin`, `configuracion`. Each maps to a distinct feature area.

**Database** (`database/db.py`): Direct SQLite via `sqlite3` with `Row` factory, WAL mode, foreign keys enabled, and a 10-second timeout. `get_db()` opens a connection per request; all routes call `db.close()` explicitly. Schema is initialized on app startup via `init_db()`.

**Authentication & subscriptions:** Session-based (`session['negocio_id']`). A `@login_required`-style check at the start of most routes validates session and subscription (`fecha_vencimiento`). Passwords are hashed with werkzeug PBKDF2-SHA256.

**PDF generation** (`routes/facturas.py`, `informe_semanal.py`): Uses ReportLab; PDFs are saved to `facturas_pdf/` (excluded from git).

**Static assets:** Bootstrap 5.3 + Bootstrap Icons via CDN. Custom CSS in `static/css/style.css`, minimal vanilla JS in `static/js/main.js`. No npm, no bundler.

**Template filter:** `|moneda` — formats numbers as Colombian pesos (COP). Registered in `app.py`.

## Key Implementation Details

- The `ordenes` module (`routes/ordenes.py`, ~676 lines) is the most complex: it handles the full repair-order lifecycle (Recibido → En proceso → Listo → Entregado), photo uploads, WhatsApp pre-fill links, and PDF receipts.
- Subscription validation happens per request — check `fecha_vencimiento` and grace period logic in `routes/auth.py` or the relevant decorator.
- `SECRET_KEY` is read from `os.environ.get('SECRET_KEY', '<default>')`. Change the default before any real deployment.
- SQLite database file (`tecnocel.db`) is gitignored. It lives one level above `database/` (i.e., project root).
- Product photos go to `static/uploads/productos/` (gitignored). Business logos are stored as base64 in the `negocios` table.
- `informe_semanal.py` is a standalone script intended for Windows Task Scheduler — it generates a weekly summary PDF independently of the web app.

## Known Issues (REVISION_Y_MEJORAS.md)

- No CSRF protection on any form.
- No database migration tool (Alembic not set up).
- `db.close()` is repeated manually in every route instead of using `@app.teardown_appcontext`.
- No input validation library (raw `request.form` everywhere).

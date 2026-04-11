"""
Gestor de túnel para Tecnocel CRM.
Intenta cloudflared primero, luego ngrok.
Escribe la URL pública en tunnel_url.txt para que Flask la muestre en /qr.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
TUNNEL_FILE = os.path.join(BASE_DIR, 'tunnel_url.txt')


def _banner(url: str, origen: str = 'cloudflare'):
    linea = '=' * 58
    print(f'\n{linea}')
    print(f'  TUNEL ACTIVO ({origen})')
    print(f'  URL publica:  {url}')
    print(f'  QR / Celular: {url}/qr')
    print(f'  Comparte esta URL para acceso con datos moviles')
    print(f'{linea}\n', flush=True)


def guardar_url(url: str):
    with open(TUNNEL_FILE, 'w', encoding='utf-8') as f:
        f.write(url.strip())


def limpiar_url():
    try:
        if os.path.exists(TUNNEL_FILE):
            os.remove(TUNNEL_FILE)
    except Exception:
        pass


# ── Cloudflared ───────────────────────────────────────────────────────────────
def iniciar_cloudflared() -> bool:
    """Arranca cloudflared y captura la URL de trycloudflare.com."""
    # Buscar en PATH y en el directorio del proyecto
    candidatos = ['cloudflared', 'cloudflared.exe',
                  os.path.join(BASE_DIR, 'cloudflared.exe'),
                  os.path.join(BASE_DIR, 'cloudflared')]
    ejecutable = None
    for c in candidatos:
        try:
            subprocess.run([c, '--version'], capture_output=True, check=True)
            ejecutable = c
            break
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    if not ejecutable:
        return False

    print(f'[CF] Iniciando cloudflared ({ejecutable})...')
    proc = subprocess.Popen(
        [ejecutable, 'tunnel', '--url', 'http://localhost:5000'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    url_ok = False
    try:
        for linea in proc.stdout:
            sys.stdout.write('[CF] ' + linea)
            sys.stdout.flush()
            if not url_ok:
                m = re.search(r'https://[a-z0-9\-]+\.trycloudflare\.com', linea)
                if m:
                    url = m.group(0)
                    guardar_url(url)
                    url_ok = True
                    _banner(url, 'cloudflare')
    except KeyboardInterrupt:
        proc.terminate()
    finally:
        limpiar_url()
    return True


# ── ngrok ─────────────────────────────────────────────────────────────────────
def iniciar_ngrok() -> bool:
    """Arranca ngrok y lee la URL pública desde su API local."""
    candidatos = ['ngrok', 'ngrok.exe',
                  os.path.join(BASE_DIR, 'ngrok.exe'),
                  os.path.join(BASE_DIR, 'ngrok')]
    ejecutable = None
    for c in candidatos:
        try:
            subprocess.run([c, 'version'], capture_output=True, check=True)
            ejecutable = c
            break
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    if not ejecutable:
        return False

    print(f'[NG] Iniciando ngrok ({ejecutable})...')
    proc = subprocess.Popen(
        [ejecutable, 'http', '5000'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url_ok = False
    # Esperar hasta 30 s a que ngrok inicie
    for _ in range(15):
        time.sleep(2)
        try:
            resp = urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels', timeout=2)
            data = json.loads(resp.read())
            for t in data.get('tunnels', []):
                if t.get('proto') == 'https':
                    url = t['public_url']
                    guardar_url(url)
                    url_ok = True
                    _banner(url, 'ngrok')
                    break
        except Exception:
            pass
        if url_ok:
            break

    if not url_ok:
        proc.terminate()
        return False

    # Mantener ngrok activo
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    finally:
        limpiar_url()
    return True


# ── Instrucciones de instalación ──────────────────────────────────────────────
INSTRUCCIONES = """
  ┌─────────────────────────────────────────────────────────┐
  │  INSTALA cloudflared para acceso con datos moviles       │
  │                                                         │
  │  1. Ve a:                                               │
  │     https://github.com/cloudflare/cloudflared/releases  │
  │                                                         │
  │  2. Descarga: cloudflared-windows-amd64.exe             │
  │                                                         │
  │  3. Renombralo a:  cloudflared.exe                      │
  │                                                         │
  │  4. Copialo a esta carpeta del proyecto:                │
  │     C:\\Users\\TECNOCEL\\tecnocel-crm\\                    │
  │                                                         │
  │  5. Vuelve a ejecutar  iniciar_con_tunel.bat             │
  │                                                         │
  │  (Alternativa: ngrok — https://ngrok.com/download)      │
  └─────────────────────────────────────────────────────────┘
"""

if __name__ == '__main__':
    limpiar_url()
    print('Buscando cloudflared...')
    if not iniciar_cloudflared():
        print('[!] cloudflared no encontrado. Buscando ngrok...')
        if not iniciar_ngrok():
            print('[!] Ni cloudflared ni ngrok estan instalados.')
            print(INSTRUCCIONES)
            input('Presiona ENTER para salir...')

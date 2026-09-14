"""RCJ Rescue Line offline — lanzador para PC (se empaqueta como RCJ-Line-Offline.exe).

Levanta la app en http://localhost:8766 y abre el navegador. El puerto es FIJO a propósito: el navegador
guarda mapas y corridas por dirección (origen), así que si cambiara el puerto los datos "desaparecerían".

Opciones:
    --puerto N        otro puerto (los datos del puerto 8766 no se ven desde otro)
    --sin-navegador   no abrir el navegador
    --solo-esta-pc    no aceptar conexiones desde el celular u otras PCs de la red
"""
import argparse
import functools
import http.server
import os
import socket
import sys
import threading
import urllib.request
import webbrowser

PUERTO_POR_DEFECTO = 8766
MARCA_APP = b'RCJ Rescue Line offline'


def carpeta_app():
    if getattr(sys, 'frozen', False):  # dentro del .exe de PyInstaller
        return os.path.join(sys._MEIPASS, 'app')
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Manejador(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        '.html': 'text/html; charset=utf-8',
        '.js': 'text/javascript; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.webmanifest': 'application/manifest+json',
    }

    def end_headers(self):
        # Revalidar siempre: después de actualizar la app el navegador no usa JS viejo.
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, formato, *args):
        pass  # ventana limpia


class Servidor(http.server.ThreadingHTTPServer):
    # En Windows SO_REUSEADDR deja que DOS programas escuchen el mismo puerto y se repartan los pedidos.
    # Sin reuse, si el puerto está ocupado falla y lo avisamos.
    allow_reuse_address = False
    daemon_threads = True


def ya_esta_abierta(puerto):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{puerto}/index.html', timeout=1.5) as r:
            return MARCA_APP in r.read(6000)
    except Exception:
        return False


def ip_de_la_red():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))  # no manda nada: solo elige la interfaz de salida
        ip = s.getsockname()[0]
        s.close()
        return None if ip.startswith('127.') else ip
    except Exception:
        return None


def esperar_enter():
    try:
        input('\nApretá Enter para cerrar esta ventana...')
    except EOFError:
        pass


def main():
    ap = argparse.ArgumentParser(description='RCJ Rescue Line offline')
    ap.add_argument('--puerto', type=int, default=PUERTO_POR_DEFECTO)
    ap.add_argument('--sin-navegador', action='store_true')
    ap.add_argument('--solo-esta-pc', action='store_true')
    args = ap.parse_args()

    url = f'http://localhost:{args.puerto}/index.html'

    if ya_esta_abierta(args.puerto):
        print('La app ya estaba abierta en otra ventana. Abro el navegador.')
        if not args.sin_navegador:
            webbrowser.open(url)
        return

    raiz = carpeta_app()
    if not os.path.isfile(os.path.join(raiz, 'index.html')):
        print(f'No encuentro la app en {raiz}.')
        esperar_enter()
        sys.exit(1)

    host = '127.0.0.1' if args.solo_esta_pc else '0.0.0.0'
    try:
        servidor = Servidor((host, args.puerto), functools.partial(Manejador, directory=raiz))
    except OSError as e:
        print(f'No pude usar el puerto {args.puerto}: otro programa lo está usando ({e}).')
        print('Cerrá ese programa (por ejemplo un "python -m http.server" que hayas abierto) y volvé a abrir la app.')
        esperar_enter()
        sys.exit(1)

    print('=' * 64)
    print('  RCJ Rescue Line offline  -  IITA Salta')
    print('=' * 64)
    print(f'  En esta PC:              {url}')
    ip = ip_de_la_red()
    if ip and not args.solo_esta_pc:
        print(f'  Celular / tablet (WiFi): http://{ip}:{args.puerto}/index.html')
        print('  (si Windows pregunta por el firewall, permití "Redes privadas")')
    print()
    print('  Los mapas y corridas se guardan en el navegador de cada dispositivo.')
    print('  Usá siempre el mismo navegador y esta misma dirección.')
    print()
    print('  Para cerrar la app, cerrá esta ventana.')
    print('=' * 64, flush=True)

    if not args.sin_navegador:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == '__main__':
    main()

"""Servidor estático de rcj-line-offline sin caché vieja.

python -m http.server no manda Cache-Control, así que el navegador puede seguir usando JS viejo después
de actualizar la app. Este servidor es igual pero agrega `Cache-Control: no-cache`: el navegador revalida
cada archivo (con Last-Modified responde 304 sin volver a bajarlo si no cambió).

Uso (desde la raíz del repo):
    python tools/rcj-line-offline/herramientas/servir.py            # 0.0.0.0:8766
    python tools/rcj-line-offline/herramientas/servir.py 8080 127.0.0.1
"""
import functools
import http.server
import os
import sys

RAIZ_APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SinCacheVieja(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        '.html': 'text/html; charset=utf-8',
        '.js': 'text/javascript; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.webmanifest': 'application/manifest+json',
    }

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()


def main():
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    host = sys.argv[2] if len(sys.argv) > 2 else '0.0.0.0'
    manejador = functools.partial(SinCacheVieja, directory=RAIZ_APP)
    with http.server.ThreadingHTTPServer((host, puerto), manejador) as servidor:
        print(f'rcj-line-offline en http://{host}:{puerto}/ (carpeta {RAIZ_APP})', flush=True)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()

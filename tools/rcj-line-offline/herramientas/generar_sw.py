"""Genera sw.js: el service worker que deja usar la app sin internet (app instalable / PWA).

Lista todos los archivos que la app necesita en ejecución y calcula una versión con el hash de su contenido.
Cuando la app cambia, la versión cambia, el navegador baja el sw.js nuevo, precarga los archivos nuevos y
borra la caché vieja.

Correr cada vez que se modifique la app (antes de publicar o de armar el .exe):
    python tools/rcj-line-offline/herramientas/generar_sw.py
"""
import hashlib
import json
import os

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETAS = ['components', 'javascripts', 'stylesheets', 'templates', 'images', 'sounds',
            'scoresheet_generation', 'lang', 'data', 'local', 'icons']
EXTENSIONES_EXCLUIDAS = {'.md', '.py'}

PLANTILLA = r"""/* Generado por herramientas/generar_sw.py: no editar a mano. */
'use strict';
const VERSION = '__VERSION__';
const CACHE = 'rcj-line-offline-' + VERSION;
const ARCHIVOS = __ARCHIVOS__;

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    for (let i = 0; i < ARCHIVOS.length; i += 20) {
      await Promise.all(ARCHIVOS.slice(i, i + 20).map(async (archivo) => {
        const respuesta = await fetch(new Request(archivo, { cache: 'reload' }));
        if (!respuesta.ok) throw new Error('No se pudo precargar ' + archivo + ' (' + respuesta.status + ')');
        await cache.put(archivo, respuesta);
      }));
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    for (const clave of await caches.keys()) {
      if (clave.startsWith('rcj-line-offline-') && clave !== CACHE) await caches.delete(clave);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const pedido = event.request;
  if (pedido.method !== 'GET') return;
  if (new URL(pedido.url).origin !== self.location.origin) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    // ignoreSearch: juez.html?run=... y templates/line_editor_modal.html?gs usan el mismo archivo.
    const guardado = await cache.match(pedido, { ignoreSearch: true });
    if (guardado) return guardado;
    try {
      return await fetch(pedido);
    } catch (error) {
      if (pedido.mode === 'navigate') {
        const inicio = await cache.match('index.html');
        if (inicio) return inicio;
      }
      throw error;
    }
  })());
});
"""


def main():
    archivos = []
    for nombre in sorted(os.listdir(APP)):
        ruta = os.path.join(APP, nombre)
        if os.path.isfile(ruta) and (nombre.endswith('.html') or nombre.startswith('LICENSE') or nombre == 'manifest.webmanifest'):
            archivos.append(nombre)
    for carpeta in CARPETAS:
        for raiz, _, nombres in os.walk(os.path.join(APP, carpeta)):
            for nombre in nombres:
                if os.path.splitext(nombre)[1].lower() in EXTENSIONES_EXCLUIDAS:
                    continue
                archivos.append(os.path.relpath(os.path.join(raiz, nombre), APP).replace(os.sep, '/'))
    archivos = sorted(set(archivos))

    hash_total = hashlib.sha256()
    for archivo in archivos:
        hash_total.update(archivo.encode('utf-8'))
        with open(os.path.join(APP, archivo), 'rb') as f:
            hash_total.update(f.read())
    version = hash_total.hexdigest()[:12]

    contenido = PLANTILLA.replace('__VERSION__', version).replace('__ARCHIVOS__', json.dumps(archivos, indent=2, ensure_ascii=False))
    with open(os.path.join(APP, 'sw.js'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(contenido)
    tamano = sum(os.path.getsize(os.path.join(APP, a)) for a in archivos)
    print(f'sw.js generado: versión {version}, {len(archivos)} archivos, {tamano / 1e6:.1f} MB para precargar')


if __name__ == '__main__':
    main()

# App instalable (PWA) y ejecutable para PC (agregados, no son del CMS)

## App instalable

**Archivos:** `manifest.webmanifest`, `icons/` (192, 512 y maskable, generados desde `images/logo.png`),
`sw.js` (generado por `herramientas/generar_sw.py`), `local/pwa.js` y el bloque final de `local/config.js`.

- `local/config.js` inyecta en todas las páginas el `<link rel="manifest">`, el `theme-color` y `local/pwa.js`.
- `local/pwa.js` registra `sw.js` solo en contexto seguro (https o localhost), muestra **Instalar app** en el
  inicio cuando Chrome lo ofrece y avisa con **Hay una versión nueva: recargar** cuando se actualiza.
- `sw.js` precarga los 293 archivos que usa la app (~10,6 MB) y responde desde la caché con `ignoreSearch`
  (`juez.html?run=...`, `templates/line_editor_modal.html?gs`). La versión es un hash del contenido: si la app
  cambia, cambia `sw.js` y el navegador baja la versión nueva y borra la vieja.
- **Después de cualquier cambio en la app hay que correr `herramientas/generar_sw.py`** (el workflow de GitHub
  Pages lo corre solo antes de publicar).

## Ejecutable para PC

**Archivos:** `herramientas/lanzador.py`, `herramientas/construir_exe.py`, `herramientas/servir.py`.

- PyInstaller `--onefile` con la app en `app/`. Puerto fijo 8766 (los datos del navegador dependen del origen).
- Servidor sin `SO_REUSEADDR` (en Windows dejaría a dos programas escuchar el mismo puerto) y con
  `Cache-Control: no-cache` para no quedar con JS viejo después de actualizar.
- Si la app ya está abierta en el puerto, solo abre el navegador.

## Verificación (13-sep-2026)

- Service worker activo y controlando la página en `localhost:8766`: 293/293 archivos en caché, 0 fallos.
- `.exe`: sirve las páginas y librerías (200), no incluye `tests/`, detecta la app ya abierta.

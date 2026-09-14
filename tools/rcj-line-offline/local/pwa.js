/*
 * rcj-line-offline — app instalable (PWA). NUEVO, no es del CMS.
 * - Registra sw.js (herramientas/generar_sw.py) para que la app funcione sin internet.
 * - En el inicio muestra el botón "Instalar app" cuando el navegador lo permite (Chrome / Android).
 * - Avisa cuando se descargó una versión nueva de la app.
 * El modo offline solo existe en contexto seguro (https o localhost); por http con la IP de la WiFi no.
 */
(function () {
  'use strict';

  var R = window.RCJLocal || {};
  var base = R.base || './';

  function boton(id, texto, estilo, accion) {
    var b = document.createElement('button');
    b.id = id;
    b.type = 'button';
    b.textContent = texto;
    b.style.cssText = 'position:fixed;z-index:100001;border:0;border-radius:24px;padding:10px 18px;' +
      'font:600 15px/1.2 system-ui,sans-serif;box-shadow:0 4px 12px rgba(0,0,0,.3);cursor:pointer;' + estilo;
    b.addEventListener('click', accion);
    document.body.appendChild(b);
    return b;
  }

  function enInicio() {
    return /(^|\/)(index\.html)?$/.test(location.pathname);
  }

  // ------------------------------------------------------------------ instalar
  var promptInstalacion = null;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    promptInstalacion = e;
    if (!enInicio() || document.getElementById('rcj-instalar')) return;
    boton('rcj-instalar', '⬇ Instalar app', 'left:12px;bottom:12px;background:#16a34a;color:#fff;', function () {
      var b = document.getElementById('rcj-instalar');
      if (b) b.parentNode.removeChild(b);
      if (promptInstalacion) {
        promptInstalacion.prompt();
        promptInstalacion = null;
      }
    });
  });
  window.addEventListener('appinstalled', function () {
    var b = document.getElementById('rcj-instalar');
    if (b) b.parentNode.removeChild(b);
  });

  // ------------------------------------------------------------------ modo offline
  if (!('serviceWorker' in navigator) || !window.isSecureContext) return;

  var habiaControlador = !!navigator.serviceWorker.controller;
  navigator.serviceWorker.addEventListener('controllerchange', function () {
    if (!habiaControlador) {
      habiaControlador = true; // primera instalación: no hace falta recargar
      return;
    }
    if (document.getElementById('rcj-actualizar')) return;
    boton('rcj-actualizar', '↻ Hay una versión nueva: recargar', 'right:12px;bottom:12px;background:#2563eb;color:#fff;', function () {
      location.reload();
    });
  });

  function registrar() {
    navigator.serviceWorker.register(base + 'sw.js').catch(function (e) {
      console.warn('[pwa] no se pudo registrar el modo offline:', e);
    });
  }
  if (document.readyState === 'complete') registrar();
  else window.addEventListener('load', registrar);
})();

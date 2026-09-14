/*
 * rcj-line-offline — área editor. Script SOLO DE PRUEBA que el servidor de tests/editor-correr.py inyecta en
 * editor.html justo después de <meta charset="utf-8"> (la página publicada no lo carga).
 *
 *  - Junta errores de la página (window.onerror, recursos que no cargan, unhandledrejection, console.error) en
 *    window.__errores y los console.warn en window.__avisos, para que la página de prueba (padre del iframe) los lea.
 *  - Intercepta las descargas (<a download>.click()) y window.open: guarda {href, download} / {url, destino} en
 *    window.__descargas / window.__ventanas en lugar de descargar o abrir otra pestaña.
 *  - ?__latido=N (solo en la ventana de arriba, para las capturas): mantiene N pedidos /__latido pendientes en fila
 *    (~250 ms reales cada uno) para que Edge headless no avance el tiempo virtual mientras trabaja IndexedDB.
 *  - ?__modal=x,y (capturas): cuando el editor terminó de cargar, abre el modal de propiedades de esa baldosa.
 */
(function () {
  'use strict';
  var errores = window.__errores = [];
  var avisos = window.__avisos = [];
  window.__descargas = [];
  window.__ventanas = [];

  function texto(a) {
    if (a && a.stack) return String(a.stack);
    if (a !== null && typeof a === 'object') {
      try { return JSON.stringify(a); } catch (e) { return String(a); }
    }
    return String(a);
  }

  window.addEventListener('error', function (e) {
    var t = e.target;
    if (t && t !== window && (t.src || t.href)) {
      errores.push('recurso no cargó: ' + (t.src || t.href));
      return;
    }
    errores.push('onerror: ' + (e.message || e.type) + (e.filename ? ' @' + e.filename + ':' + e.lineno : ''));
  }, true);
  window.addEventListener('unhandledrejection', function (e) {
    var r = e.reason;
    errores.push('unhandledrejection: ' + ((r && (r.stack || r.message)) || texto(r)));
  });
  var errorOriginal = console.error;
  console.error = function () {
    errores.push('console.error: ' + Array.prototype.map.call(arguments, texto).join(' ').slice(0, 1500));
    return errorOriginal.apply(console, arguments);
  };
  var avisoOriginal = console.warn;
  console.warn = function () {
    avisos.push(Array.prototype.map.call(arguments, texto).join(' ').slice(0, 500));
    return avisoOriginal.apply(console, arguments);
  };

  var clickOriginal = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function () {
    if (this.hasAttribute('download')) {
      window.__descargas.push({ href: this.getAttribute('href'), download: this.getAttribute('download') });
      return;
    }
    return clickOriginal.apply(this, arguments);
  };
  window.open = function (url, destino) {
    window.__ventanas.push({ url: String(url), destino: destino });
    return null;
  };

  // Edge headless con --virtual-time-budget no entrega cuadros de forma confiable (sobre todo dentro de un iframe):
  // ngAnimate / $animateCss de ui-bootstrap esperan requestAnimationFrame y los modales quedaban a mitad del fundido.
  // requestAnimationFrame con respaldo por setTimeout (lo que llegue primero, una sola vez) y scroll sin animación
  // (centerMap usa behavior:'smooth', que tampoco avanza). Solo en la prueba: la página publicada no carga este archivo.
  var rafNativo = window.requestAnimationFrame.bind(window);
  var cafNativo = window.cancelAnimationFrame.bind(window);
  var siguienteRaf = 1;
  var rafPendientes = {};
  window.requestAnimationFrame = function (cb) {
    var id = siguienteRaf++;
    var p = rafPendientes[id] = { hecho: false };
    function correr(t) {
      if (p.hecho) return;
      p.hecho = true;
      delete rafPendientes[id];
      clearTimeout(p.to);
      cafNativo(p.raf);
      cb(typeof t === 'number' ? t : performance.now());
    }
    p.raf = rafNativo(correr);
    p.to = setTimeout(correr, 34);
    return id;
  };
  window.cancelAnimationFrame = function (id) {
    var p = rafPendientes[id];
    if (!p) return;
    p.hecho = true;
    clearTimeout(p.to);
    cafNativo(p.raf);
    delete rafPendientes[id];
  };
  function sinSuave(original) {
    // Pasa EXACTAMENTE los argumentos recibidos: scrollTo(obj, undefined) se interpreta como scrollTo(x, y) y
    // manda el scroll a 0,0 (eso rompía centerMap en las pruebas).
    return function (a) {
      var args = Array.prototype.slice.call(arguments);
      if (a && typeof a === 'object' && a.behavior === 'smooth') args[0] = Object.assign({}, a, { behavior: 'auto' });
      return original.apply(this, args);
    };
  }
  Element.prototype.scrollTo = sinSuave(Element.prototype.scrollTo);
  window.scrollTo = sinSuave(window.scrollTo);

  // Transiciones CSS y scroll suave tampoco avanzan sin cuadros: el fundido del modal de Bootstrap quedaba en
  // translateY(-26..-50px) y #map-container (scroll-behavior: smooth en line_modern.css) no llegaba a centrar.
  var estiloPrueba = document.createElement('style');
  estiloPrueba.id = 'rcj-prueba-sin-transiciones';
  estiloPrueba.textContent = '*, *::before, *::after { transition-duration: 0s !important; transition-delay: 0s !important;' +
    ' animation-duration: 0s !important; animation-delay: 0s !important; scroll-behavior: auto !important; }';
  (document.head || document.documentElement).appendChild(estiloPrueba);

  var mL = /[?&]__latido=(\d+)/.exec(location.search);
  if (mL && window.top === window) {
    var vueltas = Math.max(1, Math.round(Math.min(+mL[1], 60000) / 250));
    (async function () {
      for (var i = 0; i < vueltas; i++) {
        try {
          var r = await fetch('/__latido?ms=250', { cache: 'no-store' });
          if (r.status !== 204) break;
        } catch (e) { break; }
        // capturas: volver a centrar el mapa con la función del propio editor (Reset View) mientras carga
        if (i % 4 === 3 && window.angular && document.body) {
          try {
            var sc = window.angular.element(document.body).scope();
            if (sc && typeof sc.centerMap === 'function') sc.centerMap();
          } catch (e) { /* sin editor todavía */ }
        }
      }
    })();
  }

  var mM = /[?&]__modal=(\d+),(\d+)/.exec(location.search);
  if (mM) {
    var intentos = 0;
    (function esperar() {
      var s = window.angular && document.body && window.angular.element(document.body).scope();
      var listo = s && s.tileSet && s.tiles && s.tiles[mM[1] + ',' + mM[2] + ',' + (s.z || 0)] &&
        document.querySelectorAll('tile img.tile-image').length > 0;
      if (!listo) {
        if (++intentos < 400) setTimeout(esperar, 50);
        return;
      }
      setTimeout(function () { s.$apply(function () { s.open(+mM[1], +mM[2]); }); }, 800);
    })();
  }
})();

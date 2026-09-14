/*
 * rcj-line-offline — área estadísticas. Ayudas de las páginas tests/estadisticas-*.html
 * (mismo patrón que tests/admin-comun.js, copiado para no depender de archivos de otra área).
 * - Captura window.onerror, unhandledrejection y console.error de la página de prueba y de cada iframe.
 * - Latido: mantiene un fetch a /__latido pendiente mientras la prueba corre, así Edge headless con
 *   --virtual-time-budget no vuelca el DOM antes de que termine IndexedDB (ver tests/estadisticas-correr.py).
 * - Escribe el resultado en <pre id="resultado">JSON</pre> (y opcionalmente lo manda por POST).
 * Cargar ANTES que los scripts de la app.
 */
(function () {
  'use strict';

  var errores = [];

  function textoArg(a) {
    if (a && a.stack) return a.stack;
    if (a !== null && typeof a === 'object') {
      try { return JSON.stringify(a); } catch (e) { return String(a); }
    }
    return String(a);
  }

  function engancharErrores(w, prefijo) {
    if (!w || w.__estDoc === w.document) return;
    try {
      w.__estDoc = w.document;
      w.addEventListener('error', function (e) {
        errores.push(prefijo + 'onerror: ' + (e.message || e.type) + (e.filename ? ' @' + e.filename + ':' + e.lineno : ''));
      });
      w.addEventListener('unhandledrejection', function (e) {
        var r = e.reason;
        errores.push(prefijo + 'unhandledrejection: ' + ((r && (r.stack || r.message)) || r));
      });
      var original = w.console.error;
      w.console.error = function () {
        errores.push(prefijo + 'console.error: ' + Array.prototype.map.call(arguments, textoArg).join(' ').slice(0, 1500));
        return original.apply(w.console, arguments);
      };
    } catch (e) { /* otro origen */ }
  }
  engancharErrores(window, '');

  var latiendo = true;
  (async function latir() {
    while (latiendo) {
      try {
        var r = await fetch('/__latido?ms=50', { cache: 'no-store' });
        if (r.status !== 204) break;
      } catch (e) { break; }
    }
  })();

  function esperar(ms) { return new Promise(function (res) { setTimeout(res, ms); }); }

  var T = window.T = {
    checks: [],
    pasos: [],
    paso: function (nombre) { this.pasos.push(nombre); },
    check: function (nombre, cond, detalle) {
      var c = { nombre: nombre, ok: !!cond };
      if (!cond && detalle !== undefined) c.detalle = detalle;
      this.checks.push(c);
      return !!cond;
    },
    igual: function (nombre, obtenido, esperado) {
      var ok = JSON.stringify(obtenido) === JSON.stringify(esperado);
      var c = { nombre: nombre, ok: ok };
      if (!ok) { c.obtenido = obtenido; c.esperado = esperado; }
      this.checks.push(c);
      return ok;
    },
    /** Compara números con tolerancia (por defecto 1e-9). */
    cerca: function (nombre, obtenido, esperado, tol) {
      var ok = typeof obtenido === 'number' && Math.abs(obtenido - esperado) <= (tol == null ? 1e-9 : tol);
      var c = { nombre: nombre, ok: ok };
      if (!ok) { c.obtenido = obtenido; c.esperado = esperado; }
      this.checks.push(c);
      return ok;
    },
    esperar: esperar,
    esperarQue: async function (fn, ms, que) {
      var limite = Date.now() + (ms || 15000);
      var ultimo;
      while (Date.now() < limite) {
        try {
          ultimo = fn();
          if (ultimo) return ultimo;
        } catch (e) { ultimo = e; }
        await esperar(50);
      }
      throw new Error('timeout esperando: ' + (que || fn.toString().slice(0, 120)) + (ultimo instanceof Error ? ' (' + ultimo.message + ')' : ''));
    },
    api: function (metodo, url, cuerpo) { return window.RCJLocal.api.request(metodo, url, cuerpo); },
    resetear: async function () {
      var cols = window.RCJLocal.store.colecciones;
      for (var i = 0; i < cols.length; i++) await window.RCJLocal.store.clear(cols[i]);
    },
    cargarIframe: async function (url, opciones) {
      opciones = opciones || {};
      var f = document.createElement('iframe');
      f.style.width = (opciones.ancho || 1024) + 'px';
      f.style.height = (opciones.alto || 768) + 'px';
      f.style.border = '0';
      f.style.display = 'block';
      (opciones.contenedor || document.getElementById('marcos') || document.body).appendChild(f);
      var docAnterior = f.contentDocument;
      f.src = url;
      await T.esperarQue(function () {
        var d = f.contentDocument, v = f.contentWindow;
        if (!d || d === docAnterior || v.location.href === 'about:blank') return false;
        engancharErrores(v, '[' + v.location.pathname.split('/').pop() + '] ');
        return true;
      }, 20000, 'navegación del iframe');
      await T.esperarQue(function () { return f.contentWindow.document.readyState === 'complete'; }, 20000, 'carga de ' + url);
      return f;
    },
    scope: function (f, selector) {
      var w = f.contentWindow;
      var el = selector ? w.document.querySelector(selector) : w.document.body;
      return w.angular.element(el).scope();
    },
    terminar: function (extra) {
      var fallas = this.checks.filter(function (c) { return !c.ok; });
      var res = {
        ok: fallas.length === 0 && errores.length === 0 && this.checks.length > 0,
        total: this.checks.length,
        fallas: fallas,
        errores: errores,
        pasos: this.pasos,
        verificaciones: this.checks.map(function (c) { return (c.ok ? 'OK    ' : 'FALLA ') + c.nombre; })
      };
      if (extra) res.extra = extra;
      document.getElementById('resultado').textContent = JSON.stringify(res);
      var fin = function () { latiendo = false; };
      if (typeof T.alTerminar === 'function') Promise.resolve().then(function () { return T.alTerminar(res); }).then(fin, fin);
      else fin();
    },
    correr: function (fn) {
      var self = this;
      Promise.resolve().then(fn).then(function (extra) { self.terminar(extra); }, function (e) {
        errores.push('excepción de la prueba (último paso: ' + self.pasos[self.pasos.length - 1] + '): ' + ((e && e.stack) || e));
        self.terminar();
      });
    }
  };
})();

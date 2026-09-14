/*
 * rcj-line-offline — área backend. Ayudas comunes de las páginas tests/backend-*.html.
 * Captura window.onerror, unhandledrejection y console.error; junta verificaciones y escribe el
 * resultado en <pre id="resultado">JSON</pre> para leerlo con --dump-dom.
 * Cargar ANTES que los scripts de la app para capturar errores de sintaxis.
 */
(function () {
  'use strict';

  var errores = [];
  var ignorados = [];
  window.__errores = errores;

  function textoArg(a) {
    if (a && a.stack) return a.stack;
    if (a !== null && typeof a === 'object') {
      try { return JSON.stringify(a); } catch (e) { return String(a); }
    }
    return String(a);
  }
  function registrar(txt) {
    for (var i = 0; i < ignorados.length; i++) {
      if (ignorados[i].test(txt)) { T.erroresIgnorados.push(txt.slice(0, 300)); return; }
    }
    errores.push(txt);
  }

  window.addEventListener('error', function (e) {
    registrar('onerror: ' + (e.message || e.type) + (e.filename ? ' @' + e.filename + ':' + e.lineno : ''));
  });
  window.addEventListener('unhandledrejection', function (e) {
    var r = e.reason;
    registrar('unhandledrejection: ' + ((r && (r.stack || r.message)) || r));
  });
  var errorOriginal = console.error;
  console.error = function () {
    registrar('console.error: ' + Array.prototype.map.call(arguments, textoArg).join(' '));
    return errorOriginal.apply(console, arguments);
  };

  // Latido: mantiene un pedido de red pendiente mientras la prueba corre (ver tests/backend-correr.py).
  // Con --virtual-time-budget, Edge headless no avanza el tiempo virtual con pedidos pendientes, así que
  // el --dump-dom espera a que terminen las operaciones de IndexedDB. Sin el endpoint (404) se detiene.
  var latiendo = true;
  (async function latir() {
    while (latiendo) {
      try {
        var r = await fetch('/__latido?ms=200', { cache: 'no-store' });
        if (r.status !== 204) break;
      } catch (e) {
        break;
      }
    }
  })();

  var T = window.T = {
    checks: [],
    erroresIgnorados: [],
    ignorarErrores: function (re) { ignorados.push(re); },
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
    api: function (metodo, url, cuerpo) { return window.RCJLocal.api.request(metodo, url, cuerpo); },
    resetear: async function () {
      var cols = window.RCJLocal.store.colecciones;
      for (var i = 0; i < cols.length; i++) await window.RCJLocal.store.clear(cols[i]);
    },
    fixture: async function (nombre) {
      var r = await fetch('backend-fixtures/' + nombre, { cache: 'no-cache' });
      if (!r.ok) throw new Error('fixture ' + nombre + ' HTTP ' + r.status);
      return r.json();
    },
    esperar: function (ms) { return new Promise(function (res) { setTimeout(res, ms); }); },
    terminar: function (extra) {
      var fallas = this.checks.filter(function (c) { return !c.ok; });
      var res = {
        ok: fallas.length === 0 && errores.length === 0 && this.checks.length > 0,
        total: this.checks.length,
        fallas: fallas,
        errores: errores,
        erroresIgnorados: this.erroresIgnorados,
        verificaciones: this.checks.map(function (c) { return (c.ok ? 'OK    ' : 'FALLA ') + c.nombre; })
      };
      if (extra) res.extra = extra;
      document.getElementById('resultado').textContent = JSON.stringify(res);
      latiendo = false;
    },
    correr: function (fn) {
      var self = this;
      Promise.resolve().then(fn).then(function (extra) { self.terminar(extra); }, function (e) {
        errores.push('excepción de la prueba: ' + ((e && e.stack) || e));
        self.terminar();
      });
    }
  };
})();

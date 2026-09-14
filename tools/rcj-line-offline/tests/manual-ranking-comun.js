/*
 * rcj-line-offline — área manual-ranking. Ayudas comunes de las páginas tests/manual-ranking-*.html.
 *
 * - Captura window.onerror, unhandledrejection y console.error de la página de prueba y de los
 *   iframes que se abran con T.abrirIframe (se engancha en cuanto el documento del iframe existe y
 *   otra vez en su evento load; los errores anteriores al enganche los levanta el runner leyendo la
 *   consola de Edge con --enable-logging=stderr).
 * - Latido (/__latido) mientras la prueba corre: con --virtual-time-budget, Edge headless no avanza
 *   el tiempo virtual con pedidos de red pendientes y el --dump-dom espera a IndexedDB.
 * - Junta verificaciones y escribe <pre id="resultado">JSON</pre>.
 * Cargar ANTES que los scripts de la app.
 */
(function () {
  'use strict';

  var errores = [];
  var ignorados = [];

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
    errores.push(txt.slice(0, 2000));
  }

  function engancharErrores(win, etiqueta) {
    if (!win || win.__mrEnganchado) return;
    try {
      win.__mrEnganchado = true;
      win.addEventListener('error', function (e) {
        registrar('[' + etiqueta + '] onerror: ' + (e.message || e.type) + (e.filename ? ' @' + e.filename + ':' + e.lineno : ''));
      });
      win.addEventListener('unhandledrejection', function (e) {
        var r = e.reason;
        registrar('[' + etiqueta + '] unhandledrejection: ' + ((r && (r.stack || r.message)) || r));
      });
      var orig = win.console.error;
      win.console.error = function () {
        registrar('[' + etiqueta + '] console.error: ' + Array.prototype.map.call(arguments, textoArg).join(' '));
        return orig.apply(win.console, arguments);
      };
    } catch (e) { /* otro origen: no se puede */ }
  }
  engancharErrores(window, 'prueba');

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
    notas: {},
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
    // Espera hasta que fn() devuelva algo truthy (o lanza al vencer el plazo)
    esperarQue: async function (descripcion, fn, plazoMs) {
      var limite = Date.now() + (plazoMs || 15000);
      var ultimoError;
      while (Date.now() < limite) {
        try {
          var v = fn();
          if (v) return v;
        } catch (e) { ultimoError = e; }
        await this.esperar(50);
      }
      throw new Error('Plazo vencido esperando: ' + descripcion + (ultimoError ? ' (' + ultimoError + ')' : ''));
    },
    // Abre (o reutiliza) un iframe y espera a que cargue la URL. Engancha la captura de errores.
    abrirIframe: function (id, url, ancho, alto) {
      var f = document.getElementById(id);
      if (!f) {
        f = document.createElement('iframe');
        f.id = id;
        document.body.appendChild(f);
      }
      f.style.width = ancho || '1366px';
      f.style.height = alto || '900px';
      f.style.border = '0';
      return new Promise(function (res, rej) {
        var vigilante = setInterval(function () {
          try {
            var w = f.contentWindow;
            if (w && w.location && w.location.href !== 'about:blank') engancharErrores(w, id);
          } catch (e) { /* navegando */ }
        }, 0);
        var plazo = setTimeout(function () { clearInterval(vigilante); rej(new Error('Plazo vencido abriendo ' + url)); }, 30000);
        f.onload = function () {
          clearInterval(vigilante);
          clearTimeout(plazo);
          engancharErrores(f.contentWindow, id);
          res(f);
        };
        f.src = url;
      });
    },
    // Espera la próxima carga (navegación) de un iframe ya abierto (con plazo, para que un fallo no cuelgue la prueba)
    esperarCarga: function (f, plazoMs) {
      return new Promise(function (res, rej) {
        var plazo = setTimeout(function () { rej(new Error('Plazo vencido esperando la navegación del iframe ' + f.id + ' (sigue en ' + f.contentWindow.location.href + ')')); }, plazoMs || 20000);
        f.onload = function () { clearTimeout(plazo); engancharErrores(f.contentWindow, f.id); res(f); };
      });
    },
    // Scope del body de un iframe con Angular
    scope: function (f) {
      var w = f.contentWindow;
      return w.angular.element(w.document.body).scope();
    },
    // Dispara un clic real (evento DOM) sobre un elemento
    clic: function (el) {
      if (!el) throw new Error('clic: elemento inexistente');
      el.dispatchEvent(new el.ownerDocument.defaultView.MouseEvent('click', { bubbles: true, cancelable: true }));
    },
    dobleClic: function (el) {
      if (!el) throw new Error('dobleClic: elemento inexistente');
      el.dispatchEvent(new el.ownerDocument.defaultView.MouseEvent('dblclick', { bubbles: true, cancelable: true }));
    },
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

/*
 * rcj-line-offline — área admin. Ayudas de las páginas tests/admin-*.html.
 * - Captura window.onerror, unhandledrejection y console.error de la página de prueba y de cada
 *   iframe que se abre con T.cargarIframe / T.navegar / T.esperarNavegacion.
 * - Latido: mantiene un fetch a /__latido pendiente mientras la prueba corre, así Edge headless con
 *   --virtual-time-budget no vuelca el DOM (ni saca la captura) antes de que termine IndexedDB
 *   (ver tests/admin-correr.py).
 * - Escribe el resultado en <pre id="resultado">JSON</pre>.
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
    errores.push(txt.slice(0, 1500));
  }

  function engancharErrores(w, prefijo) {
    // la marca va atada al documento: la ventana about:blank inicial de un iframe se reutiliza
    if (!w || w.__adminDoc === w.document) return;
    try {
      w.__adminDoc = w.document;
      w.addEventListener('error', function (e) {
        registrar(prefijo + 'onerror: ' + (e.message || e.type) + (e.filename ? ' @' + e.filename + ':' + e.lineno : ''));
      });
      w.addEventListener('unhandledrejection', function (e) {
        var r = e.reason;
        registrar(prefijo + 'unhandledrejection: ' + ((r && (r.stack || r.message)) || r));
      });
      var original = w.console.error;
      w.console.error = function () {
        registrar(prefijo + 'console.error: ' + Array.prototype.map.call(arguments, textoArg).join(' '));
        return original.apply(w.console, arguments);
      };
    } catch (e) { /* ventana de otro origen */ }
  }
  engancharErrores(window, '');

  var latiendo = true;
  (async function latir() {
    while (latiendo) {
      try {
        var r = await fetch('/__latido?ms=50', { cache: 'no-store' });
        if (r.status !== 204) break;
      } catch (e) {
        break;
      }
    }
  })();

  function esperar(ms) { return new Promise(function (res) { setTimeout(res, ms); }); }

  var T = window.T = {
    checks: [],
    erroresIgnorados: [],
    pasos: [],
    ignorarErrores: function (re) { ignorados.push(re); },
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
    sha256: async function (texto) {
      var buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(texto));
      return Array.prototype.map.call(new Uint8Array(buf), function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
    },

    // ------------------------------------------------------------ iframes
    cargarIframe: async function (url, opciones) {
      opciones = opciones || {};
      var f = document.createElement('iframe');
      f.style.width = (opciones.ancho || 1024) + 'px';
      f.style.height = (opciones.alto || 768) + 'px';
      f.style.border = '0';
      f.style.display = 'block';
      (opciones.contenedor || document.getElementById('marcos') || document.body).appendChild(f);
      f.__nombre = opciones.nombre || url;
      await T.navegar(f, url);
      return f;
    },
    /** Navega el iframe a url y espera la carga completa (enganchando errores lo antes posible). */
    navegar: async function (f, url) {
      var docAnterior = f.contentDocument;
      f.src = url;
      return T.esperarNavegacion(f, null, docAnterior);
    },
    /**
     * Espera que el iframe tenga un documento distinto de docAnterior (capturarlo ANTES de disparar la
     * navegación), opcionalmente con href que cumpla re, y que termine de cargar.
     */
    esperarNavegacion: async function (f, re, docAnterior) {
      var w = await T.esperarQue(function () {
        var d = f.contentDocument;
        var v = f.contentWindow;
        if (!d || d === docAnterior) return false;
        var href = v.location.href;
        if (href === 'about:blank') return false;
        if (re && !re.test(href)) return false;
        engancharErrores(v, '[' + v.location.pathname.split('/').pop() + '] ');
        return v;
      }, 20000, 'navegación del iframe' + (re ? ' a ' + re : ''));
      await T.esperarQue(function () { return w.document.readyState === 'complete'; }, 20000, 'carga de ' + w.location.href);
      return w;
    },
    scope: function (f, selector) {
      var w = f.contentWindow;
      var el = selector ? w.document.querySelector(selector) : w.document.body;
      return w.angular.element(el).scope();
    },
    aplicar: function (scope, fn) {
      var r;
      scope.$apply(function () { r = fn(); });
      return r;
    },
    /** Espera que no queden pedidos $http pendientes en la página del iframe. */
    esperarHttp: async function (f, ms) {
      await T.esperarQue(function () {
        var w = f.contentWindow;
        var inj = w.angular && w.angular.element(w.document.body).injector();
        return inj && inj.get('$http').pendingRequests.length === 0;
      }, ms || 15000, '$http inactivo');
    },
    /** SweetAlert2 visible en el iframe con un título que contenga `texto` (o cualquiera si no se indica). */
    esperarSwal: async function (f, texto, ms) {
      return T.esperarQue(function () {
        var w = f.contentWindow;
        var s = w.swal || w.Swal;
        if (!s || !s.isVisible()) return false;
        var t = s.getTitle();
        var titulo = t ? t.textContent : '';
        if (texto && titulo.indexOf(texto) < 0) return false;
        return titulo || true;
      }, ms || 10000, 'swal ' + (texto || ''));
    },
    confirmarSwal: function (f, valorInput) {
      var w = f.contentWindow;
      var s = w.swal || w.Swal;
      if (valorInput !== undefined) {
        var inp = s.getInput();
        inp.value = valorInput;
        inp.dispatchEvent(new w.Event('input', { bubbles: true }));
      }
      s.clickConfirm();
    },
    /** Pone archivos en un <input type=file> del iframe (DataTransfer sintético) y dispara change. */
    ponerArchivos: function (f, selector, archivos) {
      var w = f.contentWindow;
      var input = w.document.querySelector(selector);
      if (!input) throw new Error('no existe ' + selector);
      var dt = new w.DataTransfer();
      archivos.forEach(function (a) {
        dt.items.add(new w.File([a.texto], a.nombre, { type: a.tipo || 'application/json' }));
      });
      input.files = dt.files;
      input.dispatchEvent(new w.Event('change', { bubbles: true }));
    },
    clic: function (f, selector) {
      var el = f.contentWindow.document.querySelector(selector);
      if (!el) throw new Error('no existe ' + selector);
      el.click();
      return el;
    },

    terminar: function (extra) {
      var fallas = this.checks.filter(function (c) { return !c.ok; });
      var res = {
        ok: fallas.length === 0 && errores.length === 0 && this.checks.length > 0,
        total: this.checks.length,
        fallas: fallas,
        errores: errores,
        erroresIgnorados: this.erroresIgnorados,
        pasos: this.pasos,
        verificaciones: this.checks.map(function (c) { return (c.ok ? 'OK    ' : 'FALLA ') + c.nombre; })
      };
      if (extra) res.extra = extra;
      document.getElementById('resultado').textContent = JSON.stringify(res);
      var fin = function () { latiendo = false; };
      // T.alTerminar(res) opcional (p. ej. POST del resultado cuando la corrida es --screenshot)
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

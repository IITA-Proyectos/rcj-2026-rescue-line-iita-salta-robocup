/*
 * rcj-line-offline — área editor. Ayudas comunes de las páginas tests/editor-*.html.
 * Mismo patrón que tests/backend-comun.js (errores capturados, latido, <pre id="resultado">JSON</pre>) más
 * ayudas para manejar editor.html dentro de un iframe del mismo origen: abrirlo, esperar a Angular, importar un
 * archivo por el MISMO input #select, leer descargas interceptadas y juntar los errores de consola del editor
 * (los captura tests/editor-captura.js, que el servidor de pruebas inyecta en editor.html).
 * Cargar ANTES que los scripts de la app.
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
      if (ignorados[i].test(txt)) { T.erroresIgnorados.push(txt.slice(0, 400)); return; }
    }
    errores.push(txt);
  }

  window.addEventListener('error', function (e) {
    registrar('prueba onerror: ' + (e.message || e.type) + (e.filename ? ' @' + e.filename + ':' + e.lineno : ''));
  });
  window.addEventListener('unhandledrejection', function (e) {
    var r = e.reason;
    registrar('prueba unhandledrejection: ' + ((r && (r.stack || r.message)) || r));
  });
  var errorOriginal = console.error;
  console.error = function () {
    registrar('prueba console.error: ' + Array.prototype.map.call(arguments, textoArg).join(' '));
    return errorOriginal.apply(console, arguments);
  };

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

  var SHA_FIXTURE = 'df7986072ce370a1c5347ce76b2f4eacb8e9bf9de228cff0932652834de1251e';

  var T = window.T = {
    SHA_FIXTURE: SHA_FIXTURE,
    checks: [],
    erroresIgnorados: [],
    avisosEditor: [],
    animaciones: [],
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
    /** Verificación que espera (hasta ms) a que la condición se cumpla: para clases que ngAnimate cambia en diferido. */
    checkEsperando: async function (nombre, cond, ms, detalle) {
      var ok = false;
      try { await T.esperarQue(nombre, cond, ms || 4000); ok = true; } catch (e) { /* queda en falla */ }
      return T.check(nombre, ok, ok ? undefined : (typeof detalle === 'function' ? detalle() : detalle));
    },
    api: function (metodo, url, cuerpo) { return window.RCJLocal.api.request(metodo, url, cuerpo); },
    resetear: async function () {
      var cols = window.RCJLocal.store.colecciones;
      for (var i = 0; i < cols.length; i++) await window.RCJLocal.store.clear(cols[i]);
    },
    textoFixture: async function (nombre) {
      var r = await fetch('editor-fixtures/' + nombre, { cache: 'no-cache' });
      if (!r.ok) throw new Error('fixture ' + nombre + ' HTTP ' + r.status);
      return r.text();
    },
    sha256: async function (texto) {
      var buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(texto));
      return Array.prototype.map.call(new Uint8Array(buf), function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
    },
    esperar: function (ms) { return new Promise(function (res) { setTimeout(res, ms); }); },
    esperarQue: async function (nombre, cond, ms) {
      var hasta = Date.now() + (ms || 15000);
      while (Date.now() < hasta) {
        var v;
        try { v = cond(); } catch (e) { v = false; }
        if (v) return v;
        await T.esperar(40);
      }
      throw new Error('tiempo agotado esperando: ' + nombre);
    },

    // ---------------------------------------------------------------- editor en iframe
    iframe: null,
    /** Crea (o reutiliza) el iframe del editor con el tamaño pedido. */
    marco: function (ancho, alto) {
      var f = document.getElementById('editor');
      if (!f) {
        f = document.createElement('iframe');
        f.id = 'editor';
        f.style.border = '0';
        // visible desde (0,0): un iframe fuera de la vista puede quedar sin requestAnimationFrame
        f.style.position = 'fixed';
        f.style.left = '0';
        f.style.top = '0';
        f.style.zIndex = '10';
        document.body.appendChild(f);
      }
      f.style.width = (ancho || 1366) + 'px';
      f.style.height = (alto || 900) + 'px';
      T.iframe = f;
      return f;
    },
    /** Junta los errores y avisos de la ventana del editor (antes de navegar o al final). */
    recoger: function (win, etiqueta) {
      if (!win || win.__recogido) return;
      win.__recogido = true;
      (win.__errores || []).forEach(function (e) { registrar('editor[' + etiqueta + '] ' + e); });
      (win.__avisos || []).forEach(function (a) { T.avisosEditor.push('[' + etiqueta + '] ' + a); });
    },
    /** Espera a que el editor dentro del iframe tenga Angular arrancado, tilesets y (con ?map=) el mapa cargado. */
    esperarEditor: async function (f, etiqueta) {
      var win;
      await T.esperarQue('editor listo (' + etiqueta + ')', function () {
        win = f.contentWindow;
        if (!win || !win.angular || !win.document || win.document.readyState !== 'complete') return false;
        var s = win.angular.element(win.document.body).scope();
        if (!s || !s.tileSet || typeof s.copySelection !== 'function') return false;
        var inj = win.angular.element(win.document.body).injector();
        if (inj.get('$http').pendingRequests.length) return false;
        if (win.mapId && !s.competition) return false;
        return win.document.querySelectorAll('td.slot').length === (s.width || 0) * (s.length || 0);
      }, 30000);
      await T.esperar(150);
      var s = win.angular.element(win.document.body).scope();
      // Las animaciones quedan ENCENDIDAS: editor-captura.js (inyectado) da requestAnimationFrame con respaldo por
      // setTimeout, así ngAnimate y los modales de ui-bootstrap terminan también en Edge headless.
      T.animaciones.push(etiqueta + ': $animate.enabled() = ' + win.angular.element(win.document.body).injector().get('$animate').enabled());
      return { win: win, doc: win.document, scope: s, etiqueta: etiqueta };
    },
    abrirEditor: async function (query, etiqueta, ancho, alto) {
      var f = T.marco(ancho, alto);
      if (f.contentWindow && f.contentWindow.__errores) T.recoger(f.contentWindow, T._etiquetaActual || '?');
      T._etiquetaActual = etiqueta;
      var cargado = new Promise(function (res) { f.addEventListener('load', res, { once: true }); });
      f.src = '../editor.html' + (query ? '?' + query : '');
      await cargado;
      return T.esperarEditor(f, etiqueta);
    },
    /** Ejecuta accion() (que navega el iframe) y espera el editor nuevo. */
    tras_navegar: async function (accion, etiqueta) {
      var f = T.iframe;
      var anterior = f.contentWindow;
      var cargado = new Promise(function (res) { f.addEventListener('load', res, { once: true }); });
      T.recoger(anterior, T._etiquetaActual || '?');
      await accion();
      await cargado;
      T._etiquetaActual = etiqueta;
      return T.esperarEditor(f, etiqueta);
    },
    aplicar: function (ed, fn) {
      var s = ed.scope;
      var r;
      s.$apply(function () { r = fn(s); });
      return r;
    },
    /** Importa un texto JSON por el MISMO input #select del editor (FileReader del L26). */
    importar: async function (ed, texto, nombreArchivo) {
      var w = ed.win;
      var s = ed.scope;
      s.$apply(function () { s.name = '__importando__'; });
      var dt = new w.DataTransfer();
      dt.items.add(new w.File([texto], nombreArchivo || 'mapa.json', { type: 'application/json' }));
      var input = ed.doc.getElementById('select');
      input.files = dt.files;
      input.dispatchEvent(new w.Event('change', { bubbles: true }));
      await T.esperarQue('import aplicado', function () { return s.name !== '__importando__'; }, 10000);
      await T.esperar(100);
    },
    /** Llama export() y devuelve {href, download, json} de la descarga interceptada. */
    exportar: function (ed) {
      var w = ed.win;
      w.__descargas.length = 0;
      T.aplicar(ed, function (s) { s.export(); });
      var d = w.__descargas[w.__descargas.length - 1];
      if (!d) return null;
      var prefijo = 'data:text/json;charset=utf-8,';
      d.prefijoOk = d.href.indexOf(prefijo) === 0;
      d.json = decodeURIComponent(d.href.slice(prefijo.length));
      return d;
    },
    celda: function (ed, x, y, z) {
      return ed.doc.querySelector('tile[x="' + x + '"][y="' + y + '"][z="' + (z || 0) + '"]');
    },
    td: function (ed, x, y, z) {
      var t = T.celda(ed, x, y, z);
      return t && t.closest('td');
    },
    /** Arrastrar y soltar HTML5 sintético (mismo dataTransfer en todo el gesto) de origen a destino. */
    arrastrar: function (ed, origen, destino) {
      var w = ed.win;
      var dt = new w.DataTransfer();
      function ev(tipo, el) {
        var e = new w.DragEvent(tipo, { bubbles: true, cancelable: true, dataTransfer: dt });
        el.dispatchEvent(e);
        return e;
      }
      ev('dragstart', origen);
      ev('dragenter', destino);
      ev('dragover', destino);
      ev('drop', destino);
      ev('dragend', origen);
    },
    clic: function (ed, el, opciones) {
      var w = ed.win;
      var o = Object.assign({ bubbles: true, cancelable: true, view: w, button: 0 }, opciones || {});
      el.dispatchEvent(new w.MouseEvent('click', o));
    },
    swalTexto: function (ed) {
      var p = ed.doc.querySelector('.swal2-container .swal2-popup');
      return p ? p.textContent.replace(/\s+/g, ' ').trim() : '';
    },

    terminar: function (extra) {
      if (T.iframe && T.iframe.contentWindow) T.recoger(T.iframe.contentWindow, T._etiquetaActual || '?');
      var fallas = this.checks.filter(function (c) { return !c.ok; });
      var res = {
        ok: fallas.length === 0 && errores.length === 0 && this.checks.length > 0,
        total: this.checks.length,
        fallas: fallas,
        errores: errores,
        erroresIgnorados: this.erroresIgnorados,
        avisosEditor: this.avisosEditor.slice(0, 40),
        animaciones: this.animaciones,
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

/*
 * rcj-line-offline — área firma. Ayudas comunes de las páginas tests/firma-*.html.
 * Basado en el patrón de tests/backend-comun.js (copia propia para no depender de archivos de otra área):
 * captura errores, junta verificaciones y escribe <pre id="resultado">JSON</pre> para --dump-dom.
 * Agrega: sembrado de una corrida puntuada sobre el fixture oficial, carga de páginas en iframes con captura
 * temprana de errores, trazos sintéticos para jSignature y un oráculo independiente del desglose.
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
      if (ignorados[i].test(txt)) { T.erroresIgnorados.push(txt.slice(0, 300)); return; }
    }
    errores.push(txt.slice(0, 2000));
  }

  // Engancha errores de una ventana (la propia o la de un iframe)
  function engancharErrores(win, prefijo) {
    if (!win || win.__rcjEnganchado) return;
    try {
      win.__rcjEnganchado = true;
      win.addEventListener('error', function (e) {
        registrar(prefijo + 'onerror: ' + (e.message || e.type) + (e.filename ? ' @' + e.filename + ':' + e.lineno : ''));
      }, true);
      win.addEventListener('unhandledrejection', function (e) {
        var r = e.reason;
        registrar(prefijo + 'unhandledrejection: ' + ((r && (r.stack || r.message)) || r));
      });
      var original = win.console.error;
      win.console.error = function () {
        registrar(prefijo + 'console.error: ' + Array.prototype.map.call(arguments, textoArg).join(' '));
        return original.apply(win.console, arguments);
      };
      var logOriginal = win.console.log;
      win.__logs = [];
      win.console.log = function () {
        try { win.__logs.push(Array.prototype.map.call(arguments, function (a) { return typeof a === 'string' ? a : '[obj]'; }).join(' ')); } catch (e) { /* nada */ }
        return logOriginal.apply(win.console, arguments);
      };
    } catch (e) { /* ventana de otro origen o cerrada */ }
  }
  engancharErrores(window, '');

  // Latido (ver tests/firma-correr.py): mantiene un pedido pendiente para que Edge headless no adelante el
  // tiempo virtual mientras IndexedDB trabaja. Sin el endpoint (404) se detiene.
  var latiendo = true;
  (async function latir() {
    while (latiendo) {
      try {
        var r = await fetch('/__latido?ms=150', { cache: 'no-store' });
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
    extra: {},
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
    esperar: esperar,
    esperarQue: async function (fn, ms, nombre) {
      var t0 = Date.now();
      var limite = ms || 15000;
      while (Date.now() - t0 < limite) {
        try { if (fn()) return true; } catch (e) { /* todavía no */ }
        await esperar(50);
      }
      if (nombre) errores.push('timeout esperando: ' + nombre);
      return false;
    },
    api: function (metodo, url, cuerpo) { return window.RCJLocal.api.request(metodo, url, cuerpo); },
    resetear: async function () {
      var cols = window.RCJLocal.store.colecciones;
      for (var i = 0; i < cols.length; i++) await window.RCJLocal.store.clear(cols[i]);
    },
    fixture: async function (nombre) {
      var r = await fetch(nombre, { cache: 'no-cache' });
      if (!r.ok) throw new Error('fixture ' + nombre + ' HTTP ' + r.status);
      return r.json();
    },

    /**
     * Crea competencia/ronda/cancha/equipo semilla, ingiere el fixture oficial y crea una corrida.
     * cuerpoFn(run, mapa) -> cuerpo del PUT que la puntúa (o null para dejarla sin puntuar).
     */
    sembrarCorrida: async function (cuerpoFn) {
      await T.resetear();
      await window.RCJLocal.semillas();
      var cid = (await T.api('GET', '/api/competitions/')).data[0]._id;
      var ronda = (await T.api('GET', '/api/competitions/' + cid + '/rounds')).data[0];
      var cancha = (await T.api('GET', '/api/competitions/' + cid + '/fields')).data[0];
      var equipo = (await T.api('GET', '/api/competitions/' + cid + '/Line/teams')).data[0];
      var fx = await T.fixture('firma-fixture-mapa-oficial.json');
      var mapId = await window.RCJLocal.ingestMap(fx, { competition: cid });
      var nueva = await T.api('POST', '/api/runs/line', { round: ronda._id, team: equipo._id, field: cancha._id, competition: cid, map: mapId });
      if (nueva.status !== 201) throw new Error('no se pudo crear la corrida: ' + JSON.stringify(nueva.data));
      var runId = nueva.data.id;
      var run = (await T.api('GET', '/api/runs/line/' + runId + '?populate=true')).data; // E10 inicializa tiles/LoPs
      var mapa = (await T.api('GET', '/api/maps/line/' + mapId + '?populate=true')).data;
      var put = null;
      if (cuerpoFn) {
        var cuerpo = cuerpoFn(run, mapa);
        put = await T.api('PUT', '/api/runs/line/' + runId, cuerpo);
        if (put.status !== 200) throw new Error('PUT de puntaje falló: ' + put.status + ' ' + JSON.stringify(put.data));
      }
      var guardada = await window.RCJLocal.store.get('lineRuns', runId);
      return { cid: cid, mapId: mapId, runId: runId, run: guardada, mapa: mapa, put: put && put.data, equipo: equipo, ronda: ronda, cancha: cancha };
    },

    /** Marca como puntuados todos los scoredItems salvo los índices de `fallidos` ({indice: true}). */
    tilesPuntuadas: function (run, fallidos) {
      return run.tiles.map(function (t, i) {
        return { scoredItems: t.scoredItems.map(function (s) { return { item: s.item, scored: !(fallidos && fallidos[i]), count: s.count }; }) };
      });
    },

    /**
     * Oráculo independiente del desglose (misma aritmética que helper/scoreCalculatorRules/2026.js, reescrita
     * para la prueba): puntos por elementos, por checkpoints (con el inicio y el tramo final) y bonus de salida.
     */
    desglose: function (run, mapa) {
      var LoPs = run.LoPs, total = 0, i, j;
      for (i = 0; i < LoPs.length; i++) total += LoPs[i];
      var elementos = 0, cps = 0, lastCP = 0, cpCount = 0;
      for (i = 0; i < run.tiles.length; i++) {
        var sis = run.tiles[i].scoredItems;
        for (j = 0; j < sis.length; j++) {
          var s = sis[j], sc = s.scored ? 1 : 0;
          switch (s.item) {
            case 'checkpoint': cps += Math.max((i - lastCP) * (5 - 2 * LoPs[cpCount]), 0) * sc; lastCP = i; cpCount++; break;
            case 'gap': elementos += 10 * sc; break;
            case 'intersection': elementos += 10 * sc * s.count; break;
            case 'obstacle': elementos += 20 * sc * s.count; break;
            case 'speedbump': elementos += 10 * sc; break;
            case 'ramp': elementos += 10 * sc * s.count; break;
            case 'seesaw': elementos += 20 * sc * s.count; break;
          }
        }
      }
      var bonus = run.exitBonus ? Math.max(60 - 5 * total, 0) : 0;
      var tramoFinal = run.exitBonus ? Math.max((run.tiles.length - lastCP - 1) * (5 - 2 * LoPs[cpCount]), 0) : 0;
      var sinInicio = elementos + cps + bonus + tramoFinal;
      var inicio = (run.showedUp || sinInicio > 0) ? 5 : 0;
      // multiplicador del servidor
      var mult = 1, err = 1, vivas = 0;
      (run.rescueOrder || []).forEach(function (v) {
        if (v.victimType == 'LIVE' && v.zoneType == 'RED') return;
        if (v.victimType == 'DEAD' && v.zoneType == 'GREEN') return;
        if (v.victimType == 'DEAD' && vivas != mapa.victims.live) return;
        mult *= Math.max(1400 - 50 * LoPs[mapa.EvacuationAreaLoPIndex], 1250);
        err *= 1000;
        if (v.victimType == 'LIVE') vivas++;
      });
      mult /= err;
      return {
        elementos: elementos, checkpoints: cps, tramoFinal: tramoFinal, bonus: bonus, inicio: inicio,
        inicioCliente: 5 * (run.showedUp ? 1 : 0), raw: sinInicio + inicio, multiplicador: mult,
        checkpointsServidorCantidad: cpCount
      };
    },

    /** Carga una página de la app en un iframe y engancha sus errores lo antes posible. */
    cargarIframe: async function (url, opciones) {
      opciones = opciones || {};
      var f = document.createElement('iframe');
      f.style.width = (opciones.ancho || 1366) + 'px';
      f.style.height = (opciones.alto || 900) + 'px';
      f.style.border = '0';
      f.style.display = 'block';
      if (opciones.id) f.id = opciones.id;
      (opciones.contenedor || document.body).appendChild(f);
      var prefijo = '[' + (opciones.nombre || url) + '] ';
      f.src = url;
      // el parser del iframe cede al esperar cada <script src>: se engancha en cuanto aparece la ventana nueva
      await T.esperarQue(function () {
        var w = f.contentWindow;
        if (w && w.location && w.location.href !== 'about:blank') { engancharErrores(w, prefijo); return true; }
        return false;
      }, 10000, 'ventana del iframe ' + url);
      await new Promise(function (res) {
        if (f.contentDocument && f.contentDocument.readyState === 'complete' && f.contentWindow.location.href !== 'about:blank') res();
        else f.addEventListener('load', function () { res(); }, { once: true });
      });
      engancharErrores(f.contentWindow, prefijo);
      return f;
    },

    /** scope de ddController dentro de un iframe */
    scope: function (f) {
      var w = f.contentWindow;
      return w.angular.element(w.document.body).scope();
    },

    /** Espera a que la página de firma/vista tenga la corrida y el mapa cargados y las baldosas dibujadas */
    esperarCarga: async function (f, nombre) {
      var ok = await T.esperarQue(function () {
        var s = T.scope(f);
        var d = f.contentDocument;
        return s && s.team && s.mtiles && Object.keys(s.mtiles).length > 0 && s.checkPointDistance.length > 0 &&
          d.querySelectorAll('tile img').length > 0;
      }, 20000, 'carga de ' + (nombre || f.src));
      T.sinAnimaciones(f);
      return ok;
    },

    /**
     * SOLO PRUEBAS. En Edge headless con --virtual-time-budget no hay frames en los iframes: requestAnimationFrame
     * no corre y ngAnimate deja a medias los ng-show/ng-hide (se ven a la vez "Firmar" y la firma), los modales y
     * los SweetAlert. $animate.enabled(false) hace que Angular aplique las clases al instante, igual que un
     * navegador real cuando la animación termina. No cambia lógica de la página.
     */
    sinAnimaciones: function (f) {
      try {
        var w = f.contentWindow;
        w.angular.element(w.document.body).injector().get('$animate').enabled(false);
        return true;
      } catch (e) { return false; }
    },

    /** Dibuja trazos sintéticos (mousedown/mousemove/mouseup) sobre el canvas de jSignature de #idDiv */
    dibujarFirma: async function (f, idDiv, trazos) {
      var w = f.contentWindow;
      var d = f.contentDocument;
      var ok = await T.esperarQue(function () { return d.querySelector('#' + idDiv + ' canvas'); }, 5000, 'canvas de ' + idDiv);
      if (!ok) return 0;
      var canvas = d.querySelector('#' + idDiv + ' canvas');
      var r = canvas.getBoundingClientRect();
      trazos = trazos || [
        [[0.10, 0.60], [0.18, 0.30], [0.26, 0.70], [0.34, 0.35], [0.42, 0.65], [0.50, 0.40]],
        [[0.55, 0.55], [0.62, 0.45], [0.70, 0.62], [0.78, 0.38], [0.88, 0.58]]
      ];
      function ev(tipo, px, py) {
        var x = r.left + px * r.width, y = r.top + py * r.height;
        var e = new w.MouseEvent(tipo, { bubbles: true, cancelable: true, view: w, clientX: x, clientY: y, screenX: x, screenY: y, button: 0, buttons: tipo === 'mouseup' ? 0 : 1 });
        canvas.dispatchEvent(e);
      }
      for (var t = 0; t < trazos.length; t++) {
        var pts = trazos[t];
        ev('mousedown', pts[0][0], pts[0][1]);
        for (var k = 1; k < pts.length; k++) {
          // puntos intermedios para un trazo continuo
          for (var q = 1; q <= 4; q++) {
            ev('mousemove', pts[k - 1][0] + (pts[k][0] - pts[k - 1][0]) * q / 4, pts[k - 1][1] + (pts[k][1] - pts[k - 1][1]) * q / 4);
            await esperar(5);
          }
        }
        ev('mouseup', pts[pts.length - 1][0], pts[pts.length - 1][1]);
        await esperar(20);
      }
      try { return w.jQuery('#' + idDiv).jSignature('getData', 'native').length; } catch (e) { return -1; }
    },

    /** Clic en el primer elemento del iframe que matchee selector (y filtro opcional por atributo ng-click) */
    clic: function (f, selector, ngClick) {
      var d = f.contentDocument;
      var lista = Array.prototype.slice.call(d.querySelectorAll(selector));
      if (ngClick) lista = lista.filter(function (el) { return el.getAttribute('ng-click') === ngClick; });
      if (!lista.length) throw new Error('no hay elemento ' + selector + ' ' + (ngClick || ''));
      lista[0].click();
      return lista[0];
    },

    /** Espera un SweetAlert2 abierto en el iframe y devuelve {titulo, texto} */
    esperarSwal: async function (f, titulo) {
      var d = f.contentDocument;
      var ok = await T.esperarQue(function () {
        var t = d.querySelector('.swal2-container .swal2-title');
        return t && (!titulo || t.textContent === titulo) && d.querySelector('.swal2-popup.swal2-show');
      }, 10000, 'swal ' + (titulo || ''));
      if (!ok) return null;
      return { titulo: d.querySelector('.swal2-title').textContent, texto: (d.querySelector('.swal2-content') || {}).textContent };
    },

    /**
     * SweetAlert2 7.33 quita el contenedor en animationend y ui-bootstrap/ngAnimate saca el modal después de la
     * transición (con requestAnimationFrame). En Edge headless sin frames esos eventos pueden no llegar nunca y el
     * DOM queda con .swal2-hide / .modal sin quitar aunque ya esté cerrado (mismo criterio que tests/juez-comun.js).
     */
    swalCerrado: function (f) {
      var d = f.contentDocument;
      return !d.querySelector('.swal2-container') || !d.querySelector('.swal2-popup:not(.swal2-hide)');
    },
    modalCerrado: function (f) {
      var w = f.contentWindow, d = f.contentDocument;
      if (!d.querySelector('.modal-dialog')) return true;
      try { return w.angular.element(d.body).injector().get('$uibModalStack').getTop() === undefined; } catch (e) { return false; }
    },

    texto: function (f, selector) {
      var el = f.contentDocument.querySelector(selector);
      return el ? el.textContent.replace(/\s+/g, ' ').trim() : null;
    },

    terminar: function () {
      var fallas = this.checks.filter(function (c) { return !c.ok; });
      var res = {
        ok: fallas.length === 0 && errores.length === 0 && this.checks.length > 0,
        total: this.checks.length,
        fallas: fallas,
        errores: errores,
        erroresIgnorados: this.erroresIgnorados,
        verificaciones: this.checks.map(function (c) { return (c.ok ? 'OK    ' : 'FALLA ') + c.nombre; }),
        extra: this.extra
      };
      document.getElementById('resultado').textContent = JSON.stringify(res);
      latiendo = false;
    },
    correr: function (fn) {
      var self = this;
      Promise.resolve().then(fn).then(function () { self.terminar(); }, function (e) {
        errores.push('excepción de la prueba: ' + ((e && e.stack) || e));
        self.terminar();
      });
    },
    detenerLatido: function () { latiendo = false; }
  };
})();

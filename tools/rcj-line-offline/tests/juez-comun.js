/*
 * rcj-line-offline — área juez. Ayudas comunes de las páginas tests/juez-*.html.
 *
 * - Captura window.onerror, unhandledrejection y console.error de la página de prueba y del juez que
 *   corre dentro del iframe (la sonda se instala mientras el iframe todavía está cargando, antes del
 *   arranque de Angular, porque $log guarda la referencia a console.error al arrancar).
 * - Espía RCJLocal.api.request del iframe: cada pedido queda en T.juez.pedidos con su respuesta.
 * - Latido /__latido (ver tests/juez-correr.py): con --virtual-time-budget Edge headless no adelanta el
 *   tiempo virtual mientras haya un pedido pendiente, así el --dump-dom espera a IndexedDB.
 * - Escribe el resultado en <pre id="resultado">JSON</pre>.
 * Cargar ANTES que cualquier otro script de la página.
 */
(function () {
  'use strict';

  var errores = [];
  var ignorados = [];
  var consola = []; // console.warn/log del juez (informativo)

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

  function instalarCaptura(w, prefijo) {
    w.addEventListener('error', function (e) {
      // Errores de carga de recursos (img/script) llegan como Event sin message
      if (e && e.target && e.target !== w && e.target.tagName) {
        registrar(prefijo + 'recurso no cargado: <' + e.target.tagName.toLowerCase() + '> ' + (e.target.src || e.target.href || ''));
        return;
      }
      registrar(prefijo + 'onerror: ' + (e.message || e.type) + (e.filename ? ' @' + e.filename + ':' + e.lineno : ''));
    }, true);
    w.addEventListener('unhandledrejection', function (e) {
      var r = e.reason;
      registrar(prefijo + 'unhandledrejection: ' + ((r && (r.stack || r.message)) || r));
    });
    var errorOriginal = w.console.error;
    w.console.error = function () {
      registrar(prefijo + 'console.error: ' + Array.prototype.map.call(arguments, textoArg).join(' '));
      return errorOriginal.apply(w.console, arguments);
    };
    var warnOriginal = w.console.warn;
    w.console.warn = function () {
      consola.push(prefijo + 'warn: ' + Array.prototype.map.call(arguments, textoArg).join(' ').slice(0, 300));
      return warnOriginal.apply(w.console, arguments);
    };
  }
  instalarCaptura(window, '');

  var latiendo = true;
  // ?latidoMax=N corta el latido tras N pedidos (~200 ms reales c/u): las capturas terminan aunque algo se cuelgue
  var latidoMax = Number(new URLSearchParams(location.search).get('latidoMax')) || Infinity;
  (async function latir() {
    var n = 0;
    while (latiendo && n++ < latidoMax) {
      try {
        var r = await fetch('/__latido?ms=200', { cache: 'no-store' });
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
    consola: consola,
    extra: {},
    ignorarErrores: function (re) { ignorados.push(re); },
    check: function (nombre, cond, detalle) {
      var c = { nombre: nombre, ok: !!cond };
      if (!cond && detalle !== undefined) {
        try { c.detalle = JSON.parse(JSON.stringify(detalle)); } catch (e) { c.detalle = String(detalle); }
      }
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
      try {
        window.localStorage.removeItem('rcjLocalFlags');
        Object.keys(window.localStorage).forEach(function (k) { if (k.indexOf('rcjJuezTimer:') === 0) window.localStorage.removeItem(k); });
        window.sessionStorage.removeItem('rcjVolviDeFirma');
      } catch (e) { /* nada */ }
      Object.assign(window.RCJLocal.flags, window.RCJLocal.flagsPorDefecto);
    },
    fixture: async function (nombre) {
      var r = await fetch('backend-fixtures/' + nombre, { cache: 'no-cache' });
      if (!r.ok) throw new Error('fixture ' + nombre + ' HTTP ' + r.status);
      return r.json();
    },
    esperar: esperar,
    esperarQue: async function (cond, ms, descripcion) {
      var limite = Date.now() + (ms || 10000);
      while (Date.now() < limite) {
        try { if (cond()) return true; } catch (e) { /* todavía no */ }
        await esperar(20);
      }
      throw new Error('tiempo agotado esperando: ' + (descripcion || cond.toString().slice(0, 200)));
    },

    /** Sembrado estándar: semillas + mapa + corrida (E13). Devuelve {cid, ronda, cancha, equipo, mapId, mapa, runId}. */
    sembrar: async function (mapaExport, opciones) {
      opciones = opciones || {};
      await this.resetear();
      var sets = await this.fixture('tilesets.json');
      await window.RCJLocal.semillas({ tilesets: sets });
      var comp = (await this.api('GET', '/api/competitions/')).data[0];
      var cid = comp._id;
      var ronda = (await this.api('GET', '/api/competitions/' + cid + '/rounds')).data[0];
      var cancha = (await this.api('GET', '/api/competitions/' + cid + '/fields')).data[0];
      var equipo = (await this.api('GET', '/api/competitions/' + cid + '/Line/teams')).data[0];
      var mapId = await window.RCJLocal.ingestMap(mapaExport, { competition: cid, renombrarSiExiste: true });
      var mapa = (await this.api('GET', '/api/maps/line/' + mapId + '?populate=true')).data;
      var alta = await this.api('POST', '/api/runs/line', { round: ronda._id, team: equipo._id, field: cancha._id, competition: cid, map: mapId });
      if (alta.status !== 201) throw new Error('E13 no creó la corrida: ' + JSON.stringify(alta.data));
      return { cid: cid, comp: comp, ronda: ronda, cancha: cancha, equipo: equipo, mapId: mapId, mapa: mapa, runId: alta.data.id };
    },

    terminar: function (extra) {
      var fallas = this.checks.filter(function (c) { return !c.ok; });
      var res = {
        ok: fallas.length === 0 && errores.length === 0 && this.checks.length > 0,
        total: this.checks.length,
        fallas: fallas,
        errores: errores,
        erroresIgnorados: this.erroresIgnorados,
        verificaciones: this.checks.map(function (c) { return (c.ok ? 'OK    ' : 'FALLA ') + c.nombre; }),
        consola: consola.slice(0, 60)
      };
      res.extra = Object.assign({}, this.extra, extra || {});
      document.getElementById('resultado').textContent = JSON.stringify(res);
      latiendo = false;
    },
    correr: function (fn) {
      var self = this;
      Promise.resolve().then(fn).then(function (extra) { self.terminar(extra); }, function (e) {
        errores.push('excepción de la prueba: ' + ((e && e.stack) || e));
        self.terminar();
      });
    },
    detenerLatido: function () { latiendo = false; }
  };

  // ------------------------------------------------------------------ manejo del juez en un iframe
  var J = T.juez = {
    iframe: null,
    pedidos: [],
    sondas: [],
    crear: function (ancho, alto) {
      var f = document.createElement('iframe');
      f.id = 'juez';
      f.style.cssText = 'border:1px solid #999;width:' + (ancho || 1366) + 'px;height:' + (alto || 860) + 'px;display:block';
      document.body.insertBefore(f, document.body.firstChild);
      this.iframe = f;
      return f;
    },
    win: function () { return this.iframe.contentWindow; },
    doc: function () { return this.iframe.contentWindow.document; },
    scope: function () { return this.win().angular.element(this.doc().body).scope(); },
    $: function (sel) { return this.doc().querySelector(sel); },
    $$: function (sel) { return Array.prototype.slice.call(this.doc().querySelectorAll(sel)); },

    // Instala la sonda en la ventana nueva del iframe apenas existe (document.readyState === 'loading').
    vigilar: function (patron) {
      var self = this;
      var viejo = null;
      try { viejo = self.iframe.contentWindow; } catch (e) { /* nada */ }
      var fin = Date.now() + 20000;
      (function poll() {
        var w;
        try { w = self.iframe.contentWindow; } catch (e) { w = null; }
        var listo = false;
        // La página vieja lleva __rcjViejo (marcarViejo). No se exige readyState 'loading': en una pestaña en
        // segundo plano los setTimeout se estrangulan y la sonda puede llegar tarde (queda registrado en sondas).
        try { listo = w && w.location.href.indexOf(patron) >= 0 && !w.__rcjSonda && !w.__rcjViejo; } catch (e) { listo = false; }
        if (listo) {
          w.__rcjSonda = true;
          self.sondas.push({ url: w.location.href, readyState: w.document.readyState });
          instalarCaptura(w, '[iframe ' + w.location.pathname.split('/').pop() + '] ');
          (function espiar() {
            if (w.RCJLocal && w.RCJLocal.api && w.RCJLocal.api.request && !w.RCJLocal.api.request.__espia) {
              var original = w.RCJLocal.api.request;
              var espia = function (method, url, body, opts) {
                // $http serializa el cuerpo antes del decorador de $httpBackend: llega como string JSON
                var cuerpo;
                if (typeof body === 'string') { try { cuerpo = JSON.parse(body); } catch (e) { cuerpo = body; } }
                else cuerpo = body === undefined ? undefined : JSON.parse(JSON.stringify(body));
                var reg = { method: method, url: url, body: cuerpo, t: Date.now() };
                self.pedidos.push(reg);
                return original.apply(this, arguments).then(function (r) {
                  reg.status = r.status;
                  try { reg.data = JSON.parse(JSON.stringify(r.data)); } catch (e) { reg.data = String(r.data); }
                  return r;
                }, function (e) { reg.status = 'excepción'; reg.error = String(e); throw e; });
              };
              espia.__espia = true;
              w.RCJLocal.api.request = espia;
            } else if (w.document.readyState !== 'complete' || !w.RCJLocal) {
              setTimeout(espiar, 2);
            }
          })();
          // Arnés de prueba: sin animaciones de ngAnimate en el juez. Con --virtual-time-budget Edge headless no
          // termina las animaciones (quedan con ng-hide-animate/ng-hide-remove), el promise `closed` del modal no
          // se resuelve y la vista de puntuación queda oculta. Sin animaciones los cambios de clase son inmediatos,
          // como en un navegador real un frame después. No toca el código del juez.
          (function sinAnimaciones(intentos) {
            var listo = false;
            try {
              var inj = w.angular && w.document.body && w.angular.element(w.document.body).injector();
              if (inj) {
                inj.get('$animate').enabled(false);
                listo = true;
              } else if (w.angular) {
                var modulo = w.angular.module('ddApp');
                modulo.run(['$animate', function ($animate) { $animate.enabled(false); }]);
                // ui-bootstrap cierra el modal con $animateCss (no lo apaga $animate.enabled), que espera
                // requestAnimationFrame: sin frames el promise `closed` no se resuelve. $$rAF con setTimeout.
                modulo.config(['$provide', function ($provide) {
                  $provide.decorator('$$rAF', ['$delegate', function ($delegate) {
                    var raf = function (fn) {
                      var id = w.setTimeout(fn, 16);
                      return function () { w.clearTimeout(id); };
                    };
                    raf.supported = $delegate.supported;
                    return raf;
                  }]);
                }]);
                listo = true;
              }
            } catch (e) { /* el módulo ddApp todavía no está definido */ }
            if (!listo && intentos > 0) setTimeout(function () { sinAnimaciones(intentos - 1); }, 3);
          })(4000);
          return;
        }
        if (Date.now() < fin) setTimeout(poll, 1);
      })();
    },

    /** Navega el iframe a url y espera a que el juez tenga corrida y mapa cargados. */
    // iframe.contentWindow es el MISMO WindowProxy antes y después de navegar: para distinguir la página
    // vieja se marca su global (__rcjViejo), que desaparece con el documento nuevo.
    marcarViejo: function () {
      try { this.iframe.contentWindow.__rcjViejo = true; } catch (e) { /* nada */ }
    },
    abrir: async function (url) {
      var self = this;
      this.marcarViejo();
      this.vigilar('juez.html');
      this.iframe.src = url;
      await T.esperarQue(function () {
        var w = self.win();
        return !w.__rcjViejo && w.location.href.indexOf('juez.html') >= 0 && w.document.readyState === 'complete' && w.angular &&
          self.scope() && self.scope().duration !== undefined && self.scope().team;
      }, 15000, 'juez cargado: ' + url);
      await T.esperar(400);
    },
    recargar: async function () {
      var self = this;
      var anterior = this.win();
      this.marcarViejo();
      this.vigilar('juez.html');
      anterior.location.reload();
      await T.esperarQue(function () {
        var w = self.win();
        return !w.__rcjViejo && w.document.readyState === 'complete' && w.angular && self.scope() && self.scope().duration !== undefined && self.scope().team;
      }, 15000, 'juez recargado');
      await T.esperar(400);
    },

    /** Espera a que haya pedidos nuevos (desde n0) y que todos tengan respuesta y el digest termine. */
    esperarPedidos: async function (n0, minimo) {
      var self = this;
      await T.esperarQue(function () {
        return self.pedidos.length >= n0 + (minimo || 1) && self.pedidos.every(function (p) { return p.status !== undefined; });
      }, 10000, 'pedidos del juez');
      await T.esperar(80);
      return this.pedidos.slice(n0);
    },
    pendientes: function () { return this.pedidos.filter(function (p) { return p.status === undefined; }).length; },
    ultimoPut: function () {
      for (var i = this.pedidos.length - 1; i >= 0; i--) if (this.pedidos[i].method === 'PUT') return this.pedidos[i];
      return null;
    },
    click: function (el) {
      if (!el) throw new Error('click: elemento inexistente');
      el.click();
    },
    /** tile de la grilla en (x, y) del piso visible, con la vista sin rotar (sRotate 0). */
    baldosa: function (x, y) {
      var filas = this.$$('#wrapTile > div');
      var fila = filas[y];
      if (!fila) return null;
      var slots = fila.querySelectorAll('.slot');
      return slots[x] ? slots[x].querySelector('tile') : null;
    },
    puntajeNavbar: function () {
      var li = this.$$('nav .col-md-3 li.navbar-brand')[0];
      var m = /-?\d+/.exec(li ? li.textContent : '');
      return m ? Number(m[0]) : null;
    },
    tiempoNavbar: function () {
      var li = this.$$('nav .col-md-3 li.navbar-brand')[1];
      return li ? li.textContent.trim() : null;
    },
    // SweetAlert2 7.33 quita el contenedor en animationend; si no hay render (pestaña oculta) queda con .swal2-hide
    swalAbierto: function () { return this.$('.swal2-popup:not(.swal2-hide)'); },
    swalCerrado: function () { return !this.$('.swal2-container') || !this.$('.swal2-popup:not(.swal2-hide)'); },
    visible: function (el) {
      if (!el) return false;
      // Estado final: ng-hide-add = se está ocultando; ng-hide con ng-hide-remove = se está mostrando
      for (var n = el; n && n.nodeType === 1; n = n.parentNode) {
        var cl = n.classList;
        if (cl.contains('ng-hide-add') || (cl.contains('ng-hide') && !cl.contains('ng-hide-remove'))) return false;
      }
      return true;
    }
  };
})();

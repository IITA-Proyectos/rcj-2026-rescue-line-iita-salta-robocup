/*
 * rcj-line-offline — área salidas. Ayudas comunes de las páginas tests/salidas-*.html.
 * Captura window.onerror, unhandledrejection y console.error; junta verificaciones y escribe el
 * resultado en <pre id="resultado">JSON</pre> (se lee con --dump-dom). Cargar ANTES que la app.
 * Con tests/salidas-correr.py: GET /__latido mantiene la página "ocupada" para --virtual-time-budget
 * y POST /__archivo?nombre=X guarda un archivo generado en tests/capturas/.
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

  function latin1(ab) { return new TextDecoder('latin1').decode(new Uint8Array(ab)); }

  var T = window.T = {
    checks: [],
    erroresIgnorados: [],
    archivos: [],
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
    header: function (r, nombre) {
      var h = (r && r.headers) || {};
      var k = Object.keys(h).find(function (x) { return x.toLowerCase() === nombre.toLowerCase(); });
      return k ? h[k] : undefined;
    },
    resetear: async function () {
      var cols = window.RCJLocal.store.colecciones;
      for (var i = 0; i < cols.length; i++) await window.RCJLocal.store.clear(cols[i]);
    },
    fixture: async function (nombre) {
      var r = await fetch('salidas-fixtures/' + nombre, { cache: 'no-cache' });
      if (!r.ok) throw new Error('fixture ' + nombre + ' HTTP ' + r.status);
      return r.json();
    },
    guardar: async function (nombre, datos) {
      try {
        var r = await fetch('/__archivo?nombre=' + encodeURIComponent(nombre), { method: 'POST', body: datos });
        if (r.status === 204) this.archivos.push(nombre);
        return r.status === 204;
      } catch (e) {
        return false;
      }
    },
    pngInfo: function (ab) {
      var b = new Uint8Array(ab);
      var firma = [137, 80, 78, 71, 13, 10, 26, 10].every(function (v, i) { return b[i] === v; });
      var dv = new DataView(ab);
      return { firma: firma, ancho: firma ? dv.getUint32(16) : null, alto: firma ? dv.getUint32(20) : null, bytes: ab.byteLength };
    },
    pdfInfo: function (ab) {
      var txt = latin1(ab);
      var cajas = [];
      var re = /\/MediaBox \[([^\]]*)\]/g, m;
      while ((m = re.exec(txt))) cajas.push(m[1].trim().replace(/\s+/g, ' '));
      return {
        cabecera: txt.slice(0, 8),
        eof: /%%EOF\s*$/.test(txt),
        paginas: (txt.match(/\/Type \/Page\b(?!s)/g) || []).length,
        mediaBoxes: cajas,
        imagenes: (txt.match(/\/Subtype \/Image/g) || []).length,
        bytes: ab.byteLength
      };
    },
    igualesBytes: function (a, b) {
      if (!(a instanceof ArrayBuffer) || !(b instanceof ArrayBuffer) || a.byteLength !== b.byteLength) return false;
      var x = new Uint8Array(a), y = new Uint8Array(b);
      for (var i = 0; i < x.length; i++) if (x[i] !== y[i]) return false;
      return true;
    },
    esperar: function (ms) { return new Promise(function (res) { setTimeout(res, ms); }); },

    // Datos de prueba: competencia semilla + mapa del fixture + 2 corridas puntuadas
    sembrar: async function () {
      var api = this.api.bind(this);
      await this.resetear();
      await window.RCJLocal.semillas();
      var cid = (await api('GET', '/api/competitions/')).data[0]._id;
      var ronda1 = (await api('GET', '/api/competitions/' + cid + '/rounds')).data[0]._id;
      var cancha = (await api('GET', '/api/competitions/' + cid + '/fields')).data[0]._id;
      var equipoA = (await api('GET', '/api/competitions/' + cid + '/Line/teams')).data[0]._id;
      var ronda2 = (await api('POST', '/api/rounds', { name: 'Ronda 2', competition: cid })).data.id;
      var equipoB = (await api('POST', '/api/teams', { name: 'Equipo Práctica B', league: 'Line', competition: cid, teamCode: 'B7' })).data.id;
      var fx = await this.fixture('fixture-mapa-oficial.json');
      var mapId = await window.RCJLocal.ingestMap(fx, { competition: cid });
      var t1 = Date.UTC(2026, 8, 13, 17, 30);
      var t2 = Date.UTC(2026, 8, 13, 18, 10);
      var c1 = await api('POST', '/api/runs/line', { round: ronda1, team: equipoA, field: cancha, competition: cid, map: mapId, startTime: t1, normalizationGroup: 1 });
      var c2 = await api('POST', '/api/runs/line', { round: ronda2, team: equipoB, field: cancha, competition: cid, map: mapId, startTime: t2, normalizationGroup: 2 });
      if (c1.status !== 201 || c2.status !== 201) throw new Error('No se pudieron crear las corridas: ' + JSON.stringify([c1.data, c2.data]));
      var run1 = c1.data.id, run2 = c2.data.id;
      await api('GET', '/api/runs/line/' + run1);
      var p1 = await api('PUT', '/api/runs/line/' + run1, {
        showedUp: true, time: { minutes: 5, seconds: 42 }, LoPs: [1, 0, 2], exitBonus: true, evacuationLevel: 2,
        rescueOrder: [{ victimType: 'LIVE', zoneType: 'GREEN' }, { victimType: 'LIVE', zoneType: 'GREEN' }, { victimType: 'DEAD', zoneType: 'RED' }],
        status: 4
      });
      await api('GET', '/api/runs/line/' + run2);
      var p2 = await api('PUT', '/api/runs/line/' + run2, {
        showedUp: true, time: { minutes: 8, seconds: 0 }, LoPs: [0, 3, 0], evacuationLevel: 1,
        rescueOrder: [{ victimType: 'LIVE', zoneType: 'RED' }], status: 4
      });
      if (p1.status !== 200 || p2.status !== 200) throw new Error('No se pudieron puntuar las corridas: ' + JSON.stringify([p1.data, p2.data]));
      return { cid: cid, mapId: mapId, runs: [run1, run2], equipos: [equipoA, equipoB], rondas: [ronda1, ronda2], cancha: cancha, fx: fx, puntajes: [p1.data, p2.data] };
    },

    terminar: function (extra) {
      var fallas = this.checks.filter(function (c) { return !c.ok; });
      var res = {
        ok: fallas.length === 0 && errores.length === 0 && this.checks.length > 0,
        total: this.checks.length,
        fallas: fallas,
        errores: errores,
        erroresIgnorados: this.erroresIgnorados,
        archivos: this.archivos,
        verificaciones: this.checks.map(function (c) { return (c.ok ? 'OK    ' : 'FALLA ') + c.nombre; })
      };
      if (extra) res.extra = extra;
      document.getElementById('resultado').textContent = JSON.stringify(res);
      // Con --screenshot no hay --dump-dom: la página de captura manda el resultado por POST
      var envio = null;
      try { envio = typeof this.alTerminar === 'function' ? this.alTerminar(res) : null; } catch (e) { envio = null; }
      Promise.resolve(envio).then(null, function () {}).then(function () { latiendo = false; });
    },
    /** Iframe del tamaño pedido, esperando la carga completa. */
    cargarIframe: function (url, ancho, alto, contenedor) {
      var f = document.createElement('iframe');
      f.style.width = ancho + 'px';
      f.style.height = alto + 'px';
      f.style.border = '0';
      f.style.display = 'block';
      (contenedor || document.body).appendChild(f);
      return new Promise(function (resolver) {
        f.onload = function () { resolver(f); };
        f.src = url;
      });
    },
    /** Espera a que la condición sea verdadera (lanza si vence el plazo). */
    esperarQue: async function (fn, ms, que) {
      var fin = Date.now() + (ms || 15000);
      while (Date.now() < fin) {
        try { var v = fn(); if (v) return v; } catch (e) { /* todavía cargando */ }
        await this.esperar(100);
      }
      throw new Error('tiempo agotado esperando: ' + (que || 'condición'));
    },
    /** Angular del iframe arrancado y sin pedidos $http pendientes. */
    esperarHttp: function (f, ms) {
      return this.esperarQue(function () {
        var w = f.contentWindow;
        var inj = w.angular && w.angular.element(w.document.body).injector();
        return inj && inj.get('$http').pendingRequests.length === 0;
      }, ms || 20000, '$http inactivo');
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

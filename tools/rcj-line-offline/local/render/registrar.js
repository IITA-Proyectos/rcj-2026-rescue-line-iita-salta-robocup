/*
 * rcj-line-offline — área salidas.
 * Registra en el backend local (RCJLocal.api.registrarRuta) los endpoints de salida del CMS:
 *
 *   POST /api/maps/line/map-image-png    PNG del mapa            (editor, L26:873-889)
 *   POST /api/maps/line/map-image-pdf    PDF del mapa A4/Letter  (editor, L26:873-889)
 *   POST /api/maps/line/scoresheet       planilla PDF del mapa   (editor, L26:830-857)
 *   GET  /api/maps/line/image/:mapid     PNG de un mapa guardado (admin/maps.js:146)
 *   GET  /api/maps/line/export           PDF/ZIP de varios mapas (admin/maps.js:133-160)
 *   GET  /api/runs/line/scoresheet2      planillas de corridas   (admin/games.js:345, :485)
 *
 * Es liviano: los generadores (local/render/comun.js, mapa-png.js, mapa-pdf.js, planilla-pdf.js,
 * rutas-cms.js) y las librerías pesadas (components/pdfkit 2,6 MB, qrcode-generator) se cargan
 * recién en el primer pedido. El PNG no carga pdfkit.
 *
 * Uso en una página: después de local/nucleo/api.js,
 *   <script src="local/render/registrar.js"></script>
 * Nada más (no incluir los otros archivos de local/render/ a mano).
 *
 * Ayudas para páginas que abren estas URLs sin $http (window.open / <a href>):
 *   RCJLocal.salidas.abrir(url, destino)     abre la salida en otra pestaña (blob:)
 *   RCJLocal.salidas.descargar(url, nombre)  la descarga con <a download>
 *   RCJLocal.salidas.interceptarWindowOpen() hace que window.open('/api/...') use abrir()
 */
(function (global) {
  'use strict';

  var R = global.RCJLocal = global.RCJLocal || {};
  var S = R.salidas = R.salidas || {};
  if (S.registrado) return;

  function base() { return R.base || '/'; }

  // ---------------------------------------------------------------- carga bajo demanda
  var promesas = {};
  function cargarScript(ruta, yaCargado) {
    if (yaCargado && yaCargado()) return Promise.resolve();
    if (!promesas[ruta]) {
      promesas[ruta] = new Promise(function (resolver, rechazar) {
        var s = document.createElement('script');
        s.src = base() + ruta;
        s.async = false;
        s.onload = function () { resolver(); };
        s.onerror = function () {
          delete promesas[ruta];
          rechazar(new Error('No se pudo cargar ' + ruta));
        };
        (document.head || document.documentElement).appendChild(s);
      });
    }
    return promesas[ruta];
  }
  function moduloCargado(ruta) {
    return function () { return !!(S.modulosCargados && S.modulosCargados[ruta]); };
  }

  /** Carga los generadores. conPDF=true agrega pdfkit, qrcode-generator y los módulos PDF. */
  S.cargar = async function (conPDF) {
    await cargarScript('local/render/comun.js', function () { return !!S.comun; });
    if (conPDF) {
      await Promise.all([
        cargarScript('components/pdfkit/js/pdfkit.standalone.js', function () { return typeof global.PDFDocument === 'function'; }),
        cargarScript('components/qrcode-generator/qrcode.js', function () { return typeof global.qrcode === 'function'; })
      ]);
    }
    var lista = ['local/render/mapa-png.js'];
    if (conPDF) lista.push('local/render/mapa-pdf.js', 'local/render/planilla-pdf.js');
    lista.push('local/render/rutas-cms.js');
    await Promise.all(lista.map(function (r) { return cargarScript(r, moduloCargado(r)); }));
  };

  // ---------------------------------------------------------------- rutas
  var USUARIO_LOCAL = { username: 'local', superDuperAdmin: true, competitions: [] };

  var RUTAS = [
    { metodo: 'POST', re: /^\/api\/maps\/line\/map-image-png\/?$/i, montaje: '/api/maps/line', ruta: '/map-image-png', pdf: false },
    { metodo: 'POST', re: /^\/api\/maps\/line\/map-image-pdf\/?$/i, montaje: '/api/maps/line', ruta: '/map-image-pdf', pdf: true },
    { metodo: 'POST', re: /^\/api\/maps\/line\/scoresheet\/?$/i, montaje: '/api/maps/line', ruta: '/scoresheet', pdf: true, planilla: true },
    { metodo: 'GET', re: /^\/api\/maps\/line\/image\/([^/]+)\/?$/i, params: ['mapid'], montaje: '/api/maps/line', ruta: '/image/:mapid', pdf: false },
    { metodo: 'GET', re: /^\/api\/maps\/line\/export\/?$/i, montaje: '/api/maps/line', ruta: '/export', pdf: true, planilla: true },
    { metodo: 'GET', re: /^\/api\/runs\/line\/scoresheet2\/?$/i, montaje: '/api/runs/line', ruta: '/scoresheet2', pdf: true, planilla: true }
  ];
  S.rutas = RUTAS;

  async function atender(def, ctx) {
    await S.cargar(def.pdf);
    var C = S.comun;
    if (def.planilla) await C.fs.precargar(C.RECURSOS_PLANILLA);
    var r = C.buscarRuta(def.metodo, def.montaje, def.ruta);
    if (!r) {
      return { status: 500, data: { msg: 'Error interno del backend local', err: 'Ruta de salida no encontrada: ' + def.ruta }, headers: { 'Content-Type': 'application/json; charset=utf-8' } };
    }
    var params = {};
    (def.params || []).forEach(function (n, i) {
      try { params[n] = decodeURIComponent(ctx.match[i + 1]); } catch (e) { params[n] = ctx.match[i + 1]; }
    });
    return C.ejecutarExpress(r.handler, {
      method: ctx.method, url: ctx.url, originalUrl: ctx.url, path: ctx.path,
      body: ctx.body, query: ctx.query, params: params, user: USUARIO_LOCAL
    });
  }

  if (!R.api || typeof R.api.registrarRuta !== 'function') {
    console.error('[RCJLocal.salidas] local/render/registrar.js tiene que cargarse después de local/nucleo/api.js');
    return;
  }
  RUTAS.forEach(function (def) {
    R.api.registrarRuta(def.metodo, def.re, function (ctx) { return atender(def, ctx); });
  });
  S.registrado = true;

  // ---------------------------------------------------------------- ayudas para window.open / <a href>
  function rutaApi(url) {
    var u = new URL(url, global.location.href);
    if (u.origin !== global.location.origin || !/^\/api(\/|$)/.test(u.pathname)) return null;
    return u.pathname + u.search;
  }
  function tipoDe(r) {
    var h = r.headers || {};
    var k = Object.keys(h).find(function (x) { return x.toLowerCase() === 'content-type'; });
    if (k) return h[k];
    if (r.data instanceof ArrayBuffer && r.data.byteLength > 4) {
      var b = new Uint8Array(r.data, 0, 4);
      if (b[0] === 0x25 && b[1] === 0x50 && b[2] === 0x44 && b[3] === 0x46) return 'application/pdf';
      if (b[0] === 0x89 && b[1] === 0x50) return 'image/png';
      if (b[0] === 0x50 && b[1] === 0x4B) return 'application/zip';
    }
    return 'application/octet-stream';
  }
  function aBlob(r) {
    if (r.data instanceof Blob) return r.data;
    var cuerpo = (r.data instanceof ArrayBuffer || ArrayBuffer.isView(r.data)) ? r.data
      : (typeof r.data === 'string' ? r.data : JSON.stringify(r.data));
    return new Blob([cuerpo], { type: tipoDe(r) });
  }
  function nombreDe(r, porDefecto) {
    var h = r.headers || {};
    var k = Object.keys(h).find(function (x) { return x.toLowerCase() === 'content-disposition'; });
    var m = k && /filename="([^"]*)"/.exec(h[k]);
    if (m) { try { return decodeURIComponent(m[1]); } catch (e) { return m[1]; } }
    return porDefecto || 'salida';
  }
  async function pedir(url) {
    var ruta = rutaApi(url);
    if (!ruta) throw new Error('No es una URL /api/ de este origen: ' + url);
    var r = await R.api.request('GET', ruta);
    if (r.status < 200 || r.status >= 300) {
      var msg = (r.data && (r.data.msg || r.data.message)) || (typeof r.data === 'string' ? r.data : '') || ('HTTP ' + r.status);
      var e = new Error(msg);
      e.respuesta = r;
      throw e;
    }
    return r;
  }

  /** Abre una salida /api/... (GET) en otra pestaña. La ventana se abre en el mismo gesto del usuario. */
  S.abrir = function (url, destino) {
    var ventana = null;
    try { ventana = global.open('', destino || '_blank'); } catch (e) { ventana = null; }
    return pedir(url).then(function (r) {
      var u = URL.createObjectURL(aBlob(r));
      if (ventana && !ventana.closed) ventana.location.href = u;
      else global.location.href = u;
      return r;
    }, function (e) {
      if (ventana && !ventana.closed) ventana.close();
      console.error('[RCJLocal.salidas] abrir', url, e);
      throw e;
    });
  };

  /** Descarga una salida /api/... (GET) con <a download>. */
  S.descargar = function (url, nombre) {
    return pedir(url).then(function (r) {
      var a = document.createElement('a');
      a.href = URL.createObjectURL(aBlob(r));
      a.download = nombre || nombreDe(r, 'salida');
      document.body.appendChild(a);
      a.click();
      a.remove();
      return r;
    });
  };

  /** Opcional: window.open('/api/...') pasa por S.abrir (el resto de URLs, al window.open original). */
  S.interceptarWindowOpen = function () {
    if (global.open && global.open.__rcjSalidas) return;
    var original = global.open;
    var nuevo = function (url, destino) {
      if (typeof url === 'string' && rutaApi(url)) {
        S.abrir(url, destino);
        return null;
      }
      return original.apply(global, arguments);
    };
    nuevo.__rcjSalidas = true;
    nuevo.original = original;
    global.open = nuevo;
  };
})(window);

/*
 * rcj-line-offline — área backend.
 * RCJLocal base: versión, flags, param(), ruta(), newId(), bus (BroadcastChannel).
 * Se puede cargar en cualquier orden respecto de los demás archivos de local/: nunca pisa
 * propiedades que otro archivo ya haya definido en window.RCJLocal.
 */
(function (global) {
  'use strict';

  var R = global.RCJLocal = global.RCJLocal || {};

  R.version = 'rcj-line-offline 1.0.0 (CMS d805502)';

  // ------------------------------------------------------------------ base de la app
  // Carpeta que contiene local/config.js (p.ej. '/' o '/tools/rcj-line-offline/').
  // Todas las páginas viven en la raíz de la app, así que ruta() arma rutas absolutas desde acá.
  if (!R.base) {
    var base = '/';
    try {
      var s = document.currentScript && document.currentScript.src;
      if (s) {
        base = new URL(s, global.location.href).pathname.replace(/local\/config\.js$/, '');
      } else {
        base = global.location.pathname.replace(/[^/]*$/, '');
      }
    } catch (e) { /* se queda en '/' */ }
    R.base = base;
  }

  // ------------------------------------------------------------------ flags (ESPEC §2)
  var FLAGS_POR_DEFECTO = {
    corregirBugsVisuales: false, // D4: x1.4 del cliente, j*4, statusCode==202, íconos FA4, fila Rule vacía
    tactil: true,                // D5: polyfill DnD + pulsación larga = clic derecho + modo selección
    persistirTimer: true,        // D5: el cronómetro del juez sobrevive a una recarga
    audioResume: true,           // D5: AudioContext.resume() en el primer gesto
    fotosOpcionales: true,       // D5: pre-chequeo sin fotos
    soloFirmaCapitan: false,     // D6: 3 firmas como el CMS
    recorridoTolerante: true,    // une empalmes mal dibujados al guardar/importar el mapa (cambios/aviso-recorrido.md)
    mostrarPorcentaje: true      // "% del máximo" del mapa en juez, firma y vista (local/porcentaje-maximo.js)
  };
  R.flagsPorDefecto = FLAGS_POR_DEFECTO;

  function leerFlagsGuardados() {
    try {
      var txt = global.localStorage.getItem('rcjLocalFlags');
      var obj = txt ? JSON.parse(txt) : {};
      return (obj && typeof obj === 'object') ? obj : {};
    } catch (e) {
      return {};
    }
  }

  if (!R.flags) {
    R.flags = Object.assign({}, FLAGS_POR_DEFECTO, leerFlagsGuardados());
  }

  R.setFlag = function (nombre, valor) {
    R.flags[nombre] = valor;
    try {
      var guardados = leerFlagsGuardados();
      guardados[nombre] = valor;
      global.localStorage.setItem('rcjLocalFlags', JSON.stringify(guardados));
    } catch (e) { /* sin localStorage: el flag queda solo en memoria */ }
    return valor;
  };

  // ------------------------------------------------------------------ query string
  R.param = function (nombre) {
    try {
      var v = new URLSearchParams(global.location.search).get(nombre);
      return v == null ? '' : v;
    } catch (e) {
      return '';
    }
  };

  // ------------------------------------------------------------------ ids tipo ObjectId
  // 8 hex de timestamp (segundos) + 10 hex aleatorios por sesión + 6 hex de contador, como un
  // ObjectId de MongoDB: ordenar por _id aproxima el orden de inserción.
  var aleatorioSesion = null;
  var contador = null;
  function hexAleatorio(nBytes) {
    var bytes = new Uint8Array(nBytes);
    try { global.crypto.getRandomValues(bytes); } catch (e) {
      for (var i = 0; i < nBytes; i++) bytes[i] = Math.floor(Math.random() * 256);
    }
    var out = '';
    for (var j = 0; j < bytes.length; j++) out += ('0' + bytes[j].toString(16)).slice(-2);
    return out;
  }
  if (!R.newId) {
    R.newId = function () {
      if (aleatorioSesion === null) {
        aleatorioSesion = hexAleatorio(5);
        contador = parseInt(hexAleatorio(3), 16);
      }
      contador = (contador + 1) % 0x1000000;
      var ts = Math.floor(Date.now() / 1000).toString(16);
      ts = ('00000000' + ts).slice(-8);
      return ts + aleatorioSesion + ('000000' + contador.toString(16)).slice(-6);
    };
  }

  // ObjectId.isValid de bson 4.x (mongoose 6.11): 24 hex o cualquier string de 12 bytes.
  if (!R.esIdValido) {
    R.esIdValido = function (id) {
      if (id == null) return false;
      if (typeof id === 'number') return true;
      if (typeof id !== 'string') {
        if (typeof id === 'object' && id.toHexString) return true;
        return false;
      }
      if (/^[0-9a-fA-F]{24}$/.test(id)) return true;
      if (id.length === 12) {
        try { return new TextEncoder().encode(id).length === 12; } catch (e) { return true; }
      }
      return false;
    };
  }

  if (!R.instanciaId) R.instanciaId = R.newId();

  // ------------------------------------------------------------------ bus entre pestañas
  if (!R.bus) {
    try {
      R.bus = new BroadcastChannel('rcj-line-offline');
    } catch (e) {
      // Navegador sin BroadcastChannel: bus nulo (solo la misma pestaña recibe eventos)
      R.bus = { postMessage: function () {}, addEventListener: function () {}, removeEventListener: function () {}, close: function () {}, onmessage: null, nulo: true };
    }
  }

  // ------------------------------------------------------------------ rutas CMS -> páginas locales
  function armar(pagina, params, queryExtra, hash) {
    var partes = [];
    for (var i = 0; i < params.length; i++) {
      partes.push(encodeURIComponent(params[i][0]) + '=' + encodeURIComponent(params[i][1]));
    }
    if (queryExtra) partes.push(queryExtra);
    return R.base + pagina + (partes.length ? '?' + partes.join('&') : '') + (hash || '');
  }

  /**
   * RCJLocal.ruta(rutaCms) -> ruta local (absoluta desde la raíz del sitio).
   * Conserva la query extra (p.ej. ?return=...). Una ruta que ya es una página local (*.html) o una
   * URL de otro origen se devuelve sin cambios. Tabla en ESPEC §4.
   */
  R.ruta = function (rutaCms) {
    if (rutaCms == null || rutaCms === '') return armar('index.html', [], '', '');
    var original = String(rutaCms);
    var s = original;

    // blob:/data: (PDF y PNG generados en el navegador) y about:/javascript: no son rutas del CMS.
    if (/^(blob|data|about|javascript):/i.test(s)) return original;

    if (/^[a-z][a-z0-9+.-]*:/i.test(s)) {
      try {
        var u = new URL(s);
        if (u.origin !== global.location.origin) return original;
        s = u.pathname + u.search + u.hash;
      } catch (e) {
        return original;
      }
    }

    var hash = '';
    var ih = s.indexOf('#');
    if (ih >= 0) { hash = s.slice(ih); s = s.slice(0, ih); }
    var query = '';
    var iq = s.indexOf('?');
    if (iq >= 0) { query = s.slice(iq + 1); s = s.slice(0, iq); }

    // Ya es una página local
    if (/\.html?$/i.test(s)) return original;

    var segs = s.split('/').filter(function (x) { return x !== ''; }).map(function (x) {
      try { return decodeURIComponent(x); } catch (e) { return x; }
    });
    var n = segs.length;
    var pagina = null;
    var params = [];

    if (segs[0] === 'line') {
      if (segs[1] === 'judge' && n === 3) {
        pagina = 'juez.html'; params.push(['run', segs[2]]);
      } else if (segs[1] === 'sign' && n === 3) {
        pagina = 'firma.html'; params.push(['run', segs[2]]);
      } else if (segs[1] === 'view' && (n === 3 || (n === 4 && segs[3] === 'iframe'))) {
        pagina = 'vista.html'; params.push(['run', segs[2]]);
        if (n === 4) params.push(['iframe', 'true']);
        // En el CMS /line/view/<id>?iframe=true rinde la vista NORMAL (solo /iframe cambia la plantilla).
        else query = query.split('&').filter(function (p) { return p && !/^iframe=/.test(p); }).join('&');
      } else if (segs[1] === 'input' && n === 3) {
        pagina = 'manual.html'; params.push(['run', segs[2]]);
      } else if (segs[1] === 'check' && n === 3) {
        pagina = 'manual.html'; params.push(['run', segs[2]]); params.push(['check', 'true']);
      } else if (n === 3) {
        pagina = 'corridas.html'; params.push(['competition', segs[1]]); params.push(['league', segs[2]]);
      } else if (n === 4 && segs[3] === 'ranking') {
        pagina = 'ranking.html'; params.push(['competition', segs[1]]); params.push(['league', segs[2]]);
      }
    } else if (segs[0] === 'admin' && n >= 2) {
      var iEditor = segs.indexOf('mapEditor');
      if (iEditor >= 0) {
        var idMapa = null;
        for (var k = iEditor + 1; k < n; k++) {
          if (/^[0-9a-fA-F]{24}$/.test(segs[k])) { idMapa = segs[k]; break; }
        }
        pagina = 'editor.html';
        if (idMapa) {
          params.push(['map', idMapa]);
        } else if (iEditor === 3) {
          params.push(['competition', segs[1]]); params.push(['league', segs[2]]);
        }
      } else if (segs[n - 1] === 'maps' && (n === 3 || n === 4)) {
        pagina = 'mapas.html'; params.push(['competition', segs[1]]);
      } else if (segs[n - 1] === 'games' && (n === 3 || n === 4)) {
        pagina = 'admin-corridas.html'; params.push(['competition', segs[1]]);
      } else if (n === 5 && segs[3] === 'games' && segs[4] === 'print') {
        pagina = 'planillas.html'; params.push(['competition', segs[1]]); params.push(['league', segs[2]]);
      }
    }

    if (!pagina) {
      pagina = 'index.html';
      params = [];
    }
    return armar(pagina, params, query, hash);
  };

  // ------------------------------------------------------------------ app instalable (PWA)
  // Manifiesto y local/pwa.js en todas las páginas (config.js se carga en todas).
  try {
    var head = document.head || document.getElementsByTagName('head')[0];
    if (head && !document.querySelector('link[rel="manifest"]')) {
      var manifiesto = document.createElement('link');
      manifiesto.rel = 'manifest';
      manifiesto.href = R.base + 'manifest.webmanifest';
      head.appendChild(manifiesto);
    }
    if (head && !document.querySelector('meta[name="theme-color"]')) {
      var tema = document.createElement('meta');
      tema.name = 'theme-color';
      tema.content = '#1f2937';
      head.appendChild(tema);
    }
    if (head && !global.__rcjPwaCargado) {
      global.__rcjPwaCargado = true;
      var pwa = document.createElement('script');
      pwa.src = R.base + 'local/pwa.js';
      pwa.defer = true;
      head.appendChild(pwa);
    }
  } catch (e) { /* sin PWA: la app funciona igual */ }
})(window);

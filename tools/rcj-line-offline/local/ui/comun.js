/*
 * rcj-line-offline — área admin.
 * RCJLocalUI: ayudas compartidas por las páginas de administración (index, corridas, admin-corridas,
 * mapas, configuracion). No contiene lógica del CMS: todo lo que toca datos pasa por RCJLocal.api
 * (las mismas rutas /api/* que usaría el CMS) o por las APIs nuevas de RCJLocal (ingestMap,
 * exportMap, semillas, backup).
 * Requiere local/config.js y local/nucleo/api.js cargados antes.
 */
(function (global) {
  'use strict';

  var UI = global.RCJLocalUI = global.RCJLocalUI || {};
  var CLAVE_ACTIVA = 'rcjLocalCompetenciaActiva';

  // ------------------------------------------------------------------ competencia activa
  UI.competenciaActiva = function () {
    try { return global.localStorage.getItem(CLAVE_ACTIVA) || ''; } catch (e) { return ''; }
  };
  UI.setCompetenciaActiva = function (id) {
    try {
      if (id) global.localStorage.setItem(CLAVE_ACTIVA, id);
      else global.localStorage.removeItem(CLAVE_ACTIVA);
    } catch (e) { /* sin localStorage */ }
  };
  // Competencia de la página: ?competition= y, si falta, la competencia activa elegida en el Inicio
  UI.competenciaDePagina = function () {
    return global.RCJLocal.param('competition') || UI.competenciaActiva();
  };

  // ------------------------------------------------------------------ URLs de páginas locales
  UI.url = function (pagina, params) {
    var partes = [];
    Object.keys(params || {}).forEach(function (k) {
      var v = params[k];
      if (v === undefined || v === null || v === '') return;
      partes.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
    });
    return global.RCJLocal.base + pagina + (partes.length ? '?' + partes.join('&') : '');
  };

  // Ruta de esta página (para ?return=): conserva la query, que en la app local lleva la competencia
  UI.rutaActual = function () {
    return global.location.pathname + global.location.search;
  };

  /**
   * Rutas del CMS que RCJLocal.ruta (config del área backend) todavía no traduce.
   * Se resuelven acá y el resto se delega en RCJLocal.ruta. Reportado al backend.
   *   /admin/<cid>/<league>/games/ranking  -> ranking.html?competition&league (ranking imprimible, 04 §4.7)
   *   /admin/<cid>/<league>/games/bulk     -> admin-corridas.html?competition&league (alta masiva no portada)
   *   /admin, /admin/<cid>                 -> index.html (consola de administración no portada)
   */
  UI.ruta = function (rutaCms) {
    var s = String(rutaCms == null ? '' : rutaCms);
    var query = '';
    var iq = s.indexOf('?');
    var camino = iq >= 0 ? s.slice(0, iq) : s;
    if (iq >= 0) query = s.slice(iq + 1);
    var m = /^\/admin\/([^/?#]+)\/([^/?#]+)\/games\/ranking\/?$/.exec(camino);
    if (m) return UI.url('ranking.html', { competition: m[1], league: m[2] }) + (query ? '&' + query : '');
    m = /^\/admin\/([^/?#]+)\/([^/?#]+)\/games\/bulk\/?$/.exec(camino);
    if (m) return UI.url('admin-corridas.html', { competition: m[1], league: m[2] }) + (query ? '&' + query : '');
    return global.RCJLocal.ruta(s);
  };

  // ------------------------------------------------------------------ textos
  UI.ESTADOS = {
    '-1': 'Sin checkpoints',
    0: 'Antes de la corrida',
    1: 'Checkpoints definidos',
    2: 'En curso',
    3: 'Revisión del registro',
    4: 'Terminada',
    5: 'Aprobación en curso',
    6: 'Aprobada'
  };
  UI.textoEstado = function (s) {
    return UI.ESTADOS[s] !== undefined ? UI.ESTADOS[s] : ('Estado ' + s);
  };
  UI.bytesLegibles = function (n) {
    if (n == null || isNaN(n)) return '—';
    var u = ['B', 'KB', 'MB', 'GB', 'TB'];
    var i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return (i === 0 ? n : n.toFixed(1)).toString().replace('.', ',') + ' ' + u[i];
  };
  function dos(n) { return ('0' + n).slice(-2); }
  UI.fechaArchivo = function (d) {
    d = d || new Date();
    return d.getFullYear() + '-' + dos(d.getMonth() + 1) + '-' + dos(d.getDate()) + '_' + dos(d.getHours()) + dos(d.getMinutes());
  };
  UI.mensajeError = function (e) {
    if (!e) return 'Error desconocido';
    if (typeof e === 'string') return e;
    if (e.data && typeof e.data === 'object') return e.data.err || e.data.msg || e.data.message || JSON.stringify(e.data);
    if (e.data && typeof e.data === 'string') return e.data;
    return e.message || String(e);
  };

  // ------------------------------------------------------------------ archivos
  /** Descarga un archivo generado en el navegador. Deja una copia en UI.ultimaDescarga (pruebas). */
  UI.descargar = function (nombre, contenido, tipo) {
    var blob = (typeof Blob !== 'undefined' && contenido instanceof Blob)
      ? contenido
      : new Blob([contenido], { type: tipo || 'application/octet-stream' });
    UI.ultimaDescarga = { nombre: nombre, blob: blob };
    var url = global.URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = nombre;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      if (a.parentNode) a.parentNode.removeChild(a);
      global.URL.revokeObjectURL(url);
    }, 1500);
    return blob;
  };

  UI.leerArchivoTexto = function (archivo) {
    if (archivo && typeof archivo.text === 'function') return archivo.text();
    return new Promise(function (resolve, reject) {
      var fr = new FileReader();
      fr.onload = function () { resolve(fr.result); };
      fr.onerror = function () { reject(fr.error); };
      fr.readAsText(archivo);
    });
  };

  function textoDeDatos(data) {
    try {
      if (data instanceof ArrayBuffer || ArrayBuffer.isView(data)) return new TextDecoder().decode(data);
    } catch (e) { /* sigue */ }
    if (typeof data === 'string') return data;
    try { return JSON.stringify(data); } catch (e) { return String(data); }
  }
  function mensajeDeRespuesta(r) {
    var txt = textoDeDatos(r.data);
    try {
      var o = JSON.parse(txt);
      return o.msg || o.err || o.message || txt;
    } catch (e) {
      return txt || ('HTTP ' + r.status);
    }
  }
  function cabecera(headers, nombre) {
    var k = Object.keys(headers || {}).find(function (h) { return h.toLowerCase() === nombre; });
    return k ? headers[k] : '';
  }

  /**
   * Pide una salida binaria (PDF/PNG) al backend local. En el CMS estas URLs se abrían con
   * window.open o con <a href="/api/..."> directo al servidor; offline no hay servidor, así que se
   * piden por RCJLocal.api.request y se abren/descargan como Blob.
   * opciones: {nombreDescarga?, tipo?, silencioso?, ventana?}
   * Devuelve Promise<{ok, status, mensaje, blob}>.
   */
  UI.salidaApi = async function (metodo, url, cuerpo, opciones) {
    opciones = opciones || {};
    var r;
    try {
      r = await global.RCJLocal.api.request(metodo, url, cuerpo, { responseType: 'arraybuffer' });
    } catch (e) {
      r = { status: 500, data: JSON.stringify({ msg: String((e && e.message) || e) }), headers: {} };
    }
    if (r.status >= 200 && r.status < 300) {
      var tipo = cabecera(r.headers, 'content-type') || opciones.tipo || 'application/octet-stream';
      var blob = new Blob([r.data], { type: tipo });
      if (opciones.nombreDescarga) {
        UI.descargar(opciones.nombreDescarga, blob);
      } else {
        var objUrl = global.URL.createObjectURL(blob);
        if (opciones.ventana && !opciones.ventana.closed) opciones.ventana.location.href = objUrl;
        else global.open(objUrl, '_blank');
      }
      return { ok: true, status: r.status, blob: blob };
    }
    if (opciones.ventana && !opciones.ventana.closed) opciones.ventana.close();
    var mensaje = mensajeDeRespuesta(r);
    if (!opciones.silencioso && global.swal) {
      global.swal(r.status === 501 ? 'Salida no disponible' : 'No se pudo generar la salida', mensaje, r.status === 501 ? 'info' : 'error');
    }
    return { ok: false, status: r.status, mensaje: mensaje };
  };

  /** Igual que salidaApi pero abre la ventana ANTES del pedido asíncrono (evita el bloqueo de popups). */
  UI.abrirApi = function (metodo, url, cuerpo, opciones) {
    opciones = Object.assign({}, opciones || {});
    if (!opciones.nombreDescarga && !opciones.ventana) {
      try { opciones.ventana = global.open('', '_blank'); } catch (e) { opciones.ventana = null; }
    }
    return UI.salidaApi(metodo, url, cuerpo, opciones);
  };

  // ------------------------------------------------------------------ corridas
  async function pedir(metodo, url, cuerpo) {
    var r = await global.RCJLocal.api.request(metodo, url, cuerpo);
    if (r.status < 200 || r.status >= 300) {
      var err = new Error((r.data && (r.data.err || r.data.msg || r.data.message)) || ('HTTP ' + r.status + ' en ' + metodo + ' ' + url));
      err.respuesta = r;
      throw err;
    }
    return r.data;
  }
  UI.pedir = pedir;

  function nombreLibre(base, existentes) {
    var n = existentes.length + 1;
    var nombre = base + ' ' + n;
    while (existentes.indexOf(nombre) >= 0) { n++; nombre = base + ' ' + n; }
    return nombre;
  }

  /**
   * Crea una corrida con POST /api/runs/line (E13, mismo payload que admin/games.js:91-104).
   * Si falta la ronda o la pista, las resuelve:
   *   ronda: la primera ronda (orden natural) en la que el equipo todavía no tiene corrida (unicidad
   *          round+team del CMS); si no hay, crea "Práctica N".
   *   pista: la primera pista; si no hay ninguna, crea "Cancha 1".
   *   normalizationGroup: si no se indica, el nombre de la ronda.
   * opciones: {competition, map, team, round?, field?, normalizationGroup?, startTime?}
   * Devuelve Promise<{id, round:{_id,name,creada}, field:{_id,name,creada}}>.
   */
  UI.crearCorrida = async function (opciones) {
    var cid = opciones.competition;
    if (!cid) throw new Error('Falta la competencia');
    if (!opciones.map) throw new Error('Elegí un mapa');
    if (!opciones.team) throw new Error('Elegí un equipo');
    var ronda = null, cancha = null;

    if (opciones.round) {
      ronda = { _id: opciones.round, creada: false };
    } else {
      var rondas = await pedir('GET', '/api/competitions/' + cid + '/rounds');
      var corridas = await pedir('GET', '/api/runs/line/competition/' + cid + '?minimum=true');
      var usadas = corridas
        .filter(function (r) { return r.team && r.team._id === opciones.team && r.round; })
        .map(function (r) { return r.round._id; });
      var libre = rondas.find(function (r) { return usadas.indexOf(r._id) < 0; });
      if (libre) {
        ronda = { _id: libre._id, name: libre.name, creada: false };
      } else {
        var nombre = nombreLibre('Práctica', rondas.map(function (r) { return r.name; }));
        var nueva = await pedir('POST', '/api/rounds', { name: nombre, competition: cid });
        ronda = { _id: nueva.id, name: nombre, creada: true };
      }
    }

    if (opciones.field) {
      cancha = { _id: opciones.field, creada: false };
    } else {
      var pistas = await pedir('GET', '/api/competitions/' + cid + '/fields');
      if (pistas.length) {
        cancha = { _id: pistas[0]._id, name: pistas[0].name, creada: false };
      } else {
        var nuevaPista = await pedir('POST', '/api/fields', { name: 'Cancha 1', competition: cid });
        cancha = { _id: nuevaPista.id, name: 'Cancha 1', creada: true };
      }
    }

    var grupo = opciones.normalizationGroup;
    if (grupo === undefined && ronda.name) grupo = ronda.name;
    var run = {
      round: ronda._id,
      team: opciones.team,
      field: cancha._id,
      competition: cid,
      startTime: opciones.startTime || Date.now(),
      normalizationGroup: grupo
    };
    run.map = opciones.map;
    var creada = await pedir('POST', '/api/runs/line', run);
    return { id: creada.id, round: ronda, field: cancha };
  };

  /** URL del juez para una corrida, con ?return= a la página indicada (o a la actual). */
  UI.urlJuez = function (runId, volverA) {
    return global.RCJLocal.ruta('/line/judge/' + runId + '?return=' + encodeURIComponent(volverA || UI.rutaActual()));
  };

  // ------------------------------------------------------------------ directiva de archivos
  /**
   * Directiva AngularJS `rcj-archivo="expr($archivos, $input)"` para <input type="file">: evalúa la
   * expresión en cada change con la lista de File y vacía el input (así se puede volver a elegir el
   * mismo archivo). Cada página la registra: angular.module('X').directive('rcjArchivo', RCJLocalUI.directivaArchivo)
   */
  UI.directivaArchivo = ['$parse', function ($parse) {
    return {
      restrict: 'A',
      link: function (scope, el, attrs) {
        var fn = $parse(attrs.rcjArchivo);
        el.on('change', function () {
          var input = el[0];
          var archivos = Array.prototype.slice.call(input.files || []);
          if (!archivos.length) return;
          scope.$apply(function () { fn(scope, { $archivos: archivos, $input: input }); });
          try { input.value = ''; } catch (e) { /* navegador viejo */ }
        });
      }
    };
  }];

  // ------------------------------------------------------------------ fotos de equipo
  /** Achica una imagen a un JPEG de lado máximo `lado` px y devuelve un dataURL. */
  UI.imagenADataURL = function (archivo, lado) {
    lado = lado || 800;
    return new Promise(function (resolve, reject) {
      var fr = new FileReader();
      fr.onerror = function () { reject(fr.error); };
      fr.onload = function () {
        var img = new Image();
        img.onerror = function () { reject(new Error('No se pudo leer la imagen')); };
        img.onload = function () {
          var escala = Math.min(1, lado / Math.max(img.width, img.height));
          var c = document.createElement('canvas');
          c.width = Math.max(1, Math.round(img.width * escala));
          c.height = Math.max(1, Math.round(img.height * escala));
          c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
          resolve(c.toDataURL('image/jpeg', 0.85));
        };
        img.src = fr.result;
      };
      fr.readAsDataURL(archivo);
    });
  };
})(window);

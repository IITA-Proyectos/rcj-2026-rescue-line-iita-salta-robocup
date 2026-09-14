/*
 * rcj-line-offline — área backend.
 * RCJLocal.api: emulación en el navegador de las rutas /api/* del CMS rcj-rescue-cms (commit d805502)
 * que usan las páginas de Rescue Line 2026 (E1..E16 de analysis/08 §5.5) y las de administración
 * (competencias, rondas, canchas, equipos, corridas, mapas).
 *
 * Además: RCJLocal.ingestMap, RCJLocal.exportMap, RCJLocal.semillas, RCJLocal.backup,
 * RCJLocal.emitirSocket.
 *
 * Reglas de este archivo:
 *  - La lógica de dominio NO está acá: se llama a RCJLocal.PFs (pathFinder servidor verbatim),
 *    RCJLocal.initLine (initRunData verbatim), RCJLocal.calculateScore (2026.js verbatim) y
 *    RCJLocal.copyProperties (verbatim).
 *  - Lo que sí está acá es lo que en el CMS hacían Express + mongoose: orden de rutas, next(),
 *    poblado de referencias, casteo y validación de esquema, hooks pre-save, respuestas y códigos.
 *  - Cada diferencia con el CMS está documentada en cambios/backend.md con archivo:línea.
 *  - Orden de carga recomendado: config.js, nucleo/store.js, nucleo/pathfinder-servidor.js,
 *    nucleo/init-run.js, nucleo/score-2026.js, nucleo/copy-properties.js, nucleo/api.js,
 *    nucleo/ranking.js, io-shim.js, http-backend.js (todas las dependencias se resuelven al llamar,
 *    no al cargar).
 */
(function () {
  'use strict';

  var R = window.RCJLocal = window.RCJLocal || {};

  var COLS = ['competitions', 'rounds', 'teams', 'fields', 'lineMaps', 'lineRuns', 'tileSets', 'meta'];

  // models/competition.js:13-60 (con leagues.json)
  var LINE_LEAGUES = ['Line', 'LineNL'];
  var LEAGUES = ['Line', 'LineNL', 'Maze', 'MazeNL', 'Erebus'];
  var SUM_OF_BEST_N_GAMES = 'SUM_OF_BEST_N_GAMES';
  var MEAN_OF_NORMALIZED_BEST_N_GAMES = 'MEAN_OF_NORMALIZED_BEST_N_GAMES';
  var MEAN_OF_NORMALIZED_BEST_N_GAMES_NORMALIZED_DOCUMENT = 'MEAN_OF_NORMALIZED_BEST_N_GAMES_NORMALIZED_DOCUMENT';
  var GAMES_DOCUMENT_CHALLENGE = 'GAMES_DOCUMENT_CHALLENGE';
  var NORMALIZED_RANKING_MODE = [MEAN_OF_NORMALIZED_BEST_N_GAMES, MEAN_OF_NORMALIZED_BEST_N_GAMES_NORMALIZED_DOCUMENT, GAMES_DOCUMENT_CHALLENGE];
  var RANKING_MODE = [SUM_OF_BEST_N_GAMES].concat(NORMALIZED_RANKING_MODE);
  var ACCESSLEVEL_SUPERADMIN = 15; // models/user.js:49-55
  var DIRS = ['top', 'right', 'bottom', 'left'];
  var VICTIM_TYPE = ['LIVE', 'DEAD', 'KIT']; // models/lineRun.js:16
  var ZONE_TYPE = ['RED', 'GREEN'];          // models/lineRun.js:17

  R.constantesCMS = {
    LINE_LEAGUES: LINE_LEAGUES, LEAGUES: LEAGUES, RANKING_MODE: RANKING_MODE,
    NORMALIZED_RANKING_MODE: NORMALIZED_RANKING_MODE, SUM_OF_BEST_N_GAMES: SUM_OF_BEST_N_GAMES,
    MEAN_OF_NORMALIZED_BEST_N_GAMES: MEAN_OF_NORMALIZED_BEST_N_GAMES,
    DOCUMENT_RANKING_MODE: [MEAN_OF_NORMALIZED_BEST_N_GAMES_NORMALIZED_DOCUMENT, GAMES_DOCUMENT_CHALLENGE]
  };

  // ======================================================================================
  // Utilidades
  // ======================================================================================
  function esIdValido(id) {
    if (R.esIdValido) return R.esIdValido(id);
    return typeof id === 'string' && /^[0-9a-fA-F]{24}$/.test(id);
  }
  function nuevoId() { return R.newId(); }
  function ahoraISO() { return new Date().toISOString(); }
  function clonarProfundo(v) {
    if (v === undefined) return undefined;
    try { return structuredClone(v); } catch (e) { return JSON.parse(JSON.stringify(v)); }
  }
  function clonarJSON(v) {
    if (v === undefined) return undefined;
    return JSON.parse(JSON.stringify(v));
  }
  function tieneProp(o, k) { return o != null && Object.prototype.hasOwnProperty.call(o, k); }
  function ordenNatural(a, b) {
    var ca = a.createdAt || '', cb = b.createdAt || '';
    if (ca < cb) return -1;
    if (ca > cb) return 1;
    return a._id < b._id ? -1 : (a._id > b._id ? 1 : 0);
  }
  // Casteo de un id de consulta como lo hace mongoose con ObjectId (24 hex en minúsculas)
  function idConsulta(v) {
    try { return CAST.ObjectId(v); } catch (e) { return undefined; }
  }

  // ------------------------------------------------------------------ respuestas HTTP
  var CT_JSON = 'application/json; charset=utf-8';
  var CT_HTML = 'text/html; charset=utf-8';
  var TEXTOS_ESTADO = {
    200: 'OK', 201: 'Created', 202: 'Accepted', 204: 'No Content', 400: 'Bad Request', 401: 'Unauthorized',
    403: 'Forbidden', 404: 'Not Found', 500: 'Internal Server Error', 501: 'Not Implemented'
  };
  function json(status, data, extra) {
    return { status: status, data: data, headers: Object.assign({ 'Content-Type': CT_JSON }, extra || {}) };
  }
  function texto(status, str) { return { status: status, data: String(str), headers: { 'Content-Type': CT_HTML } }; }
  function vacio(status) { return { status: status, data: '', headers: {} }; }
  // res.send(valor) de Express: null/undefined -> cuerpo vacío; string -> html; objeto -> json
  function enviar(status, valor) {
    if (valor === null || valor === undefined) return vacio(status);
    if (typeof valor === 'string') return texto(status, valor);
    return json(status, valor);
  }
  function noEncontrado() { return json(404, { message: '404 Not found' }); } // app.js:287-290
  function errorInterno(e) {
    return json(500, { msg: 'Error interno del backend local', err: String((e && e.message) || e) });
  }
  function ErrorHttp(respuesta) { this.respuestaHttp = respuesta; this.message = 'ErrorHttp ' + respuesta.status; }
  ErrorHttp.prototype = Object.create(Error.prototype);

  // ======================================================================================
  // Emulación de mongoose 6.11: casteo, defaults y validación de esquema
  // ======================================================================================
  var RESTAURAR = { restaurar: true };

  function C(t, o) { var c = { t: t }; if (o) { for (var k in o) c[k] = o[k]; } return c; }
  function NE(campos) { return { t: 'Nested', campos: campos }; }
  function DA(campos) { return { t: 'DocArray', campos: campos }; }
  function AR(de) { return { t: 'Array', de: de }; }
  function setVacio(x) { return function (v) { return v === '' ? x : v; }; }

  function tipoValor(v) {          // mongoose/lib/error/cast.js getValueType
    if (v == null) return '' + v;
    var t = typeof v;
    if (t !== 'object') return t;
    if (typeof v.constructor !== 'function') return t;
    return v.constructor.name;
  }
  function textoValor(v) {         // aproximación de util.inspect
    var s;
    if (typeof v === 'string') s = v;
    else {
      try { s = (v !== null && typeof v === 'object') ? JSON.stringify(v) : String(v); } catch (e) { s = String(v); }
    }
    return '"' + s + '"';
  }
  function errorCast(tipo, valor, ruta, motivo) {
    var msg = 'Cast to ' + tipo + ' failed for value ' + textoValor(valor) + ' (type ' + tipoValor(valor) + ') at path "' + ruta + '"';
    if (motivo) msg += ' because of "' + motivo + '"';
    return { ruta: ruta, mensaje: msg };
  }

  // mongoose/lib/cast/*.js (6.11). Lanzan [tipo, motivo] si no se puede castear.
  var CAST = {
    Number: function (v) {
      if (v != null && typeof v === 'object' && typeof v._id !== 'undefined') v = v._id; // schema/number.js cast
      if (v == null) return v;
      if (v === '') return null;
      if (typeof v === 'string' || typeof v === 'boolean') v = Number(v);
      if (typeof v === 'number') {
        if (isNaN(v)) throw ['Number', null];
        return v;
      }
      if (Array.isArray(v)) throw ['Number', null];
      if (v instanceof Number) return v.valueOf();
      if (typeof v.valueOf === 'function') {
        var n = Number(v.valueOf());
        if (isNaN(n)) throw ['Number', null];
        return n;
      }
      throw ['Number', null];
    },
    Boolean: function (v) {
      if (v === true || v === 'true' || v === 1 || v === '1' || v === 'yes') return true;
      if (v === false || v === 'false' || v === 0 || v === '0' || v === 'no') return false;
      if (v == null) return v;
      throw ['Boolean', 'CastError'];
    },
    String: function (v) {
      if (v == null) return v;
      if (v._id && typeof v._id === 'string') return v._id;
      if (v.toString && v.toString !== Object.prototype.toString && !Array.isArray(v)) return v.toString();
      throw ['string', null];
    },
    ObjectId: function (v) {
      if (v == null) return v;
      if (typeof v === 'object' && v._id) v = v._id;
      var s = (v !== null && v !== undefined && v.toString instanceof Function) ? v.toString() : v;
      if (typeof s === 'string') {
        if (/^[0-9a-fA-F]{24}$/.test(s)) return s.toLowerCase();
        if (s.length === 12) {
          var b = new TextEncoder().encode(s);
          if (b.length === 12) {
            var hex = '';
            for (var i = 0; i < b.length; i++) hex += ('0' + b[i].toString(16)).slice(-2);
            return hex;
          }
        }
      }
      throw ['ObjectId', 'BSONTypeError'];
    },
    Date: function (v) {
      if (v == null) return v;
      if (v === '') return null;
      var d = (v instanceof Date) ? v : new Date((typeof v === 'string' && /^-?\d+$/.test(v)) ? Number(v) : v);
      if (isNaN(d.getTime())) throw ['date', null];
      return d.toISOString();
    }
  };

  function castHoja(spec, valor, ruta) {
    if (spec.set) valor = spec.set(valor);
    try {
      return { valor: CAST[spec.t](valor) };
    } catch (e) {
      if (Array.isArray(e)) return { error: errorCast(e[0], valor, ruta, e[1]) };
      throw e;
    }
  }

  function valorDefecto(spec, ruta, errores) {
    if (spec.auto) return nuevoId();
    if (spec.t === 'Nested') return castObjeto(spec.campos, {}, ruta, errores, undefined, false);
    if (spec.t === 'Array' || spec.t === 'DocArray') return [];
    if (tieneProp(spec, 'def')) return typeof spec.def === 'function' ? spec.def() : clonarProfundo(spec.def);
    return undefined;
  }

  // Castea un campo. Devuelve el valor casteado o RESTAURAR (en mongoose el $set fallido no asigna).
  function castCampo(spec, valor, ruta, errores, previo) {
    var i, out;
    switch (spec.t) {
      case 'Nested':
        if (valor === null) return null;
        if (typeof valor !== 'object' || Array.isArray(valor)) {
          errores.push(errorCast('Object', valor, ruta));
          return RESTAURAR;
        }
        return castObjeto(spec.campos, valor, ruta, errores, previo, false);
      case 'DocArray':
        if (valor == null) return valor;
        if (!Array.isArray(valor)) valor = [valor];
        out = new Array(valor.length);
        for (i = 0; i < valor.length; i++) {
          if (!(i in valor)) continue;
          var el = valor[i];
          if (!el) { out[i] = el; continue; } // schema/documentarray.js cast: `if (!value[i]) continue;`
          if (typeof el !== 'object' || Array.isArray(el)) {
            errores.push(errorCast('Embedded', el, ruta + '.' + i));
            return RESTAURAR;
          }
          out[i] = castObjeto(spec.campos, el, ruta + '.' + i, errores, previo ? previo[i] : undefined, true);
        }
        return out;
      case 'Array':
        if (valor == null) return valor;
        if (!Array.isArray(valor)) valor = [valor];
        out = new Array(valor.length);
        for (i = 0; i < valor.length; i++) {
          if (!(i in valor)) continue;
          if (valor[i] == null) { out[i] = valor[i]; continue; }
          var r = castHoja(spec.de, valor[i], ruta + '.' + i);
          if (r.error) {
            errores.push({ ruta: ruta + '.' + i, mensaje: 'Cast to [' + spec.de.t + '] failed for value ' + textoValor(valor) + ' (type ' + tipoValor(valor[i]) + ') at path "' + ruta + '.' + i + '"' });
            return RESTAURAR;
          }
          out[i] = r.valor;
        }
        return out;
      default:
        var rh = castHoja(spec, valor, ruta);
        if (rh.error) { errores.push(rh.error); return RESTAURAR; }
        return rh.valor;
    }
  }

  // Castea un objeto contra `campos` en el orden del esquema (modo strict: descarta claves desconocidas).
  // Subdocumentos: `_id` al final (como los subdocs de mongoose); raíz: `_id` es el primer campo.
  function castObjeto(campos, obj, ruta, errores, previo, esSubdoc) {
    var out = {};
    for (var k in campos) {
      var spec = campos[k];
      var rutaK = ruta ? ruta + '.' + k : k;
      var prevK = (previo != null && typeof previo === 'object') ? previo[k] : undefined;
      if (tieneProp(obj, k) && obj[k] !== undefined) {
        var v = castCampo(spec, obj[k], rutaK, errores, prevK);
        if (v === RESTAURAR) {
          if (prevK !== undefined) out[k] = clonarProfundo(prevK);
          else {
            var d0 = valorDefecto(spec, rutaK, []);
            if (d0 !== undefined) out[k] = d0;
          }
        } else if (v !== undefined) {
          out[k] = v;
        }
      } else {
        var d = valorDefecto(spec, rutaK, errores);
        if (d !== undefined) out[k] = d;
      }
    }
    if (esSubdoc) {
      if (tieneProp(obj, '_id') && obj._id != null) {
        var rid = castHoja(C('ObjectId'), obj._id, ruta + '._id');
        if (rid.error) {
          errores.push(rid.error);
          out._id = (previo && previo._id) || nuevoId();
        } else {
          out._id = rid.valor;
        }
      } else {
        out._id = nuevoId();
      }
    }
    return out;
  }

  function requeridoOk(t, v) {
    switch (t) {
      case 'Number': return typeof v === 'number';
      case 'String': return typeof v === 'string' && v.length > 0;
      case 'Boolean': return v === true || v === false;
      case 'ObjectId': return typeof v === 'string' && v.length > 0;
      case 'Date': return v != null;
      default: return v != null;
    }
  }

  // SchemaType.doValidate: required primero, luego validadores en orden de declaración; el entero
  // de mongoose-integer se agrega por plugin (último). Se reporta solo el primer error por ruta.
  function validarHoja(spec, v, ruta, rel, errores) {
    if (spec.required && !requeridoOk(spec.t, v)) {
      errores.push({ ruta: ruta, mensaje: 'Path `' + rel + '` is required.' });
      return;
    }
    if (v === undefined) return;
    for (var k in spec) {
      if (k === 'min' && v !== null && v < spec.min) {
        errores.push({ ruta: ruta, mensaje: 'Path `' + rel + '` (' + v + ') is less than minimum allowed value (' + spec.min + ').' });
        return;
      }
      if (k === 'max' && v !== null && v > spec.max) {
        errores.push({ ruta: ruta, mensaje: 'Path `' + rel + '` (' + v + ') is more than maximum allowed value (' + spec.max + ').' });
        return;
      }
      if (k === 'enum' && spec.enum.indexOf(v) === -1) {
        errores.push({ ruta: ruta, mensaje: '`' + v + '` is not a valid enum value for path `' + rel + '`.' });
        return;
      }
      if (k === 'validar' && !spec.validar(v)) {
        errores.push({ ruta: ruta, mensaje: 'Validator failed for path `' + rel + '` with value `' + v + '`' });
        return;
      }
    }
    if (spec.integer && v !== null && !(typeof v === 'number' && v % 1 === 0)) {
      errores.push({ ruta: ruta, mensaje: 'Error, expected `' + rel + '` to be an integer.' });
    }
  }

  function validarObjeto(campos, doc, ruta, rel, errores) {
    for (var k in campos) {
      var spec = campos[k];
      var v = (doc != null && typeof doc === 'object') ? doc[k] : undefined;
      var rutaK = ruta ? ruta + '.' + k : k;
      var relK = rel ? rel + '.' + k : k;
      if (spec.t === 'Nested') {
        validarObjeto(spec.campos, v, rutaK, relK, errores);
      } else if (spec.t === 'DocArray') {
        if (Array.isArray(v)) {
          for (var i = 0; i < v.length; i++) {
            if (v[i] && typeof v[i] === 'object') validarObjeto(spec.campos, v[i], rutaK + '.' + i, '', errores);
          }
        }
      } else if (spec.t === 'Array') {
        /* SchemaArray: `min` sobre [Number] no genera validador (ver cambios/backend.md) */
      } else {
        validarHoja(spec, v, rutaK, relK, errores);
      }
    }
    return errores;
  }

  function mensajeValidacion(modelo, errores) {
    var vistos = {};
    var partes = [];
    errores.forEach(function (e) {
      if (vistos[e.ruta]) return;
      vistos[e.ruta] = true;
      partes.push(e.ruta + ': ' + e.mensaje);
    });
    return modelo + ' validation failed: ' + partes.join(', ');
  }

  // ---------------------------------------------------------------- esquemas
  // models/lineRun.js:19-90 (+ mongoose-timestamp y __v)
  var ESQ_RUN = {
    _id: C('ObjectId', { auto: true }),
    competition: C('ObjectId', { required: true }),
    round: C('ObjectId', { required: true }),
    team: C('ObjectId'),
    field: C('ObjectId', { required: true }),
    map: C('ObjectId', { required: true }),
    group: C('Number', { min: 0 }),
    normalizationGroup: C('String'),
    adjustment: C('Number', { def: 0, min: -100 }),
    tiles: DA({
      scoredItems: DA({
        item: C('String', { def: '' }),
        scored: C('Boolean', { def: false }),
        count: C('Number', { def: 1 })
      })
    }),
    LoPs: AR(C('Number')),
    evacuationLevel: C('Number', { def: 1, validar: function (l) { return l == 1 || l == 2; } }),
    kitLevel: C('Number', { def: 1, validar: function (l) { return l == 1 || l == 2; } }),
    exitBonus: C('Boolean', { def: false }),
    rescueOrder: DA({
      victimType: C('String', { enum: VICTIM_TYPE }),
      zoneType: C('String', { enum: ZONE_TYPE })
    }),
    score: C('Number', { min: -1000, def: 0 }),
    raw_score: C('Number', { min: -1000, def: 0 }),
    multiplier: C('Number', { min: 1.0, def: 1.0 }),
    showedUp: C('Boolean', { def: false }),
    time: NE({
      minutes: C('Number', { min: 0, max: 8, def: 0 }),
      seconds: C('Number', { min: 0, max: 59, def: 0 })
    }),
    status: C('Number', { min: -1, def: 0 }),
    sign: NE({
      captain: C('String', { def: '' }),
      referee: C('String', { def: '' }),
      referee_as: C('String', { def: '' })
    }),
    started: C('Boolean', { def: false }),
    comment: C('String', { def: '' }),
    startTime: C('Number', { def: 0 }),
    nl: NE({
      liveVictim: DA({ found: C('Boolean', { def: false }), identified: C('Boolean', { def: false }) }),
      deadVictim: DA({ found: C('Boolean', { def: false }), identified: C('Boolean', { def: false }) })
    }),
    isNL: C('Boolean', { def: false }),
    createdAt: C('Date'),
    updatedAt: C('Date'),
    __v: C('Number', { def: 0 })
  };

  // models/lineMap.js:27-124
  var ESQ_MAPA = {
    _id: C('ObjectId', { auto: true }),
    competition: C('ObjectId', { required: true }),
    league: C('String', { enum: LINE_LEAGUES, required: true }),
    tileSet: C('ObjectId', { required: true }),
    name: C('String', { required: true }),
    height: C('Number', { integer: true, required: true, min: 1 }),
    width: C('Number', { integer: true, required: true, min: 1 }),
    length: C('Number', { integer: true, required: true, min: 1 }),
    duration: C('Number', { integer: true, min: 0, def: 480 }),
    indexCount: C('Number', { integer: true, min: 1 }),
    EvacuationAreaLoPIndex: C('Number', { def: 0 }),
    tiles: DA({
      x: C('Number', { integer: true, required: true }),
      y: C('Number', { integer: true, required: true }),
      z: C('Number', { integer: true, required: true }),
      tileType: C('ObjectId', { required: true }),
      rot: C('Number', { required: true, validar: function (a) { return a == 0 || a == 90 || a == 180 || a == 270; } }),
      items: NE({
        obstacles: C('Number', { integer: true, required: true, def: 0, min: 0, set: setVacio(0) }),
        speedbumps: C('Number', { integer: true, required: true, def: 0, min: 0, set: setVacio(0) }),
        rampPoints: C('Boolean', { def: false, required: true, set: setVacio(false) })
      }),
      index: AR(C('Number')),
      next: AR(C('String')),
      next_dir: AR(C('String')),
      levelUp: C('String', { enum: DIRS }),
      levelDown: C('String', { enum: DIRS }),
      checkPoint: C('Boolean', { def: false, required: true, set: setVacio(false) }),
      evacEntrance: C('Number', { def: -1, set: setVacio(-1) }),
      evacExit: C('Number', { def: -1, set: setVacio(-1) })
    }),
    startTile: NE({
      x: C('Number', { integer: true, required: true, min: -1 }),
      y: C('Number', { integer: true, required: true, min: -1 }),
      z: C('Number', { integer: true, required: true, min: -1 })
    }),
    startTile2: NE({
      x: C('Number', { integer: true, required: true, min: -1 }),
      y: C('Number', { integer: true, required: true, min: -1 }),
      z: C('Number', { integer: true, required: true, min: -1 })
    }),
    finished: C('Boolean', { def: false, set: setVacio(false) }),
    victims: NE({
      live: C('Number', { integer: true, min: 0, max: 100, def: 2, set: setVacio(0) }),
      dead: C('Number', { integer: true, min: 0, max: 100, def: 1, set: setVacio(0) })
    }),
    __v: C('Number', { def: 0 })
  };

  // models/competition.js:83-202 (sin publicToken/registration, que tienen select:false)
  var ESQ_COMPETENCIA = {
    _id: C('ObjectId', { auto: true }),
    name: C('String'),
    logo: C('String', { def: '/images/noLogo.png' }),
    bkColor: C('String', { def: '#fff' }),
    color: C('String', { def: '#000' }),
    message: C('String', { def: '' }),
    description: C('String', { def: '' }),
    preparation: C('Boolean', { def: true }),
    leagues: DA({
      league: C('String', { enum: LEAGUES }),
      num: C('Number', { def: 20 }),
      mode: C('String', { enum: RANKING_MODE, def: SUM_OF_BEST_N_GAMES }),
      disclose: C('Boolean', { def: false }),
      rule: C('String')
    }),
    documents: NE({
      enable: C('Boolean', { def: false }),
      deadline: C('Number', { def: 0 }),
      leagues: { t: 'Mixto', def: function () { return []; } }
    }),
    consentForm: C('String', { def: '' }),
    __v: C('Number', { def: 0 })
  };
  // models/competition.js:271-279 y 375-383
  var ESQ_RONDA = { _id: C('ObjectId', { auto: true }), competition: C('ObjectId', { required: true }), name: C('String', { required: true }), __v: C('Number', { def: 0 }) };
  var ESQ_CANCHA = { _id: C('ObjectId', { auto: true }), competition: C('ObjectId', { required: true }), name: C('String', { required: true }), __v: C('Number', { def: 0 }) };
  // models/competition.js:320-354 (email/members/document no se guardan) + fotos locales (desvío)
  var ESQ_EQUIPO = {
    _id: C('ObjectId', { auto: true }),
    competition: C('ObjectId', { required: true }),
    name: C('String', { required: true }),
    league: C('String', { enum: LEAGUES, required: true }),
    inspected: C('Boolean', { def: false }),
    docPublic: C('Boolean', { def: false }),
    country: C('String', { def: '' }),
    checkin: C('Boolean', { def: false }),
    teamCode: C('String', { def: '' }),
    __v: C('Number', { def: 0 }),
    teamPhoto: C('String'),
    robotPhoto: C('String')
  };
  // Tipo "Mixto": se copia tal cual
  CAST.Mixto = function (v) { return clonarProfundo(v); };

  R.esquemasCMS = { lineRun: ESQ_RUN, lineMap: ESQ_MAPA, competition: ESQ_COMPETENCIA, round: ESQ_RONDA, field: ESQ_CANCHA, team: ESQ_EQUIPO };
  R._mongoose = { castObjeto: castObjeto, validarObjeto: validarObjeto, mensajeValidacion: mensajeValidacion, CAST: CAST };

  // ======================================================================================
  // Decimal (decimal.js ^10.6: precisión 20, ROUND_HALF_UP) para `score * (adjustment+100)/100`
  // ======================================================================================
  function parsearDecimal(str) {
    var m = /^(-?)(\d*)(?:\.(\d*))?(?:e([+-]?\d+))?$/i.exec(String(str).trim());
    if (!m) throw new Error('[DecimalError] Invalid argument: ' + str);
    var ent = m[2] || '', frac = m[3] || '';
    var dig = (ent + frac).replace(/^0+/, '') || '0';
    return { neg: m[1] === '-', d: BigInt(dig), e: parseInt(m[4] || '0', 10) - frac.length };
  }
  function DecimalLocal(valor) {
    if (valor instanceof DecimalLocal) { this.neg = valor.neg; this.d = valor.d; this.e = valor.e; return; }
    var p = parsearDecimal(typeof valor === 'number' ? valor.toString() : valor);
    this.neg = p.neg; this.d = p.d; this.e = p.e;
    this._normalizar();
  }
  DecimalLocal.prototype._normalizar = function () {
    var s = this.d.toString();
    if (s.length > 20) {
      var sobran = s.length - 20;
      var div = BigInt(10) ** BigInt(sobran);
      var q = this.d / div, r = this.d % div;
      if (r * BigInt(2) >= div) q += BigInt(1);
      this.d = q;
      this.e += sobran;
    }
    if (this.d === BigInt(0)) { this.e = 0; this.neg = false; return this; }
    while (this.d % BigInt(10) === BigInt(0)) { this.d /= BigInt(10); this.e += 1; }
    return this;
  };
  DecimalLocal.prototype.times = function (otro) {
    var b = new DecimalLocal(otro);
    var r = Object.create(DecimalLocal.prototype);
    r.d = this.d * b.d;
    r.e = this.e + b.e;
    r.neg = this.neg !== b.neg;
    return r._normalizar();
  };
  DecimalLocal.prototype.toString = function () {
    if (this.d === BigInt(0)) return '0';
    var s = this.d.toString();
    var exp = s.length - 1 + this.e;
    var out;
    if (exp <= -7 || exp >= 21) {
      out = s[0] + (s.length > 1 ? '.' + s.slice(1) : '') + 'e' + (exp < 0 ? '' : '+') + exp;
    } else if (this.e >= 0) {
      out = s + '0'.repeat(this.e);
    } else {
      var pos = s.length + this.e;
      out = pos > 0 ? s.slice(0, pos) + '.' + s.slice(pos) : '0.' + '0'.repeat(-pos) + s;
    }
    return (this.neg ? '-' : '') + out;
  };
  DecimalLocal.prototype.valueOf = DecimalLocal.prototype.toString;
  DecimalLocal.prototype.toJSON = DecimalLocal.prototype.toString;
  DecimalLocal.prototype.toNumber = function () { return Number(this.toString()); };
  R._Decimal = DecimalLocal;

  // ======================================================================================
  // Poblado de referencias
  // ======================================================================================
  function sanearEquipo(team) {
    if (!team) return team;
    var c = clonarProfundo(team);
    delete c.teamPhoto;
    delete c.robotPhoto;
    return c;
  }
  // .select('a b c') de mongoose: _id + campos pedidos, en el orden del documento guardado
  function seleccionar(doc, campos) {
    if (doc == null) return null;
    var out = {};
    Object.keys(doc).forEach(function (k) {
      if (k === '_id' || campos.indexOf(k) >= 0) out[k] = clonarProfundo(doc[k]);
    });
    return out;
  }
  function excluir(doc, campos) {
    if (doc == null) return null;
    var out = {};
    Object.keys(doc).forEach(function (k) {
      if (campos.indexOf(k) < 0) out[k] = clonarProfundo(doc[k]);
    });
    return out;
  }

  // tileTypes indexados por _id a partir de los tilesets (poblados, orden del JSON vivo)
  async function mapaTiposBaldosa(t) {
    var sets = await t.list('tileSets');
    var m = new Map();
    sets.forEach(function (s) {
      (s.tiles || []).forEach(function (e) {
        var tt = e.tileType;
        if (tt && typeof tt === 'object' && tt._id && !m.has(tt._id)) m.set(tt._id, tt);
      });
    });
    return m;
  }

  // lineMap.findById(id).populate('tiles.tileType', '-__v').lean()
  async function cargarMapaPoblado(t, id) {
    var mid = idConsulta(id);
    if (!mid) return null;
    var m = await t.get('lineMaps', mid);
    if (!m) return null;
    var tipos = await mapaTiposBaldosa(t);
    (m.tiles || []).forEach(function (tile) {
      var tt = tipos.get(tile.tileType);
      tile.tileType = tt ? excluir(tt, ['__v']) : null;
    });
    return m;
  }

  // ======================================================================================
  // Mapas: guardado con hooks (models/lineMap.js:133-182)
  // ======================================================================================
  async function guardarMapa(t, doc, errores, opc) {
    // 1) validación del esquema (mongoose la corre antes de los pre('save') del usuario)
    validarObjeto(ESQ_MAPA, doc, '', '', errores);
    if (errores.length) throw new Error(mensajeValidacion('LineMap', errores));

    // 2) pre-save: populate('tiles.tileType') + pathFinder.findPath (errores solo logueados)
    var tipos = await mapaTiposBaldosa(t);
    var ids = doc.tiles.map(function (tile) { return tile.tileType; });
    doc.tiles.forEach(function (tile) {
      var tt = tipos.get(tile.tileType);
      tile.tileType = tt ? clonarProfundo(tt) : null;
    });
    try {
      R.PFs.findPath(doc);
      // Desvío declarado (cambios/aviso-recorrido.md): si el recorrido oficial dejó baldosas de línea sin
      // numerar y el flag está activo, se recalcula uniendo los empalmes mal dibujados.
      if (R.PFtolerante && !(R.flags && R.flags.recorridoTolerante === false)) {
        var EVAC_IDS = ['58cfd6549792e9313b1610e1', '58cfd6549792e9313b1610e2', '58cfd6549792e9313b1610e3'];
        var quedanSinNumero = doc.tiles.some(function (tile) {
          return tile.tileType && tile.tileType.paths && EVAC_IDS.indexOf(tile.tileType._id) < 0 &&
            (!tile.index || !tile.index.length);
        });
        if (quedanSinNumero) {
          var uniones = R.PFtolerante.findPath(doc);
          if (uniones.length) console.info('[RCJLocal.api] recorrido tolerante: empalmes unidos', uniones);
        }
      }
    } catch (e) {
      console.error('[RCJLocal.api] pathFinder (servidor) lanzó una excepción; el mapa se guarda igual, como en models/lineMap.js:142-146:', e);
    }
    doc.tiles.forEach(function (tile, i) { tile.tileType = ids[i]; });
    // reordenar claves según el esquema (findPath agrega indexCount al final del objeto)
    var ordenado = castObjeto(ESQ_MAPA, doc, '', [], undefined, false);

    // 3) nombre único por competencia, o corrida empezada
    if (opc.esNuevo || opc.nombreModificado) {
      var iguales = await t.list('lineMaps', function (m) {
        return m.competition === ordenado.competition && m.name === ordenado.name && m._id !== ordenado._id;
      });
      if (iguales.length) {
        var comp = await t.get('competitions', iguales[0].competition);
        throw new Error('Map "' + iguales[0].name + '" already exists in competition "' + (comp ? comp.name : undefined) + '"!');
      }
    } else {
      var empezadas = await t.list('lineRuns', function (r) { return r.map === ordenado._id && r.started === true; });
      if (empezadas.length) throw new Error('Map "' + ordenado.name + '" used in started runs, cannot modify!');
    }
    await t.put('lineMaps', ordenado);
    return ordenado;
  }

  // ======================================================================================
  // Caché síncrona de tileCount (para el $.ajax async:false del editor, L26:480-485)
  // ======================================================================================
  var cacheBaldosas = { lista: false, mapas: new Map(), tileSets: {} };

  function resumenMapa(m) {
    return { _id: m._id, tileSet: m.tileSet, tipos: (m.tiles || []).map(function (x) { return x.tileType; }) };
  }
  function resumenTileSet(s) {
    return (s.tiles || []).map(function (e) { return (e.tileType && typeof e.tileType === 'object') ? e.tileType._id : e.tileType; });
  }
  async function precargar() {
    await R.store.tx(['lineMaps', 'tileSets'], async function (t) {
      var mapas = await t.list('lineMaps');
      var sets = await t.list('tileSets');
      var nm = new Map();
      mapas.forEach(function (m) { nm.set(m._id, resumenMapa(m)); });
      var ns = {};
      sets.forEach(function (s) { ns[s._id] = resumenTileSet(s); });
      cacheBaldosas.mapas = nm;
      cacheBaldosas.tileSets = ns;
    }, 'readonly');
    cacheBaldosas.lista = true;
  }
  function avisarCambioCache() {
    try { if (R.bus) R.bus.postMessage({ tipo: 'cache', origen: R.instanciaId }); } catch (e) { /* bus cerrado */ }
  }
  var escuchandoBus = false;
  function escucharBus() {
    if (escuchandoBus || !R.bus || !R.bus.addEventListener) return;
    escuchandoBus = true;
    R.bus.addEventListener('message', function (ev) {
      var m = ev.data;
      if (m && m.tipo === 'cache' && m.origen !== R.instanciaId) {
        precargar().catch(function (e) { console.warn('[RCJLocal.api] no se pudo refrescar la caché', e); });
      }
    });
  }

  // lineMaps.js:476-507 (y :443-474 con tileId) sobre la caché
  function contarBaldosas(expectMapId, tileSetId, tileId) {
    var excluirId = esIdValido(expectMapId) ? idConsulta(expectMapId) : null; // null -> ObjectId(null) aleatorio: no excluye
    var setId = idConsulta(tileSetId);
    var contar = function (tipo) {
      var n = 0;
      cacheBaldosas.mapas.forEach(function (m) {
        if (excluirId && m._id === excluirId) return;
        if (m.tileSet !== setId) return;
        m.tipos.forEach(function (tt) { if (tt === tipo) n++; });
      });
      return n;
    };
    if (tileId !== undefined) {
      return { tileSetId: tileSetId, tileId: tileId, expectMapId: excluirId ? expectMapId : null, usedCount: contar(idConsulta(tileId)) };
    }
    var set = cacheBaldosas.tileSets[setId];
    if (!set) return null;
    return set.map(function (tipo) { return { tileId: tipo, usedCount: contar(tipo) }; });
  }

  // ======================================================================================
  // Sockets (E16): publica en BroadcastChannel y entrega en la misma ventana
  // ======================================================================================
  R.emitirSocket = function (sala, evento, datos) {
    var msg = { tipo: 'io', room: String(sala), event: evento, origen: R.instanciaId, id: nuevoId() };
    if (datos !== undefined) msg.payload = clonarJSON(datos);
    try { if (R.bus) R.bus.postMessage(msg); } catch (e) { console.warn('[RCJLocal.api] no se pudo publicar en el bus', e); }
    if (typeof R._ioLocal === 'function') {
      try { R._ioLocal(msg); } catch (e2) { console.error(e2); }
    }
  };

  // ======================================================================================
  // Rutas
  // ======================================================================================
  var RUTAS = [];
  function def(metodo, patron, handler, opciones) {
    opciones = opciones || {};
    var nombres = [];
    var cuerpo = patron.replace(/\/$/, '').replace(/[.*+?^${}()|[\]\\]/g, function (c) { return c === ':' ? c : '\\' + c; })
      .replace(/:([A-Za-z0-9_]+)/g, function (_, n) { nombres.push(n); return '([^/]+)'; });
    RUTAS.push({
      metodo: metodo,
      patron: patron,
      re: new RegExp('^' + cuerpo + '\\/?$', 'i'),
      nombres: nombres,
      handler: handler,
      modo: opciones.modo || (metodo === 'GET' ? 'readonly' : 'readwrite'),
      si: opciones.si
    });
  }
  function idOk(nombre) { return function (p) { return esIdValido(p[nombre]); }; }

  // ------------------------------------------------------------------ /api/maps/line (routes/api/lineMaps.js)
  var MAPS = '/api/maps/line';

  // E8 (salidas): si el área salidas no registró su generador, se responde error y la UI muestra su Toast
  function salidaNoDisponible(ctx) {
    if (ctx.metodo === 'POST' && (!ctx.body || !ctx.body.tiles) && /map-image/.test(ctx.path)) {
      return json(400, { msg: 'Invalid map data' }); // lineMaps.js:654-658
    }
    return json(501, { msg: 'Salida no disponible en la versión offline: el generador no está registrado', message: 'Not implemented' });
  }
  def('GET', MAPS + '/image/:mapid', salidaNoDisponible);
  def('POST', MAPS + '/map-image-pdf', salidaNoDisponible);
  def('POST', MAPS + '/map-image-png', salidaNoDisponible);
  def('POST', MAPS + '/scoresheet', salidaNoDisponible);

  // E4 — lineMaps.js:150-174
  def('GET', MAPS + '/:map', async function (ctx) {
    var id = idConsulta(ctx.params.map);
    var data;
    if (ctx.query.populate !== undefined && ctx.query.populate) {
      data = await cargarMapaPoblado(ctx.t, id);
    } else {
      data = await ctx.t.get('lineMaps', id);
    }
    return enviar(200, data);
  }, { si: idOk('map') });

  // tiletypes — lineMaps.js:370-414
  async function tiposSinPaths(t, ids) {
    var tipos = await mapaTiposBaldosa(t);
    var arr = Array.from(tipos.values());
    if (ids !== undefined) arr = arr.filter(function (tt) { return ids.indexOf(tt._id) >= 0; });
    return arr.map(function (tt) { return excluir(tt, ['paths', '__v']); });
  }
  def('GET', MAPS + '/tiletypes', async function (ctx) {
    var q = ctx.query.id;
    if (typeof q === 'string') {
      var uno = await tiposSinPaths(ctx.t, [idConsulta(q)]);
      return enviar(200, uno[0] || null);
    }
    if (Array.isArray(q)) return json(200, await tiposSinPaths(ctx.t, q.filter(esIdValido).map(idConsulta)));
    return json(200, await tiposSinPaths(ctx.t));
  });
  def('GET', MAPS + '/tiletypes/:tiletype', async function (ctx) {
    var uno = await tiposSinPaths(ctx.t, [idConsulta(ctx.params.tiletype)]);
    return enviar(200, uno[0] || null);
  }, { si: idOk('tiletype') });

  // E1 — lineMaps.js:416-441 (tilesets sembrados con el JSON vivo, sin reordenar)
  def('GET', MAPS + '/tilesets', async function (ctx) {
    var sets = await ctx.t.list('tileSets');
    sets.sort(ordenPorSemilla);
    if (ctx.query.populate !== undefined && ctx.query.populate) return json(200, sets);
    return json(200, sets.map(function (s) {
      var c = clonarProfundo(s);
      c.tiles = (c.tiles || []).map(function (e) {
        var o = {};
        Object.keys(e).forEach(function (k) { o[k] = (k === 'tileType' && e[k] && typeof e[k] === 'object') ? e[k]._id : e[k]; });
        return o;
      });
      return c;
    }));
  });
  def('GET', MAPS + '/tilesets/:tileset', async function (ctx) {
    var s = await ctx.t.get('tileSets', idConsulta(ctx.params.tileset));
    if (!s) return enviar(200, null);
    var out = { _id: s._id, name: s.name, tiles: (s.tiles || []).map(function (e) {
      var o = {};
      Object.keys(e).forEach(function (k) {
        o[k] = (k === 'tileType' && e[k] && typeof e[k] === 'object') ? excluir(e[k], ['paths', '__v']) : clonarProfundo(e[k]);
      });
      return o;
    }) };
    return json(200, out);
  }, { si: idOk('tileset') });

  // private GET '/' — lineMaps.js:31-62 (también /api/competitions/:competition/:league/maps)
  async function listarMapas(t, competition, league) {
    var mapas = await t.list('lineMaps');
    mapas.sort(ordenNatural);
    if (competition != null && typeof competition === 'string') {
      var cid = idConsulta(competition);
      mapas = mapas.filter(function (m) { return m.competition === cid; });
    } else if (Array.isArray(competition)) {
      var ids = competition.filter(esIdValido).map(idConsulta);
      mapas = mapas.filter(function (m) { return ids.indexOf(m.competition) >= 0; });
    }
    var data = mapas.map(function (m) { return seleccionar(m, ['competition', 'name', 'league']); });
    if (league) data = data.filter(function (m) { return m.league == league; });
    return data;
  }
  def('GET', MAPS + '/', async function (ctx) {
    return json(200, await listarMapas(ctx.t, ctx.query.competition, undefined));
  });
  def('GET', MAPS + '/name/:competitionid/:name', async function (ctx) {
    var cid = idConsulta(ctx.params.competitionid);
    var mapas = await ctx.t.list('lineMaps', function (m) { return m.competition === cid && m.name === ctx.params.name; });
    return json(200, mapas.map(function (m) { return { _id: m._id }; }));
  });

  // E5 — lineMaps.js:65-148
  function undefied2false(data) { return !!data; } // lineMaps.js:813-816
  def('POST', MAPS + '/', async function (ctx) {
    var map = ctx.body;
    if (typeof map != 'object') return texto(400, 'Bad request');
    var obj;
    try {
      var tiles = [];
      for (var i in map.tiles) {
        if (map.tiles.hasOwnProperty(i)) {
          var tile = map.tiles[i];
          if (isNaN(i)) {
            var coords = i.split(',');
            tile.x = coords[0];
            tile.y = coords[1];
            tile.z = coords[2];
          }
          var tileTypeId = typeof tile.tileType === 'object' ? tile.tileType._id : tile.tileType;
          tiles.push({
            x: tile.x, y: tile.y, z: tile.z, tileType: tileTypeId, rot: tile.rot,
            items: { obstacles: tile.items.obstacles, speedbumps: tile.items.speedbumps, rampPoints: undefied2false(tile.items.rampPoints) },
            levelUp: tile.levelUp, levelDown: tile.levelDown, checkPoint: undefied2false(tile.checkPoint)
          });
        }
      }
      obj = {
        competition: map.competition, tileSet: map.tileSet, name: map.name, height: map.height, width: map.width,
        length: map.length, tiles: tiles,
        startTile: { x: map.startTile.x, y: map.startTile.y, z: map.startTile.z },
        startTile2: { x: map.startTile2.x, y: map.startTile2.y, z: map.startTile2.z },
        finished: map.finished, victims: map.victims, league: map.league
      };
    } catch (e) {
      if (e instanceof TypeError) return noEncontrado(); // excepción síncrona en Express -> 404 JSON (app.js:287)
      throw e;
    }
    var errores = [];
    var doc = castObjeto(ESQ_MAPA, obj, '', errores, undefined, false);
    try {
      doc = await guardarMapa(ctx.t, doc, errores, { esNuevo: true });
    } catch (e) {
      return json(400, { msg: 'Error saving map', err: e.message });
    }
    ctx.despues.push(function () { cacheBaldosas.mapas.set(doc._id, resumenMapa(doc)); avisarCambioCache(); });
    return json(201, { msg: 'New map has been saved', id: doc._id }, { Location: '/api/maps/line/' + doc._id });
  });

  // E7 — lineMaps.js:176-212
  def('GET', MAPS + '/:map/maxScore', async function (ctx) {
    var id = idConsulta(ctx.params.map);
    var data = await ctx.t.get('lineMaps', id);
    if (!data) return json(400, { msg: 'Could not get map', err: 'Map not found' }); // original: TypeError sin respuesta
    var comp = await ctx.t.get('competitions', data.competition);
    var compSel = comp ? { _id: comp._id, leagues: clonarProfundo(comp.leagues) } : null;
    var liga = compSel ? compSel.leagues.find(function (l) { return l.league == data.league; }) : undefined;
    if (!liga) return errorInterno(new Error('La competencia del mapa no tiene la liga ' + data.league)); // original: TypeError sin respuesta
    var rule = liga.rule;
    var mapa = await cargarMapaPoblado(ctx.t, id);
    var run = await R.initLine({
      competition: compSel,
      team: { league: data.league },
      map: id,
      isNL: data.league == 'LineNL',
      nl: {},
      exitBonus: true
    }, mapa, rule, true);
    return enviar(200, R.calculateScore(run));
  }, { si: idOk('map') });

  // E6 — lineMaps.js:241-328
  var copyPropertiesMapas = function (obj, dbObj) { return R.copyProperties(obj, dbObj); };
  def('PUT', MAPS + '/:map', async function (ctx) {
    var id = idConsulta(ctx.params.map);
    var map = ctx.body;
    delete map._id;
    delete map.__v;
    delete map.competition;
    delete map.indexCount;

    var guardado = await ctx.t.get('lineMaps', id);
    if (!guardado) return json(400, { msg: 'Could not get map', err: 'Map not found' }); // original: TypeError sin respuesta
    var previo = clonarProfundo(guardado);
    var dbMap = clonarProfundo(guardado);

    var tiles = [];
    for (var i in map.tiles) {
      if (map.tiles.hasOwnProperty(i)) {
        var tile = map.tiles[i];
        if (isNaN(i)) {
          var coords = i.split(',');
          tile.x = coords[0];
          tile.y = coords[1];
          tile.z = coords[2];
        }
        tiles.push(tile);
      }
    }
    map.tiles = tiles;

    dbMap.tiles = [];
    var err = copyPropertiesMapas(map, dbMap);
    if (err) return json(400, { err: err.message, msg: 'Could not save map' });

    var errores = [];
    var doc = castObjeto(ESQ_MAPA, dbMap, '', errores, previo, false);

    var empezada = await ctx.t.list('lineRuns', function (r) { return r.map === id && r.started === true; });
    if (empezada.length) {
      return json(400, { msg: 'Run already started on map!', err: 'Run ' + empezada[0]._id + ' already started on map' });
    }
    try {
      doc = await guardarMapa(ctx.t, doc, errores, { esNuevo: false, nombreModificado: doc.name !== previo.name });
    } catch (e) {
      return json(400, { msg: 'Could not save map', err: e.message });
    }
    ctx.despues.push(function () { cacheBaldosas.mapas.set(doc._id, resumenMapa(doc)); avisarCambioCache(); });
    return json(200, { msg: 'Saved!' });
  }, { si: idOk('map') });

  // DELETE — lineMaps.js:333-368 (+ models/lineMap.js:126-131 borra sus corridas)
  def('DELETE', MAPS + '/:map', async function (ctx) {
    var id = idConsulta(ctx.params.map);
    var empezada = await ctx.t.list('lineRuns', function (r) { return r.map === id && r.started === true; });
    if (empezada.length) return json(400, { msg: 'Could not remove map', err: "Can't remove map with started run connected!" });
    var corridas = await ctx.t.list('lineRuns', function (r) { return r.map === id; });
    for (var i = 0; i < corridas.length; i++) await ctx.t.del('lineRuns', corridas[i]._id);
    await ctx.t.del('lineMaps', id);
    ctx.despues.push(function () { cacheBaldosas.mapas.delete(id); avisarCambioCache(); });
    return json(200, { msg: 'Map has been removed!' });
  }, { si: idOk('map') });

  // E9 — lineMaps.js:443-507
  def('GET', MAPS + '/tileCount/:expectMapId/:tileSetId/:tileId', async function (ctx) {
    return json(200, contarBaldosas(ctx.params.expectMapId, ctx.params.tileSetId, ctx.params.tileId));
  }, { si: function (p) { return esIdValido(p.tileSetId) && esIdValido(p.tileId); } });
  def('GET', MAPS + '/tileCount/:expectMapId/:tileSetId', async function (ctx) {
    var r = contarBaldosas(ctx.params.expectMapId, ctx.params.tileSetId);
    if (!r) return json(400, { msg: 'Could not get tile set', err: 'Tile set not found' }); // original: TypeError sin respuesta
    return json(200, r);
  }, { si: idOk('tileSetId') });

  def('GET', MAPS + '/export', salidaNoDisponible);

  // ------------------------------------------------------------------ /api/runs/line (routes/api/lineRuns.js)
  var RUNS = '/api/runs/line';

  // Poblado de la lista (lineRuns.js:81-102)
  async function poblarLista(t, runs) {
    var cache = {};
    async function traer(col, id) {
      if (id == null) return undefined;
      var k = col + ':' + id;
      if (!(k in cache)) cache[k] = await t.get(col, id);
      return cache[k];
    }
    for (var i = 0; i < runs.length; i++) {
      var r = runs[i];
      if ('competition' in r) { var c = await traer('competitions', r.competition); r.competition = c ? seleccionar(c, ['name', 'leagues', 'preparation']) : null; }
      if ('round' in r) { var ro = await traer('rounds', r.round); r.round = ro ? seleccionar(ro, ['name']) : null; }
      if ('team' in r) { var te = await traer('teams', r.team); r.team = te ? seleccionar(te, ['name', 'league', 'teamCode']) : null; }
      if ('field' in r) { var fi = await traer('fields', r.field); r.field = fi ? seleccionar(fi, ['name', 'league']) : null; }
      if ('map' in r) { var ma = await traer('lineMaps', r.map); r.map = ma ? seleccionar(ma, ['name']) : null; }
    }
    return runs;
  }

  // E12 — lineRuns.js:51-159
  def('GET', RUNS + '/competition/:competitionId', async function (ctx) {
    var competition = idConsulta(ctx.params.competitionId);
    var normalized = ctx.query.normalized;
    var minimum = ctx.query.minimum;
    var maxScoreCache = {};
    var todas = await ctx.t.list('lineRuns', function (r) {
      if (r.competition !== competition) return false;
      if (ctx.query.ended == 'false') return r.status <= 1;
      return true;
    });
    todas.sort(ordenNatural);
    var campos = minimum
      ? ['competition', 'round', 'team', 'field', 'status', 'started', 'startTime', 'sign']
      : ['competition', 'round', 'team', 'field', 'map', 'score', 'raw_score', 'multiplier', 'time', 'status', 'started', 'LoPs', 'comment', 'startTime', 'sign', 'rescueOrder', 'nl', 'group', 'normalizationGroup', 'exitBonus', 'evacuationLevel', 'kitLevel', 'adjustment'];
    var dbRuns = todas.map(function (r) { return seleccionar(r, campos); });
    await poblarLista(ctx.t, dbRuns);

    dbRuns.map(function (run) {
      // authViewRun del usuario local = 1 (helper/authLevels.js:45-47): solo el case 1
      run.originalScore = run.score;
      if (run.adjustment != null) {
        run.score = new DecimalLocal(run.score).times((run.adjustment + 100) / 100);
      }
    });

    if (!minimum && normalized) { // authCompetition(ADMIN) = true para el usuario local
      dbRuns.map(function (run) {
        var rankingSettings = run.competition.leagues.find(function (r) { return r.league == run.team.league; });
        if (NORMALIZED_RANKING_MODE.includes(rankingSettings.mode)) {
          var maxScore = getMaxScoreWithCache(dbRuns, run.team.league, run.normalizationGroup, maxScoreCache);
          if (maxScore == 0) run.normalizedScore = 0;
          else run.normalizedScore = run.score / maxScore;
        }
      });
    }
    return json(200, dbRuns);
  }, { si: idOk('competitionId') });

  // lineRuns.js:161-168 (verbatim)
  function getMaxScoreWithCache(runs, league, normalizationGroup, cache) {
    if (cache[league + normalizationGroup] != null) {
      return cache[league + normalizationGroup];
    }
    cache[league + normalizationGroup] = Math.max(...runs.filter(run => run.team.league == league && run.normalizationGroup == normalizationGroup)
      .map(run => run.score));
    return cache[league + normalizationGroup];
  }

  // lineRuns.js:225-257 (signage; barato de mantener)
  def('GET', RUNS + '/find/:competitionid/:field/:status', async function (ctx) {
    var cid = idConsulta(ctx.params.competitionid), fid = idConsulta(ctx.params.field);
    var estado = Number(ctx.params.status);
    var runs = await ctx.t.list('lineRuns', function (r) { return r.competition === cid && r.field === fid && r.status === estado; });
    runs.sort(function (a, b) { return (a.startTime || 0) - (b.startTime || 0); });
    var data = runs.map(function (r) { return seleccionar(r, ['field', 'team', 'competition', 'status', 'startTime']); });
    for (var i = 0; i < data.length; i++) {
      if (data[i].team) { var te = await ctx.t.get('teams', data[i].team); data[i].team = te ? seleccionar(te, ['name', 'league', 'teamCode']) : null; }
    }
    return json(200, data);
  }, { si: function (p) { return esIdValido(p.competitionid) && esIdValido(p.field); } });

  // Carga una corrida con los poblados de E10 (lineRuns.js:306-311)
  async function poblarCorridaGet(t, dbRun) {
    var round = dbRun.round != null ? await t.get('rounds', dbRun.round) : undefined;
    var team = dbRun.team != null ? await t.get('teams', dbRun.team) : undefined;
    var field = dbRun.field != null ? await t.get('fields', dbRun.field) : undefined;
    var comp = dbRun.competition != null ? await t.get('competitions', dbRun.competition) : undefined;
    return {
      round: round === undefined ? undefined : (round || null),
      team: team === undefined ? undefined : (team ? seleccionar(team, ['name', 'league', 'teamCode']) : null),
      field: field === undefined ? undefined : (field || null),
      competition: comp === undefined ? undefined : (comp ? seleccionar(comp, ['name', 'leagues', 'preparation']) : null)
    };
  }

  // E10 — lineRuns.js:298-384
  def('GET', RUNS + '/:runid', async function (ctx) {
    var id = idConsulta(ctx.params.runid);
    var normalized = ctx.query.normalized;
    var guardada = await ctx.t.get('lineRuns', id);
    if (!guardada) return noEncontrado(); // original: sin respuesta (documentado)

    var dbRun = clonarProfundo(guardada);
    delete dbRun.__v; // findById(id, '-__v')
    var pob = await poblarCorridaGet(ctx.t, dbRun);
    if (!pob.competition || !pob.team) {
      return errorInterno(new Error('La corrida no tiene competencia o equipo válidos')); // original: TypeError sin respuesta
    }
    var liga = pob.competition.leagues.find(function (r) { return r.league == pob.team.league; });
    if (!liga) return errorInterno(new Error('La competencia no tiene la liga del equipo')); // original: TypeError sin respuesta
    var rule = liga.rule;
    // authViewRun = 1 (usuario local superDuperAdmin)

    // Init run data (lineRuns.js:330-345): initLine muta el mismo documento
    var runInit = clonarProfundo(dbRun);
    runInit.round = pob.round; runInit.team = pob.team; runInit.field = pob.field; runInit.competition = pob.competition;
    var mapa = await cargarMapaPoblado(ctx.t, dbRun.map);
    var initDbRun = await R.initLine(runInit, mapa, rule);
    var respuesta = dbRun;
    if (initDbRun != null) {
      var mezclado = clonarProfundo(dbRun);
      mezclado.tiles = initDbRun.tiles;
      mezclado.LoPs = initDbRun.LoPs;
      mezclado.nl = initDbRun.nl;
      mezclado.rescueOrder = initDbRun.rescueOrder; // IRD:119 lo pone en [] sobre el MISMO documento (C1)
      mezclado.__v = guardada.__v;
      var errores = [];
      var casteada = castObjeto(ESQ_RUN, mezclado, '', errores, guardada, false);
      // save(): validación + pre-save (map.finished). El original arma la respuesta antes de que el
      // guardado termine (lineRuns.js:336-347), así que la respuesta sale igual aunque falle.
      validarObjeto(ESQ_RUN, casteada, '', '', errores);
      var mapaSel = await ctx.t.get('lineMaps', dbRun.map);
      if (!errores.length && mapaSel && mapaSel.finished) {
        var persistir = clonarProfundo(casteada);
        persistir.updatedAt = ahoraISO();
        persistir.__v = (guardada.__v || 0) + 1; // $set de arrays incrementa la versión
        await ctx.t.put('lineRuns', persistir);
      } else {
        console.warn('[RCJLocal.api] GET corrida: la re-inicialización no se guardó (como en el CMS):',
          errores.length ? mensajeValidacion('LineRun', errores) : (mapaSel ? 'Map "' + mapaSel.name + '" is not finished!' : 'map null'));
      }
      respuesta = casteada;
      delete respuesta.__v;
    }
    respuesta.round = pob.round;
    respuesta.team = pob.team;
    respuesta.field = pob.field;
    respuesta.competition = pob.competition;

    var rankingSettings = pob.competition.leagues.find(function (r) { return r.league == pob.team.league; });
    if (!rankingSettings) rankingSettings = { mode: SUM_OF_BEST_N_GAMES, disclose: false, num: 20 };
    if (normalized && NORMALIZED_RANKING_MODE.includes(rankingSettings.mode)) {
      // disclose || ADMIN: el usuario local es admin
      var grupo = await ctx.t.list('lineRuns', function (r) {
        return r.competition === pob.competition._id && r.normalizationGroup == respuesta.normalizationGroup;
      });
      var puntajes = [];
      for (var i = 0; i < grupo.length; i++) {
        var tg = grupo[i].team != null ? await ctx.t.get('teams', grupo[i].team) : null;
        if (tg && tg.league == pob.team.league) puntajes.push(grupo[i]._id === respuesta._id ? respuesta.score : grupo[i].score);
      }
      var maxScore = Math.max.apply(null, puntajes);
      if (maxScore == 0) respuesta.normalizedScore = 0;
      else respuesta.normalizedScore = respuesta.score / maxScore;
    }
    return json(200, respuesta);
  }, { si: idOk('runid'), modo: 'readwrite' });

  // E11 — lineRuns.js:475-661 (pipeline de 08 §5.5 en UNA transacción)
  def('PUT', RUNS + '/:runid', async function (ctx) {
    var id = idConsulta(ctx.params.runid);
    var statusUpdate = false;
    var run = ctx.body;

    // 1) lineRuns.js:485-492
    delete run._id;
    delete run.__v;
    delete run.map;
    delete run.competition;
    delete run.round;
    delete run.team;
    delete run.field;
    delete run.score;

    var guardada = await ctx.t.get('lineRuns', id);
    if (!guardada) return noEncontrado(); // original: sin respuesta
    var previo = clonarProfundo(guardada);
    var dbRun = clonarProfundo(guardada);
    // populate map (tiles.tileType con select 'indexCount, victims' -> solo _id), competition, team
    var mapaDoc = await ctx.t.get('lineMaps', dbRun.map);
    var compDoc = await ctx.t.get('competitions', dbRun.competition);
    var teamDoc = dbRun.team != null ? await ctx.t.get('teams', dbRun.team) : null;
    if (!compDoc) return errorInterno(new Error('La corrida no tiene competencia')); // original: TypeError sin respuesta
    // authCompetition(JUDGE): usuario local

    var erroresCast = [];
    try {
      // 2) lineRuns.js:526-535 — diccionario como array disperso
      if (run.tiles != null && run.tiles.constructor === Object) {
        var tilesDic = run.tiles;
        run.tiles = [];
        Object.keys(tilesDic).forEach(function (key) {
          if (!isNaN(key)) {
            run.tiles[key] = tilesDic[key];
          }
        });
      }
      // 3) lineRuns.js:537-539
      if (run.LoPs != null && run.LoPs.length != dbRun.LoPs.length) {
        dbRun.LoPs.length = run.LoPs.length;
      }
      // 4) lineRuns.js:541-553 — reemplazo completo (mongoose castea al asignar)
      if (run.rescueOrder != null) {
        var ro = castCampo(ESQ_RUN.rescueOrder, run.rescueOrder, 'rescueOrder', erroresCast, previo.rescueOrder);
        if (ro !== RESTAURAR) dbRun.rescueOrder = ro;
      }
      if (run.nl != null) {
        if (run.nl.liveVictim != null) {
          var lv = castCampo(ESQ_RUN.nl.campos.liveVictim, run.nl.liveVictim, 'nl.liveVictim', erroresCast, previo.nl && previo.nl.liveVictim);
          if (lv !== RESTAURAR) dbRun.nl.liveVictim = lv;
        }
        if (run.nl.deadVictim != null) {
          var dv = castCampo(ESQ_RUN.nl.campos.deadVictim, run.nl.deadVictim, 'nl.deadVictim', erroresCast, previo.nl && previo.nl.deadVictim);
          if (dv !== RESTAURAR) dbRun.nl.deadVictim = dv;
        }
      }
    } catch (e) {
      if (e instanceof TypeError || e instanceof RangeError) return errorInterno(e); // original: excepción asíncrona sin respuesta
      throw e;
    }

    // 5) lineRuns.js:555-557 — status no decreciente, salvo desde 6; 0 (falsy) pasa siempre
    if (run.status) {
      if (dbRun.status > run.status && dbRun.status != 6) delete run.status;
    }
    var prevStatus = dbRun.status;

    // 6) lineRuns.js:562-596 — copyProperties verbatim
    var err = R.copyProperties(run, dbRun);
    if (err) {
      return json(400, { err: err.message, msg: 'Could not save run' });
    }
    // casteo de mongoose (en el original ocurre en cada asignación; ver cambios/backend.md)
    var casteada = castObjeto(ESQ_RUN, dbRun, '', erroresCast, previo, false);

    if (prevStatus != casteada.status) statusUpdate = 1;

    // 7) lineRuns.js:600-606
    var runCalc = Object.assign({}, casteada, {
      map: mapaDoc ? Object.assign({}, mapaDoc, { tiles: (mapaDoc.tiles || []).map(function (x) { return Object.assign({}, x, { tileType: { _id: x.tileType } }); }) }) : null,
      competition: compDoc,
      team: teamDoc
    });
    var cal;
    try {
      cal = R.calculateScore(runCalc);
    } catch (e) {
      return errorInterno(e); // original: excepción síncrona dentro del callback -> sin respuesta
    }
    if (!cal) {
      return json(202, { msg: 'Try again later' });
    }

    // 8) lineRuns.js:608-610 (con casteo Number: NaN no se asigna y queda como error)
    ['score', 'raw_score', 'multiplier'].forEach(function (k) {
      var v = castCampo(ESQ_RUN[k], cal[k], k, erroresCast, previo[k]);
      if (v !== RESTAURAR) casteada[k] = v;
    });

    // 9) lineRuns.js:612-627
    if (!casteada.started) {
      if (casteada.score > 0) {
        casteada.started = true;
      } else {
        if (run.tiles) {
          scoredCheck: for (var ti = 0; ti < run.tiles.length; ti++) {
            var tile = run.tiles[ti];
            if (!tile || !Array.isArray(tile.scoredItems)) continue; // huecos del diccionario: el original tira TypeError (quirk 10)
            for (var ii = 0; ii < tile.scoredItems.length; ii++) {
              var item = tile.scoredItems[ii];
              if (item && item.scored) {
                casteada.started = true;
                break scoredCheck;
              }
            }
          }
        }
      }
    }

    // 10) save(): validación de esquema y pre-save (models/lineRun.js:92-100)
    var errores = erroresCast.slice();
    validarObjeto(ESQ_RUN, casteada, '', '', errores);
    if (errores.length) {
      return json(400, { err: mensajeValidacion('LineRun', errores), msg: 'Could not save run' });
    }
    if (!mapaDoc) return errorInterno(new Error('La corrida no tiene mapa')); // original: TypeError sin respuesta
    if (!mapaDoc.finished) {
      return json(400, { err: 'Map "' + mapaDoc.name + '" is not finished!', msg: 'Could not save run' });
    }
    casteada.updatedAt = ahoraISO(); // mongoose-timestamp
    if (run.tiles != null || run.LoPs != null || run.rescueOrder != null) {
      casteada.__v = (guardada.__v || 0) + 1; // $set de un array incrementa __v
    }
    await ctx.t.put('lineRuns', casteada);

    // 11) lineRuns.js:637-657 — emisiones después de confirmar la transacción
    var cid = compDoc._id;
    var payload = Object.assign({}, casteada, {
      competition: clonarProfundo(compDoc),
      team: teamDoc ? sanearEquipo(teamDoc) : teamDoc,
      map: { _id: mapaDoc._id, name: mapaDoc.name, finished: mapaDoc.finished } // pre-save repuebla map con 'name finished'
    });
    ctx.despues.push(function () {
      R.emitirSocket('runs/line', 'changed');
      R.emitirSocket('runs/line/' + cid, 'changed');
      R.emitirSocket('runs/' + casteada._id, 'data', payload);
      R.emitirSocket('fields/' + casteada.field, 'data', { newRun: casteada._id });
      if (statusUpdate) R.emitirSocket('runs/line/' + cid + '/status', 'LChanged');
    });
    return json(200, { msg: 'Saved run', score: casteada.score, raw_score: casteada.raw_score, multiplier: casteada.multiplier });
  }, { si: idOk('runid') });

  // admin PUT /bulk — lineRuns.js:386-441
  def('PUT', RUNS + '/bulk', async function (ctx) {
    var updates = Array.isArray(ctx.body) ? ctx.body : [];
    var totalCount = updates.length, success = 0;
    for (var i = 0; i < updates.length; i++) {
      var u = updates[i] || {};
      var guardada = await ctx.t.get('lineRuns', idConsulta(u._id));
      if (!guardada) continue; // original: nunca responde si falta alguna
      var doc = clonarProfundo(guardada);
      doc.adjustment = u.adjustment;
      var errores = [];
      var casteada = castObjeto(ESQ_RUN, doc, '', errores, guardada, false);
      validarObjeto(ESQ_RUN, casteada, '', '', errores);
      var mapa = await ctx.t.get('lineMaps', casteada.map);
      if (errores.length || !mapa || !mapa.finished) continue;
      casteada.updatedAt = ahoraISO();
      await ctx.t.put('lineRuns', casteada);
      success++;
    }
    if (totalCount == success) return json(200, { msg: 'All success: ' + totalCount });
    return json(200, { msg: 'Partial success: ' + success + '/' + totalCount });
  });

  def('GET', RUNS + '/scoresheet2', salidaNoDisponible);

  // admin DELETE /:runids — lineRuns.js:771-815
  def('DELETE', RUNS + '/:runids', async function (ctx) {
    var ids = ctx.params.runids.split(',');
    var primera = await ctx.t.get('lineRuns', idConsulta(ids[0]));
    if (!primera) return noEncontrado(); // original: TypeError sin respuesta
    var invalidos = ids.filter(function (x) { return !esIdValido(x); });
    if (invalidos.length) {
      return json(400, { msg: 'Could not remove run', err: 'Cast to ObjectId failed for value "' + invalidos[0] + '" (type string) at path "_id" for model "LineRun"' });
    }
    var lista = ids.map(idConsulta);
    var borrar = await ctx.t.list('lineRuns', function (r) { return lista.indexOf(r._id) >= 0 && r.competition === primera.competition; });
    for (var i = 0; i < borrar.length; i++) await ctx.t.del('lineRuns', borrar[i]._id);
    return json(200, { msg: 'Run has been removed!' });
  }, { si: function (p) { return esIdValido(p.runids.split(',')[0]); } });

  // E13 admin POST / — lineRuns.js:835-861 + pre-save models/lineRun.js:92-280
  def('POST', RUNS + '/', async function (ctx) {
    var run = ctx.body || {};
    var errores = [];
    var doc = castObjeto(ESQ_RUN, {
      competition: run.competition, round: run.round, team: run.team, field: run.field, map: run.map,
      startTime: run.startTime, group: run.group, normalizationGroup: run.normalizationGroup
    }, '', errores, undefined, false);
    validarObjeto(ESQ_RUN, doc, '', '', errores);
    var falla = function (mensaje) { return json(400, { msg: 'Error saving run in db', err: mensaje }); };
    if (errores.length) return falla(mensajeValidacion('LineRun', errores));

    var mapa = await ctx.t.get('lineMaps', doc.map);
    if (!mapa) return falla('No map with that id!'); // original: TypeError en el populate (sin respuesta)
    if (!mapa.finished) return falla('Map "' + mapa.name + '" is not finished!');

    var comp = await ctx.t.get('competitions', doc.competition);
    var round = await ctx.t.get('rounds', doc.round);
    var field = await ctx.t.get('fields', doc.field);
    var team = null;
    if (doc.team) {
      var dup = await ctx.t.list('lineRuns', function (r) { return r.round === doc.round && r.team === doc.team; });
      if (dup.length) {
        var dt = await ctx.t.get('teams', dup[0].team);
        var dr = await ctx.t.get('rounds', dup[0].round);
        return falla('Team "' + (dt ? dt.name : undefined) + '" already has a run in round "' + (dr ? dr.name : undefined) + '"!');
      }
      team = await ctx.t.get('teams', doc.team);
    }
    if (!comp) return falla('No competition with that id!');
    if (!round) return falla('No round with that id!');
    if (doc.team && !team) return falla('No team with that id!');
    if (!field) return falla('No field with that id!');
    var competitionId = comp._id;
    if (round.competition != competitionId) return falla('Round does not match competition!');
    if (doc.team) {
      if (team.competition != competitionId) return falla('Team does not match competition!');
      if (LINE_LEAGUES.indexOf(team.league) == -1) return falla('Team does not match league!');
    }
    if (field.competition != competitionId) return falla('Field does not match competition!');
    if (mapa.competition != competitionId) return falla('Map does not match competition!');
    if (doc.team) doc.isNL = team.league == 'LineNL';

    var ahora = ahoraISO();
    doc.createdAt = ahora;
    doc.updatedAt = ahora;
    await ctx.t.put('lineRuns', doc);
    return json(201, { err: 'New run has been saved', id: doc._id }, { Location: '/api/runs/' + doc._id });
  });

  // ------------------------------------------------------------------ /api/competitions (routes/api/competitions.js)
  var COMPS = '/api/competitions';
  function defaultsCompetencia(data, logo) {
    if (!data.color) data.color = '000000';
    if (!data.bkColor) data.bkColor = 'ffffff';
    if (!data.message) data.message = '';
    if (!data.description) data.description = '';
    if (!data.logo) data.logo = logo;
    if (data.documents) delete data.documents.leagues;
    return data;
  }
  // A1 — competitions.js:27-54
  def('GET', COMPS + '/', async function (ctx) {
    var data = await ctx.t.list('competitions');
    data.sort(ordenNatural);
    data.forEach(function (c) {
      c.authLevel = ACCESSLEVEL_SUPERADMIN; // competitionLevel(usuario local superDuperAdmin)
      defaultsCompetencia(c, '/images/NoImage.png');
    });
    return json(200, data);
  });
  def('GET', COMPS + '/leagues', async function () { return json(200, R.LEAGUES_JSON); });
  // A3 — competitions.js:60-82
  def('GET', COMPS + '/leagues/:league', async function (ctx) {
    var league = ctx.params.league;
    if (LEAGUES.filter(function (elm) { return elm.indexOf(league) != -1; }).length == 0) return noEncontrado();
    var lj = (R.LEAGUES_JSON || []).find(function (l) { return l.id == league; });
    if (!lj) return errorInterno(new Error('Liga parcial sin coincidencia exacta')); // original: nunca responde
    return json(200, { id: lj.id, type: lj.type, name: lj.name });
  });
  // A2 — competitions.js:84-115
  def('GET', COMPS + '/:competition', async function (ctx) {
    var data = await ctx.t.get('competitions', idConsulta(ctx.params.competition));
    if (!data) return json(400, { msg: 'Could not get competition' });
    defaultsCompetencia(data, '/images/noLogo.png');
    for (var i = 0; i < data.leagues.length; i++) {
      var l = data.leagues[i];
      var det = (R.LEAGUES_JSON || []).find(function (j) { return j.id == l.league; });
      if (!det) return errorInterno(new Error('Liga desconocida ' + l.league));
      l.name = det.name;
      l.type = det.type;
    }
    return json(200, data);
  }, { si: idOk('competition') });
  def('GET', COMPS + '/:competition/teams/:teamid', async function (ctx) {
    var cid = idConsulta(ctx.params.competition), tid = idConsulta(ctx.params.teamid);
    var team = await ctx.t.get('teams', tid);
    return enviar(200, team && team.competition === cid ? sanearEquipo(team) : null);
  }, { si: function (p) { return esIdValido(p.competition) && esIdValido(p.teamid); } });
  def('GET', COMPS + '/:competition/fields', async function (ctx) {
    var cid = idConsulta(ctx.params.competition);
    var data = await ctx.t.list('fields', function (f) { return f.competition === cid; });
    return json(200, data.sort(ordenNatural));
  }, { si: idOk('competition') });
  def('GET', COMPS + '/:competitionid/fields/:name', async function (ctx) {
    var cid = idConsulta(ctx.params.competitionid);
    var data = await ctx.t.list('fields', function (f) { return f.competition === cid && f.name === ctx.params.name; });
    return json(200, data.map(function (f) { return { _id: f._id }; }));
  }, { si: idOk('competitionid') });
  def('GET', COMPS + '/:competition/rounds', async function (ctx) {
    var cid = idConsulta(ctx.params.competition);
    var data = await ctx.t.list('rounds', function (r) { return r.competition === cid; });
    return json(200, data.sort(ordenNatural));
  }, { si: idOk('competition') });
  def('GET', COMPS + '/:competitionid/rounds/:name', async function (ctx) {
    var cid = idConsulta(ctx.params.competitionid);
    var data = await ctx.t.list('rounds', function (r) { return r.competition === cid && r.name === ctx.params.name; });
    return json(200, data.map(function (r) { return { _id: r._id }; }));
  }, { si: idOk('competitionid') });
  // private — competitions.js:489-515
  def('GET', COMPS + '/:competition/teams', async function (ctx) {
    var cid = idConsulta(ctx.params.competition);
    var data = await ctx.t.list('teams', function (x) { return x.competition === cid; });
    return json(200, data.sort(ordenNatural).map(function (x) {
      return seleccionar(x, ['name', 'competition', 'league', 'inspected', 'country', 'checkin', 'teamCode']);
    }));
  }, { si: idOk('competition') });
  // private — competitions.js:547-592
  def('GET', COMPS + '/:competition/:league/teams', async function (ctx) {
    var league = ctx.params.league;
    var leagueArr = [];
    if (league == 'line') leagueArr = LINE_LEAGUES;
    else if (league == 'maze') leagueArr = ['Maze', 'MazeNL'];
    else if (league == 'simulation') leagueArr = ['Erebus'];
    else if (LEAGUES.filter(function (elm) { return elm.indexOf(league) != -1; }).length == 0) return noEncontrado();
    else leagueArr.push(league);
    var cid = idConsulta(ctx.params.competition);
    var data = await ctx.t.list('teams', function (x) { return x.competition === cid && leagueArr.indexOf(x.league) >= 0; });
    return json(200, data.sort(ordenNatural).map(function (x) {
      return seleccionar(x, ['name', 'competition', 'league', 'inspected', 'country', 'checkin', 'teamCode']);
    }));
  }, { si: idOk('competition') });
  // private — competitions.js:612-637
  def('GET', COMPS + '/:competition/:league/maps', async function (ctx) {
    var league = ctx.params.league;
    if (LINE_LEAGUES.filter(function (elm) { return elm.indexOf(league) != -1; }).length == 0) return noEncontrado();
    return json(200, await listarMapas(ctx.t, ctx.params.competition, league));
  }, { si: idOk('competition') });
  // admin PUT — competitions.js:204-286
  def('PUT', COMPS + '/:competitionid', async function (ctx) {
    var id = idConsulta(ctx.params.competitionid);
    var data = ctx.body || {};
    var guardada = await ctx.t.get('competitions', id);
    if (!guardada) return noEncontrado(); // original: sin respuesta
    var doc = clonarProfundo(guardada);
    ['name', 'logo', 'bkColor', 'color', 'message', 'description', 'preparation', 'leagues'].forEach(function (k) {
      if (data[k] != null) doc[k] = data[k];
    });
    if (data.documents != null) {
      if (data.documents.enable != null) doc.documents.enable = data.documents.enable;
      if (data.documents.deadline != null) doc.documents.deadline = data.documents.deadline;
    }
    var errores = [];
    var casteada = castObjeto(ESQ_COMPETENCIA, doc, '', errores, guardada, false);
    validarObjeto(ESQ_COMPETENCIA, casteada, '', '', errores);
    if (errores.length) return json(400, { err: mensajeValidacion('Competition', errores), msg: 'Could not save changes' });
    var dup = await ctx.t.list('competitions', function (c) { return c._id !== id && c.name === casteada.name && casteada.name != null; });
    if (dup.length) return json(400, { err: 'E11000 duplicate key error collection: competitions index: name_1 dup key: { name: "' + casteada.name + '" }', msg: 'Could not save changes' });
    await ctx.t.put('competitions', casteada);
    return json(200, { msg: 'Settings has been saved' });
  }, { si: idOk('competitionid') });
  def('GET', COMPS + '/:competition/adminTeams', async function (ctx) {
    var cid = idConsulta(ctx.params.competition);
    var data = await ctx.t.list('teams', function (x) { return x.competition === cid; });
    return json(200, data.sort(ordenNatural).map(function (x) {
      return seleccionar(x, ['name', 'competition', 'league', 'country', 'teamCode']);
    }));
  }, { si: idOk('competition') });
  // admin POST — competitions.js:745-818 (ligas: solo Line/2026 por ESPEC §5; ver cambios/backend.md)
  def('POST', COMPS + '/', async function (ctx) {
    var competition = ctx.body || {};
    var errores = [];
    var doc = castObjeto(ESQ_COMPETENCIA, {
      name: competition.name,
      leagues: [{ league: 'Line', rule: '2026' }]
    }, '', errores, undefined, false);
    validarObjeto(ESQ_COMPETENCIA, doc, '', '', errores);
    if (errores.length) return json(400, { msg: 'Error saving competition', err: mensajeValidacion('Competition', errores) });
    var dup = await ctx.t.list('competitions', function (c) { return c.name === doc.name && doc.name != null; });
    if (dup.length) return json(400, { msg: 'Error saving competition', err: 'E11000 duplicate key error collection: competitions index: name_1 dup key: { name: "' + doc.name + '" }' });
    await ctx.t.put('competitions', doc);
    return json(201, { msg: 'New competition has been saved', id: doc._id });
  });
  // admin DELETE — competitions.js:820-874 (+ cascada de models/competition.js:204-218)
  def('DELETE', COMPS + '/:competitionid', async function (ctx) {
    var id = idConsulta(ctx.params.competitionid);
    var borrados = [];
    var cols = ['rounds', 'teams', 'fields', 'lineMaps', 'lineRuns'];
    for (var c = 0; c < cols.length; c++) {
      var docs = await ctx.t.list(cols[c], function (d) { return d.competition === id; });
      for (var i = 0; i < docs.length; i++) {
        await ctx.t.del(cols[c], docs[i]._id);
        if (cols[c] === 'lineMaps') borrados.push(docs[i]._id);
      }
    }
    await ctx.t.del('competitions', id);
    ctx.despues.push(function () { borrados.forEach(function (m) { cacheBaldosas.mapas.delete(m); }); avisarCambioCache(); });
    return json(200, { msg: 'Competition has been removed!' });
  }, { si: idOk('competitionid') });

  // ------------------------------------------------------------------ /api/rounds y /api/fields
  function crudSimple(base, col, esquema, modelo, textos) {
    def('GET', base + '/', async function (ctx) {
      return json(200, (await ctx.t.list(col)).sort(ordenNatural));
    });
    def('GET', base + '/:id', async function (ctx) {
      return enviar(200, await ctx.t.get(col, idConsulta(ctx.params.id)));
    }, { si: idOk('id') });
    def('DELETE', base + '/:id', async function (ctx) {
      await ctx.t.del(col, idConsulta(ctx.params.id));
      return json(200, { msg: textos.borrado });
    }, { si: idOk('id') });
    def('POST', base + '/', async function (ctx) {
      var b = ctx.body || {};
      var errores = [];
      var doc = castObjeto(esquema, { name: b.name, competition: b.competition }, '', errores, undefined, false);
      validarObjeto(esquema, doc, '', '', errores);
      if (errores.length) return json(400, { msg: textos.error, err: mensajeValidacion(modelo, errores) });
      // pre-save: nombre único por competencia (models/competition.js:281-301 y 385-405)
      var dup = await ctx.t.list(col, function (d) { return d.competition === doc.competition && d.name === doc.name; });
      if (dup.length) return json(400, { msg: textos.error, err: textos.existe(doc.name) });
      await ctx.t.put(col, doc);
      return json(201, { msg: textos.creado, id: doc._id }, { Location: base + '/' + doc._id });
    });
  }
  crudSimple('/api/rounds', 'rounds', ESQ_RONDA, 'Round', {
    borrado: 'Round has been removed!', error: 'Error saving round', creado: 'New round has been saved',
    existe: function (n) { return 'Round with name "' + n + '" already exists!'; }
  });
  crudSimple('/api/fields', 'fields', ESQ_CANCHA, 'Field', {
    borrado: 'Field has been removed!', error: 'Error saving field', creado: 'New field has been saved',
    existe: function (n) { return 'Field with name "' + n + '" already exists!'; }
  });

  // ------------------------------------------------------------------ /api/teams (routes/api/teams.js)
  def('GET', '/api/teams/leagues', async function () { return json(200, R.LEAGUES_JSON); });
  def('GET', '/api/teams/:teamid', async function (ctx) {
    var team = await ctx.t.get('teams', idConsulta(ctx.params.teamid));
    return enviar(200, team ? seleccionar(team, ['inspected', 'name', 'teamCode', 'league', 'competition', 'checkin', 'country']) : null);
  }, { si: idOk('teamid') });
  // private PUT — teams.js:155-213 (+ fotos locales teamPhoto/robotPhoto, desvío documentado)
  def('PUT', '/api/teams/:competitionid/:teamid', async function (ctx) {
    var cid = idConsulta(ctx.params.competitionid), tid = idConsulta(ctx.params.teamid);
    var team = ctx.body || {};
    var guardado = await ctx.t.get('teams', tid);
    if (!guardado || guardado.competition !== cid) return noEncontrado(); // original: sin respuesta
    var doc = clonarProfundo(guardado);
    if (team.inspected != null) doc.inspected = team.inspected;
    if (team.docPublic != null) doc.docPublic = team.docPublic;
    if (team.checkin != null) doc.checkin = team.checkin;
    if (team.code != null) doc.teamCode = team.code;
    if (team.name != null) doc.name = team.name;
    if (team.teamCode != null) doc.teamCode = team.teamCode;
    if (team.league != null) doc.league = team.league;
    if (team.country != null) doc.country = team.country;
    ['teamPhoto', 'robotPhoto'].forEach(function (k) {
      if (team[k] === '') delete doc[k];
      else if (team[k] != null) doc[k] = team[k];
    });
    var errores = [];
    var casteado = castObjeto(ESQ_EQUIPO, doc, '', errores, guardado, false);
    validarObjeto(ESQ_EQUIPO, casteado, '', '', errores);
    if (errores.length) return json(400, { err: mensajeValidacion('Team', errores), msg: 'Could not save changes' });
    await ctx.t.put('teams', casteado);
    return json(200, { msg: 'Saved changes' });
  }, { si: idOk('teamid') });
  // admin DELETE — teams.js:239-299 (+ cascada de corridas, models/competition.js:365-372)
  def('DELETE', '/api/teams/:teamid', async function (ctx) {
    var ids = ctx.params.teamid.split(',');
    var primero = await ctx.t.get('teams', idConsulta(ids[0]));
    if (!primero) return noEncontrado(); // original: TypeError sin respuesta
    var lista = ids.map(idConsulta);
    var equipos = await ctx.t.list('teams', function (x) { return lista.indexOf(x._id) >= 0 && x.competition === primero.competition; });
    for (var i = 0; i < equipos.length; i++) {
      await ctx.t.del('teams', equipos[i]._id);
    }
    var corridas = await ctx.t.list('lineRuns', function (r) { return lista.indexOf(r.team) >= 0; });
    for (var j = 0; j < corridas.length; j++) await ctx.t.del('lineRuns', corridas[j]._id);
    return json(200, { msg: 'Team has been removed!' });
  }, { si: function (p) { return esIdValido(p.teamid.split(',')[0]); } });
  // admin POST — teams.js:301-364
  def('POST', '/api/teams/', async function (ctx) {
    var team = ctx.body || {};
    var comp = team.competition != null ? await ctx.t.get('competitions', idConsulta(team.competition)) : null;
    if (!comp) return json(400, { msg: 'Error saving team', err: 'No competition with that id!' }); // original: sin respuesta
    var errores = [];
    var doc = castObjeto(ESQ_EQUIPO, {
      name: team.name, league: team.league, competition: team.competition, teamCode: team.teamCode, country: team.country
    }, '', errores, undefined, false);
    validarObjeto(ESQ_EQUIPO, doc, '', '', errores);
    if (errores.length) return json(400, { msg: 'Error saving team', err: mensajeValidacion('Team', errores) });
    await ctx.t.put('teams', doc);
    return json(201, { msg: 'New team has been saved', id: doc._id });
  });

  // ------------------------------------------------------------------ /api/ranking (routes/api/ranking.js)
  def('GET', '/api/ranking/:competitionId/:leagueId', async function (ctx) {
    if (!R.ranking || typeof R.ranking.calcular !== 'function') {
      return errorInterno(new Error('Falta cargar local/nucleo/ranking.js'));
    }
    return R.ranking.calcular(ctx.t, ctx.params.competitionId, ctx.params.leagueId, ctx.query, { json: json, noEncontrado: noEncontrado });
  }, { si: function (p) { return esIdValido(p.competitionId) && LINE_LEAGUES.includes(p.leagueId); } });

  // ------------------------------------------------------------------ E14 fotos del pre-chequeo
  function dataURLaBlob(dataURL) {
    var m = /^data:([^;,]*)((?:;[^;,]*)*),([\s\S]*)$/.exec(dataURL);
    if (!m) return null;
    var mime = m[1] || 'application/octet-stream';
    var esB64 = /;base64/i.test(m[2]);
    var bytes;
    if (esB64) {
      var bin = atob(m[3]);
      bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    } else {
      bytes = new TextEncoder().encode(decodeURIComponent(m[3]));
    }
    return { blob: new Blob([bytes], { type: mime }), mime: mime };
  }
  // document.js:1511-1569: el CMS sirve images/NoImage.png (200) si no hay archivo (:1556-1569); acá 404 (ESPEC E14)
  def('GET', '/api/document/inspection/files/:teamId/:fileName', async function (ctx) {
    var team = await ctx.t.get('teams', idConsulta(ctx.params.teamId));
    if (!team) return json(400, { msg: 'Could not get team', err: 'No team found' });
    var nombre = ctx.params.fileName;
    var dataURL = (nombre === 'teamPhoto' || nombre === 'robotPhoto') ? team[nombre] : null;
    var b = (typeof dataURL === 'string' && dataURL.indexOf('data:') === 0) ? dataURLaBlob(dataURL) : null;
    if (!b) return { status: 404, data: '', headers: {} };
    return { status: 200, data: b.blob, headers: { 'Content-Type': b.mime } };
  }, { si: idOk('teamId') });

  // ======================================================================================
  // Motor de pedidos
  // ======================================================================================
  var registradas = [];

  function parsearCuerpo(cuerpo) {
    if (cuerpo === undefined || cuerpo === null || cuerpo === '') return {};
    if (typeof cuerpo === 'string') {
      try {
        var v = JSON.parse(cuerpo);
        return (v !== null && typeof v === 'object') ? v : {};
      } catch (e) {
        return {};
      }
    }
    if (typeof Blob !== 'undefined' && cuerpo instanceof Blob) return {};
    if (typeof FormData !== 'undefined' && cuerpo instanceof FormData) return {};
    if (cuerpo instanceof ArrayBuffer) return {};
    return clonarProfundo(cuerpo);
  }

  function parsearQuery(u) {
    var q = {};
    u.searchParams.forEach(function (v, k) {
      if (tieneProp(q, k)) q[k] = [].concat(q[k], v);
      else q[k] = v;
    });
    return q;
  }

  function normalizar(r) {
    var status = r.status || 200;
    var headers = r.headers || {};
    var data = r.data;
    var esBinario = (typeof Blob !== 'undefined' && data instanceof Blob) || data instanceof ArrayBuffer || ArrayBuffer.isView(data);
    if (data === undefined || data === null) data = '';
    else if (!esBinario && typeof data !== 'string') data = clonarJSON(data); // serialización de Express (toJSON)
    return { status: status, data: data, headers: headers, statusText: r.statusText || TEXTOS_ESTADO[status] || '' };
  }

  function decodificar(x) {
    try { return decodeURIComponent(x); } catch (e) { return x; }
  }

  // ------------------------------------------------------------------ inicialización
  var promesaListo = null;

  async function leerTilesetsArchivo() {
    try {
      var resp = await fetch((R.base || '/') + 'data/tilesets.json', { cache: 'no-cache' });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      var datos = await resp.json();
      var valido = Array.isArray(datos) && datos.length > 0 && datos.every(function (s) { return s && s._id && Array.isArray(s.tiles); });
      if (!valido) throw new Error('data/tilesets.json no tiene el formato esperado (¿HTML de error?)');
      return datos;
    } catch (e) {
      console.warn('[RCJLocal.api] no se pudieron leer los tilesets de data/tilesets.json:', e);
      return null;
    }
  }

  async function sembrarTilesets(tilesets) {
    await R.store.tx(['tileSets', 'meta'], async function (t) {
      for (var i = 0; i < tilesets.length; i++) await t.put('tileSets', clonarProfundo(tilesets[i]));
      await t.put('meta', { _id: 'ordenTilesets', ids: tilesets.map(function (s) { return s._id; }) });
    });
  }

  var ordenSemilla = null;
  function ordenPorSemilla(a, b) {
    if (!ordenSemilla) return a._id < b._id ? -1 : (a._id > b._id ? 1 : 0);
    var ia = ordenSemilla.indexOf(a._id), ib = ordenSemilla.indexOf(b._id);
    if (ia < 0) ia = 1e9;
    if (ib < 0) ib = 1e9;
    return ia - ib || (a._id < b._id ? -1 : (a._id > b._id ? 1 : 0));
  }

  function asegurarListo() {
    if (!promesaListo) {
      promesaListo = (async function () {
        await R.store.abrir();
        escucharBus();
        if ((await R.store.count('tileSets')) === 0) {
          var sets = await leerTilesetsArchivo();
          if (sets) await sembrarTilesets(sets);
        }
        var meta = await R.store.get('meta', 'ordenTilesets');
        ordenSemilla = meta ? meta.ids : null;
        await precargar();
      })().catch(function (e) {
        promesaListo = null;
        throw e;
      });
    }
    return promesaListo;
  }

  /**
   * RCJLocal.api.request(method, url, body, opts) -> Promise<{status, data, headers, statusText}>
   * url: '/api/...' (con query). body: objeto o string JSON. opts.responseType: solo lo usa
   * http-backend.js para codificar; acá `data` es objeto/string/Blob/ArrayBuffer.
   */
  async function request(metodo, url, cuerpo, opts) {
    opts = opts || {};
    await asegurarListo();
    metodo = String(metodo || 'GET').toUpperCase();
    var u = new URL(url, window.location.origin);
    var path = u.pathname;
    var query = parsearQuery(u);

    for (var i = 0; i < registradas.length; i++) {
      var rr = registradas[i];
      if (rr.metodo !== '*' && rr.metodo !== metodo) continue;
      var m = rr.re.exec(path);
      if (!m) continue;
      var r = await rr.handler({
        method: metodo, url: url, path: path, query: query, body: parsearCuerpo(cuerpo), match: m, opts: opts, store: R.store, api: R.api
      });
      if (r != null) return normalizar(r);
    }

    for (var j = 0; j < RUTAS.length; j++) {
      var ruta = RUTAS[j];
      if (ruta.metodo !== metodo) continue;
      var m2 = ruta.re.exec(path);
      if (!m2) continue;
      var params = {};
      for (var k = 0; k < ruta.nombres.length; k++) params[ruta.nombres[k]] = decodificar(m2[k + 1]);
      if (ruta.si && !ruta.si(params, query)) continue; // next()
      var despues = [];
      var ctx = { params: params, query: query, body: parsearCuerpo(cuerpo), path: path, metodo: metodo, despues: despues, opts: opts };
      var respuesta;
      try {
        respuesta = await R.store.tx(COLS, function (t) {
          ctx.t = t;
          return ruta.handler(ctx);
        }, ruta.modo);
      } catch (e) {
        despues.length = 0;
        if (e && e.respuestaHttp) respuesta = e.respuestaHttp;
        else {
          console.error('[RCJLocal.api]', metodo, path, e);
          respuesta = errorInterno(e);
        }
      }
      for (var d = 0; d < despues.length; d++) {
        try { despues[d](); } catch (e2) { console.error('[RCJLocal.api] tarea posterior', e2); }
      }
      return normalizar(respuesta);
    }
    return normalizar(noEncontrado());
  }

  /** Versión síncrona: SOLO tileCount (E9), servida desde la caché en memoria. */
  function requestSync(metodo, url) {
    metodo = String(metodo || 'GET').toUpperCase();
    var u = new URL(url, window.location.origin);
    var partes = u.pathname.replace(/\/$/, '').split('/');
    // ['', 'api', 'maps', 'line', 'tileCount', expect, set, (tile)]
    if (metodo === 'GET' && partes.length >= 7 && partes.length <= 8 && partes[1] === 'api' && partes[2] === 'maps' &&
        partes[3] === 'line' && partes[4].toLowerCase() === 'tilecount') {
      if (!cacheBaldosas.lista) {
        console.warn('[RCJLocal.api] tileCount síncrono antes de terminar la precarga: se cuenta con lo disponible');
      }
      var expect = decodificar(partes[5]), set = decodificar(partes[6]);
      if (partes.length === 8) {
        var tile = decodificar(partes[7]);
        if (!esIdValido(set) || !esIdValido(tile)) return normalizar(noEncontrado());
        return normalizar(json(200, contarBaldosas(expect, set, tile)));
      }
      if (!esIdValido(set)) return normalizar(noEncontrado());
      var r = contarBaldosas(expect, set);
      if (!r) return normalizar(json(400, { msg: 'Could not get tile set', err: 'Tile set not found' }));
      return normalizar(json(200, r));
    }
    return normalizar(json(500, { msg: 'Llamada síncrona no soportada por el backend local: ' + metodo + ' ' + u.pathname }));
  }

  /**
   * Registra un manejador que tiene prioridad sobre las rutas internas (p.ej. E8 del área salidas).
   * handler(ctx) -> {status, data, headers} | null (null/undefined = seguir con las rutas internas).
   * ctx = {method, url, path, query, body, match, opts, store, api}.
   */
  function registrarRuta(metodo, regex, handler) {
    var re = regex instanceof RegExp ? regex : new RegExp(regex);
    registradas.push({ metodo: String(metodo || '*').toUpperCase(), re: re, handler: handler });
  }

  // Fotos del pre-chequeo (dataURL en el equipo, desvío local)
  async function fotoEquipo(teamId, nombre) {
    var team = await R.store.get('teams', idConsulta(teamId));
    return team && typeof team[nombre] === 'string' ? team[nombre] : null;
  }
  async function guardarFotoEquipo(teamId, nombre, dataURL) {
    if (nombre !== 'teamPhoto' && nombre !== 'robotPhoto') throw new Error('Nombre de foto inválido: ' + nombre);
    var team = await R.store.get('teams', idConsulta(teamId));
    if (!team) throw new Error('No existe el equipo ' + teamId);
    var body = {};
    body[nombre] = dataURL || '';
    var r = await request('PUT', '/api/teams/' + team.competition + '/' + team._id, body);
    if (r.status !== 200) throw new Error((r.data && (r.data.err || r.data.msg)) || ('HTTP ' + r.status));
    return true;
  }

  R.api = {
    request: request,
    requestSync: requestSync,
    registrarRuta: registrarRuta,
    precargar: function () { return asegurarListo().then(precargar); },
    listo: asegurarListo,
    fotoEquipo: fotoEquipo,
    guardarFotoEquipo: guardarFotoEquipo,
    rutas: RUTAS
  };

  // ======================================================================================
  // Ingesta y export de mapas (08 §5.2-5.3)
  // ======================================================================================
  /**
   * RCJLocal.ingestMap(exportJson, {competition, league:'Line', nombre?, renombrarSiExiste?}) -> Promise<mapId>
   * Equivale a POST + PUT del CMS: tiles objeto->array con x,y,z de la clave, lista blanca por
   * baldosa (MAPS:88-102), defaults del esquema, `duration` del export, pre-save con PFs.
   * Tolerante (D1): `tiles` como array y `tileType` como id.
   */
  R.ingestMap = async function (exportJson, opciones) {
    opciones = opciones || {};
    await asegurarListo();
    var data = typeof exportJson === 'string' ? JSON.parse(exportJson) : clonarProfundo(exportJson);
    if (!data || typeof data !== 'object') throw new Error('El JSON del mapa no es un objeto');
    var league = opciones.league || 'Line';
    var mapId = null;
    await R.store.tx(COLS, async function (t) {
      var competitionId = idConsulta(opciones.competition);
      var comp = competitionId ? await t.get('competitions', competitionId) : null;
      if (!comp) throw new Error('No existe la competencia ' + opciones.competition);

      var fuente = data.tiles || {};
      var esArray = Array.isArray(fuente);
      var tiles = [];
      Object.keys(fuente).forEach(function (i) {
        var tile = fuente[i];
        if (!tile || typeof tile !== 'object') return;
        var x = tile.x, y = tile.y, z = tile.z;
        if (!esArray && isNaN(i)) {
          var c = i.split(',');
          x = c[0]; y = c[1]; z = c[2];
        }
        if (!tile.items) throw new Error('La baldosa ' + i + ' no tiene "items"');
        tiles.push({
          x: x, y: y, z: z,
          tileType: (tile.tileType && typeof tile.tileType === 'object') ? tile.tileType._id : tile.tileType,
          rot: tile.rot,
          items: { obstacles: tile.items.obstacles, speedbumps: tile.items.speedbumps, rampPoints: !!tile.items.rampPoints },
          levelUp: tile.levelUp,
          levelDown: tile.levelDown,
          checkPoint: !!tile.checkPoint
        });
      });

      var nombre = opciones.nombre || data.name;
      if (opciones.renombrarSiExiste) {
        var existentes = (await t.list('lineMaps', function (m) { return m.competition === comp._id; })).map(function (m) { return m.name; });
        var base = nombre, n = 2;
        while (existentes.indexOf(nombre) >= 0) { nombre = base + ' (' + n + ')'; n++; }
      }
      var st = data.startTile || {}, st2 = data.startTile2 || {};
      var obj = {
        competition: comp._id, league: league, tileSet: data.tileSet, name: nombre,
        height: data.height, width: data.width, length: data.length, duration: data.duration,
        tiles: tiles,
        startTile: { x: st.x, y: st.y, z: st.z },
        startTile2: { x: st2.x, y: st2.y, z: st2.z },
        finished: data.finished,
        victims: data.victims
      };
      var errores = [];
      var doc = castObjeto(ESQ_MAPA, obj, '', errores, undefined, false);
      doc = await guardarMapa(t, doc, errores, { esNuevo: true });
      mapId = doc._id;
      cacheBaldosas.mapas.set(doc._id, resumenMapa(doc));
    });
    avisarCambioCache();
    return mapId;
  };

  /**
   * RCJLocal.exportMap(mapId) -> Promise<objeto con la forma y el orden del export del editor>
   * Reproduce la carga del editor (L26:134-170) y $scope.export (L26:993-1019). Si el pathFinder
   * cliente (global `pathFinder`) está cargado, recalcula index/next como updateTileIndex (L26:435-461).
   */
  R.exportMap = async function (mapId) {
    var r = await request('GET', '/api/maps/line/' + mapId + '?populate=true');
    var d = r.data;
    if (r.status !== 200 || !d || typeof d !== 'object') throw new Error('No existe el mapa ' + mapId);
    var tiles = {};
    for (var i = 0; i < d.tiles.length; i++) {
      tiles[d.tiles[i].x + ',' + d.tiles[i].y + ',' + d.tiles[i].z] = d.tiles[i];
    }
    if (typeof window.pathFinder === 'function') {
      var dic = [];
      for (var k in tiles) {
        var tile = tiles[k];
        tile.index = [];
        tile.next = [];
        var coords = k.split(',');
        tile.x = Number(coords[0]);
        tile.y = Number(coords[1]);
        tile.z = Number(coords[2]);
        dic[tile.x + ',' + tile.y + ',' + tile.z] = tile;
      }
      var result = window.pathFinder({ startTile: d.startTile, startTile2: d.startTile2, tiles: dic });
      for (var j in result.tiles) tiles[j] = result.tiles[j];
    }
    var map = {
      tileSet: d.tileSet,
      name: d.name,
      length: d.length,
      height: d.height,
      width: d.width,
      duration: d.duration || 480,
      finished: d.finished,
      startTile: d.startTile,
      startTile2: d.startTile2,
      tiles: tiles,
      victims: { live: d.victims.live, dead: d.victims.dead }
    };
    return JSON.parse(JSON.stringify(map));
  };

  // ======================================================================================
  // Semillas (ESPEC D10) y respaldo
  // ======================================================================================
  /**
   * RCJLocal.semillas({tilesets?}) -> Promise<{tilesets, competencia, creados}>
   * Idempotente: tilesets solo si no hay ninguno; competencia/ronda/cancha/equipo solo si no hay
   * ninguna competencia.
   */
  R.semillas = async function (opciones) {
    opciones = opciones || {};
    await R.store.abrir();
    var resumen = { tilesets: 0, competencia: null, creados: false };
    if ((await R.store.count('tileSets')) === 0) {
      var sets = opciones.tilesets || await leerTilesetsArchivo();
      if (sets) {
        await sembrarTilesets(sets);
        resumen.tilesets = sets.length;
        ordenSemilla = sets.map(function (s) { return s._id; });
      }
    }
    await asegurarListo();
    if (resumen.tilesets) await precargar();
    if ((await R.store.count('competitions')) === 0) {
      var c = await request('POST', '/api/competitions', { name: 'Práctica IITA 2026' });
      if (c.status !== 201) throw new Error('No se pudo crear la competencia semilla: ' + JSON.stringify(c.data));
      var cid = c.data.id;
      var pasos = [
        ['/api/rounds', { name: 'Ronda 1', competition: cid }],
        ['/api/fields', { name: 'Cancha 1', competition: cid }],
        ['/api/teams', { name: 'IITA Salta', league: 'Line', competition: cid, teamCode: '' }]
      ];
      for (var i = 0; i < pasos.length; i++) {
        var rp = await request('POST', pasos[i][0], pasos[i][1]);
        if (rp.status !== 201) throw new Error('No se pudo crear la semilla ' + pasos[i][0] + ': ' + JSON.stringify(rp.data));
      }
      await R.store.put('meta', { _id: 'semillas', fecha: ahoraISO(), competencia: cid });
      resumen.competencia = cid;
      resumen.creados = true;
    }
    return resumen;
  };

  R.backup = {
    formato: 'rcj-line-offline/respaldo',
    exportar: async function () {
      await R.store.abrir();
      var out = { formato: 'rcj-line-offline/respaldo', version: 1, app: R.version, fecha: ahoraISO(), colecciones: {} };
      await R.store.tx(COLS, async function (t) {
        for (var i = 0; i < COLS.length; i++) out.colecciones[COLS[i]] = await t.list(COLS[i]);
      }, 'readonly');
      return out;
    },
    importar: async function (obj, opciones) {
      if (typeof obj === 'string') obj = JSON.parse(obj);
      if (!obj || obj.formato !== 'rcj-line-offline/respaldo' || !obj.colecciones || typeof obj.colecciones !== 'object') {
        throw new Error('El archivo no es un respaldo de rcj-line-offline');
      }
      var modo = (opciones && opciones.modo) || 'reemplazar';
      if (modo !== 'reemplazar' && modo !== 'fusionar') throw new Error('Modo de importación inválido: ' + modo);
      await R.store.abrir();
      var cuenta = {};
      await R.store.tx(COLS, async function (t) {
        for (var i = 0; i < COLS.length; i++) {
          var col = COLS[i];
          if (modo === 'reemplazar') await t.clear(col);
          var docs = obj.colecciones[col];
          cuenta[col] = 0;
          if (Array.isArray(docs)) {
            for (var j = 0; j < docs.length; j++) {
              if (docs[j] && docs[j]._id != null) { await t.put(col, docs[j]); cuenta[col]++; }
            }
          }
        }
      });
      var meta = await R.store.get('meta', 'ordenTilesets');
      ordenSemilla = meta ? meta.ids : null;
      await precargar();
      avisarCambioCache();
      return { modo: modo, cuenta: cuenta };
    }
  };
})();

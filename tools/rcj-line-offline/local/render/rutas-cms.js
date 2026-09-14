/*
 * rcj-line-offline — área salidas.
 * Handlers de Express del CMS (d805502) para las salidas, copiados VERBATIM:
 *   routes/api/lineMaps.js:24-29   registro en los routers (image/:mapid, map-image-pdf, map-image-png,
 *                                  scoresheet, export)
 *   routes/api/lineMaps.js:650-804 handlePublicMapImagePDF, handlePublicMapImagePNG,
 *                                  getMapsFromRequest, handleExport, getMapImage
 *   routes/api/lineMaps.js:818-822 handleScoresheet
 *   routes/api/lineRuns.js:663-745 GET /scoresheet2 (planillas de corridas con QR y hora)
 *
 * Lo que en el CMS venía de mongoose/express se emula acá (hand-written, en español):
 *   - lineMap / lineRun: consultas find/findById + sort/select/populate/lean/exec sobre RCJLocal.store.
 *   - ObjectId(x) / ObjectId.isValid (bson 4.x), auth.authCompetition (usuario local = admin), ACCESSLEVELS.
 *   - routers: capturan (método, ruta, handler); local/render/registrar.js los atiende.
 */
(function (global) {
  var R = global.RCJLocal;
  var S = R && R.salidas;
  if (!S || !S.comun) throw new Error('local/render/rutas-cms.js: falta local/render/comun.js (incluir solo local/render/registrar.js)');
  var C = S.comun;

  // ---------------------------------------------------------------- bson / auth
  function ObjectId(v) {
    if (v && typeof v === 'object' && typeof v.toHexString === 'function') return v.toHexString();
    var s = String(v);
    if (/^[0-9a-fA-F]{24}$/.test(s)) return s.toLowerCase();
    if (s.length === 12) {
      var b = new TextEncoder().encode(s);
      if (b.length === 12) return Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
    }
    throw new TypeError('Argument passed in must be a string of 12 bytes or a string of 24 hex characters or an integer');
  }
  ObjectId.isValid = function (id) { return R.esIdValido(id); };

  // models/user.js:49-55
  var ACCESSLEVELS = { SUPERADMIN: 15, ADMIN: 10, JUDGE: 5, VIEW: 1, NONE: 0 };
  // helper/authLevels.js: el usuario local es superDuperAdmin (igual criterio que local/nucleo/api.js)
  var auth = { authCompetition: function () { return true; } };

  // ---------------------------------------------------------------- consultas estilo mongoose (lean)
  var REFERENCIAS = { competition: 'competitions', round: 'rounds', team: 'teams', field: 'fields', map: 'lineMaps' };

  function clonar(x) { return x === undefined ? undefined : JSON.parse(JSON.stringify(x)); }
  function esHex24(s) { return typeof s === 'string' && /^[0-9a-fA-F]{24}$/.test(s); }
  function normId(v) { return esHex24(v) ? v.toLowerCase() : v; }

  // Comparación numérica de MongoDB: NaN es igual a NaN y menor que cualquier otro número
  function cmpNum(a, b) {
    var na = Number.isNaN(a), nb = Number.isNaN(b);
    if (na && nb) return 0;
    if (na) return -1;
    if (nb) return 1;
    return a < b ? -1 : (a > b ? 1 : 0);
  }
  function igual(valor, esperado) {
    if (esperado === undefined || esperado === null) return valor === undefined || valor === null;
    return normId(valor) === normId(esperado) || (typeof valor === 'number' && typeof esperado === 'number' && cmpNum(valor, esperado) === 0);
  }
  function coincide(doc, filtro) {
    return Object.keys(filtro || {}).every(function (k) {
      var cond = filtro[k];
      var v = doc[k];
      if (cond && typeof cond === 'object' && !Array.isArray(cond)) {
        return Object.keys(cond).every(function (op) {
          var x = cond[op];
          switch (op) {
            case '$in': return Array.isArray(x) && x.some(function (e) { return igual(v, e); });
            case '$gte': return typeof v === 'number' && typeof x === 'number' && cmpNum(v, x) >= 0;
            case '$lte': return typeof v === 'number' && typeof x === 'number' && cmpNum(v, x) <= 0;
            case '$gt': return typeof v === 'number' && typeof x === 'number' && cmpNum(v, x) > 0;
            case '$lt': return typeof v === 'number' && typeof x === 'number' && cmpNum(v, x) < 0;
            default: throw new Error('[rcj-line-offline] operador de consulta no soportado: ' + op);
          }
        });
      }
      return igual(v, cond);
    });
  }
  // Orden de tipos de MongoDB: null < números < strings < ObjectId (los ids locales son 24 hex)
  function rangoTipo(v) {
    if (v === undefined || v === null) return 1;
    if (typeof v === 'number') return 2;
    if (esHex24(v)) return 7;
    if (typeof v === 'string') return 3;
    return 4;
  }
  function cmpMongo(a, b) {
    var ra = rangoTipo(a), rb = rangoTipo(b);
    if (ra !== rb) return ra - rb;
    if (ra === 1) return 0;
    if (ra === 2) return cmpNum(a, b);
    var sa = ra === 7 ? a.toLowerCase() : String(a), sb = rb === 7 ? b.toLowerCase() : String(b);
    return sa < sb ? -1 : (sa > sb ? 1 : 0);
  }
  function elegir(doc, seleccion) {
    if (!doc || !seleccion) return doc;
    var campos = String(seleccion).split(/\s+/).filter(Boolean);
    var out = { _id: doc._id };
    campos.forEach(function (c) { if (Object.prototype.hasOwnProperty.call(doc, c)) out[c] = doc[c]; });
    return out;
  }

  async function tiposDeBaldosa(cache) {
    if (cache.tipos) return cache.tipos;
    var r = await R.api.request('GET', '/api/maps/line/tilesets?populate=true');
    var m = new Map();
    (Array.isArray(r.data) ? r.data : []).forEach(function (set) {
      (set.tiles || []).forEach(function (e) {
        var tt = e.tileType;
        if (tt && typeof tt === 'object' && tt._id && !m.has(tt._id)) m.set(tt._id, tt);
      });
    });
    cache.tipos = m;
    return m;
  }

  async function poblar(docs, spec, cache) {
    if (typeof spec === 'string') spec = { path: spec };
    var ruta = spec.path;
    if (ruta === 'tiles.tileType') {
      var tipos = await tiposDeBaldosa(cache);
      docs.forEach(function (d) {
        if (!d || !Array.isArray(d.tiles)) return;
        d.tiles.forEach(function (t) {
          if (t && t.tileType !== undefined && t.tileType !== null && typeof t.tileType !== 'object') {
            var tt = tipos.get(String(t.tileType));
            t.tileType = tt ? clonar(tt) : null;
          }
        });
      });
      return;
    }
    var coleccion = REFERENCIAS[ruta];
    if (!coleccion) throw new Error('[rcj-line-offline] populate no soportado: ' + ruta);
    for (var i = 0; i < docs.length; i++) {
      var d = docs[i];
      if (!d || d[ruta] === undefined || d[ruta] === null) continue;
      var ref = await R.store.get(coleccion, normId(String(d[ruta])));
      if (!ref) { d[ruta] = null; continue; }
      ref = elegir(ref, spec.select);
      if (spec.populate) await poblar([ref], spec.populate, cache);
      d[ruta] = ref;
    }
  }

  function Consulta(coleccion, filtro, porId) {
    this.coleccion = coleccion;
    this.filtro = filtro;
    this.porId = porId;
    this._orden = null;
    this._seleccion = null;
    this._poblados = [];
  }
  Consulta.prototype.sort = function (orden) { this._orden = orden; return this; };
  Consulta.prototype.select = function (s) { this._seleccion = s; return this; };
  Consulta.prototype.lean = function () { return this; };
  Consulta.prototype.populate = function (a, seleccion) {
    var self = this;
    if (Array.isArray(a)) a.forEach(function (x) { self._poblados.push(x); });
    else if (typeof a === 'string') self._poblados.push({ path: a, select: seleccion });
    else self._poblados.push(a);
    return this;
  };
  Consulta.prototype._ejecutar = async function () {
    var self = this;
    var docs;
    if (self.porId !== undefined) {
      var uno = R.esIdValido(self.porId) ? await R.store.get(self.coleccion, normId(String(self.porId))) : null;
      docs = uno ? [uno] : [];
    } else {
      docs = await R.store.list(self.coleccion, function (d) { return coincide(d, self.filtro); });
      // Orden natural (createdAt y _id, como documenta local/nucleo/api.js) y después .sort()
      docs.sort(function (a, b) {
        var ca = String(a.createdAt || ''), cb = String(b.createdAt || '');
        if (ca !== cb) return ca < cb ? -1 : 1;
        return String(a._id) < String(b._id) ? -1 : (String(a._id) > String(b._id) ? 1 : 0);
      });
      if (self._orden) {
        var claves = Object.keys(self._orden);
        docs.sort(function (a, b) {
          for (var i = 0; i < claves.length; i++) {
            var c = cmpMongo(a[claves[i]], b[claves[i]]) * (self._orden[claves[i]] < 0 ? -1 : 1);
            if (c !== 0) return c;
          }
          return 0;
        });
      }
    }
    if (self._seleccion) docs = docs.map(function (d) { return elegir(d, self._seleccion); });
    var cache = {};
    for (var i = 0; i < self._poblados.length; i++) await poblar(docs, self._poblados[i], cache);
    return self.porId !== undefined ? (docs[0] || null) : docs;
  };
  // exec(cb): los errores que salen del callback (o de su promesa) terminan el pedido con 500
  Consulta.prototype.exec = function (cb) {
    var ctx = C.peticionActual();
    var p = this._ejecutar().then(function (docs) { return cb(null, docs); }, function (err) { return cb(err, null); });
    p.then(null, function (e) {
      if (ctx) ctx.fallar(e);
      else console.error('[RCJLocal.salidas] consulta', e);
    });
  };

  function Modelo(coleccion) {
    return {
      find: function (filtro) { return new Consulta(coleccion, filtro || {}); },
      findById: function (id) { return new Consulta(coleccion, null, id === undefined ? null : id); }
    };
  }
  C.Modelo = Modelo;

  // ---------------------------------------------------------------- routes/api/lineMaps.js
  (function () {
    var publicRouter = C.Router('/api/maps/line');
    var privateRouter = C.Router('/api/maps/line');
    var adminRouter = C.Router('/api/maps/line');
    var archiver = C.archiver;
    var lineMap = Modelo('lineMaps');
    var lineSSR = C.exportsDe('helper/lineSSR');
    var lineMapPDF = C.exportsDe('helper/lineMapPDF');
    var scoreSheetPDFLine2 = C.exportsDe('helper/scoreSheetPDFLine2');
// ===== INICIO VERBATIM routes/api/lineMaps.js:24-29 =====
publicRouter.get('/image/:mapid', getMapImage);
publicRouter.post('/map-image-pdf', handlePublicMapImagePDF);
publicRouter.post('/map-image-png', handlePublicMapImagePNG);
publicRouter.post('/scoresheet', handleScoresheet);

adminRouter.get('/export', handleExport);
// ===== FIN VERBATIM routes/api/lineMaps.js:24-29 =====

// ===== INICIO VERBATIM routes/api/lineMaps.js:650-804 =====
async function handlePublicMapImagePDF(req, res, next) {
  const map = req.body;
  const paperSize = req.body.paperSize || 'A4';

  if (!map || !map.tiles) {
    return res.status(400).send({
      msg: 'Invalid map data',
    });
  }

  // Convert tiles from object map to array if necessary
  if (!Array.isArray(map.tiles)) {
    const tiles = [];
    for (const i in map.tiles) {
      if (map.tiles.hasOwnProperty(i)) {
        const tile = map.tiles[i];
        if (isNaN(i)) {
          const coords = i.split(',');
          tile.x = parseInt(coords[0]);
          tile.y = parseInt(coords[1]);
          tile.z = parseInt(coords[2]);
        }
        tiles.push(tile);
      }
    }
    map.tiles = tiles;
  }

  await lineMapPDF.generateAndSendBulkMapImagesPDF(
    res,
    [map],
    map.competitionName || 'Competition',
    map.leagueName || 'League',
    paperSize
  );
}

async function handlePublicMapImagePNG(req, res, next) {
  const map = req.body;

  if (!map || !map.tiles) {
    return res.status(400).send({
      msg: 'Invalid map data',
    });
  }

  // Convert tiles from object map to array if necessary
  if (!Array.isArray(map.tiles)) {
    const tiles = [];
    for (const i in map.tiles) {
      if (map.tiles.hasOwnProperty(i)) {
        const tile = map.tiles[i];
        if (isNaN(i)) {
          const coords = i.split(',');
          tile.x = parseInt(coords[0]);
          tile.y = parseInt(coords[1]);
          tile.z = parseInt(coords[2]);
        }
        tiles.push(tile);
      }
    }
    map.tiles = tiles;
  }

  const buffer = await lineSSR.generatePNG(map, map.rule || '2026');
  res.setHeader('Content-Type', 'image/png');
  res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(map.name || 'map')}.png"`);
  res.send(buffer);
}

function getMapsFromRequest(req, callback) {
  const competitionId = req.query.competition;
  const leagueId = req.query.league;
  const mapIds = req.query.ids ? req.query.ids.split(',') : (req.params.map ? [req.params.map] : null);

  let mapQuery;
  if (mapIds) {
    mapQuery = lineMap.find({ _id: { $in: mapIds.filter(ObjectId.isValid) } });
  } else if (ObjectId.isValid(competitionId)) {
    mapQuery = lineMap.find({ competition: competitionId, league: leagueId });
  } else {
    return callback(new Error('Missing selection'), null);
  }

  mapQuery.populate('tiles.tileType').populate('competition', 'name').lean().exec(callback);
}

function handleExport(req, res) {
  const { type, format } = req.query;
  const rule = req.query.rule || '2026';

  getMapsFromRequest(req, async (err, maps) => {
    if (err) {
      return res.status(400).send({ msg: err.message });
    }
    if (!maps || maps.length === 0) {
      return res.status(404).send({ msg: 'No maps found' });
    }

    const competitionId = maps[0].competition ? maps[0].competition._id : null;

    if (!auth.authCompetition(req.user, competitionId, ACCESSLEVELS.ADMIN)) {
      return res.status(401).send({
        msg: 'You have no authority to access this api',
      });
    }

    const competitionName = maps[0].competition ? maps[0].competition.name : 'Competition';
    const leagueName = maps[0].league || 'League';

    if (type === 'scoresheets') {
      return await scoreSheetPDFLine2.generateScoreSheetsFromMaps(res, maps, rule, true);
    }

    if (type === 'maps') {
      if (format === 'png') {
        const archive = archiver('zip', { zlib: { level: 9 } });
        res.attachment('maps.zip');
        archive.pipe(res);
        for (const map of maps) {
          const buffer = await lineSSR.generatePNG(map, rule);
          archive.append(buffer, { name: `${map.name || map._id}.png` });
        }
        return archive.finalize();
      }
      const paperSize = req.query.paperSize || 'A4';
      return lineMapPDF.generateAndSendBulkMapImagesPDF(
        res,
        maps,
        competitionName,
        leagueName,
        paperSize
      );
    }

    res.status(400).send('Invalid export type');
  });
}

function getMapImage(req, res) {
  const mapid = req.params.mapid;
  if (!ObjectId.isValid(mapid)) {
    return res.status(400).send('Invalid map ID');
  }

  lineMap.findById(mapid).populate('tiles.tileType').lean().exec(async (err, map) => {
    if (err || !map) {
      return res.status(404).send('Map not found');
    }
    const buffer = await lineSSR.generatePNG(map, req.query.rule || '2026');
    res.setHeader('Content-Type', 'image/png');
    res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(map.name || mapid)}.png"`);
    res.send(buffer);
  });
}
// ===== FIN VERBATIM routes/api/lineMaps.js:650-804 =====

// ===== INICIO VERBATIM routes/api/lineMaps.js:818-822 =====
async function handleScoresheet(req, res) {
  const map = req.body;
  const rule = map.rule || '2026';
  await scoreSheetPDFLine2.generateScoreSheetFromMap(res, map, rule);
}
// ===== FIN VERBATIM routes/api/lineMaps.js:818-822 =====
    void privateRouter;
  })();

  // ---------------------------------------------------------------- routes/api/lineRuns.js
  (function () {
    var adminRouter = C.Router('/api/runs/line');
    var logger = C.logger;
    var lineRun = Modelo('lineRuns');
    var scoreSheetLinePDF2 = C.exportsDe('helper/scoreSheetPDFLine2');
// ===== INICIO VERBATIM routes/api/lineRuns.js:663-745 =====
adminRouter.get('/scoresheet2', function (req, res, next) {
  const run = req.query.run || req.params.run;
  const competition = req.query.competition || req.params.competition;
  const field = req.query.field || req.params.field;
  const round = req.query.round || req.params.round;
  const startTime = req.query.startTime || req.params.startTime;
  const endTime = req.query.endTime || req.params.endTime;
  const offset = req.query.offset;

  if (!competition && !run && !round) {
    return next();
  }

  const queryObj = {};
  const sortObj = {};
  if (ObjectId.isValid(competition)) {
    queryObj.competition = ObjectId(competition);
  }
  if (ObjectId.isValid(field)) {
    queryObj.field = ObjectId(field);
  }
  if (ObjectId.isValid(round)) {
    queryObj.round = ObjectId(round);
  }
  if (ObjectId.isValid(run)) {
    queryObj._id = ObjectId(run);
  }

  sortObj.field = 1;
  sortObj.startTime = 1; // sorting by field has the highest priority, followed by time

  if (startTime && endTime) {
    queryObj.startTime = { $gte: parseInt(startTime), $lte: parseInt(endTime) };
  } else if (startTime) {
    queryObj.startTime = { $gte: parseInt(startTime) };
  } else if (endTime) {
    queryObj.startTime = { $lte: parseInt(endTime) };
  }

  const query = lineRun.find(queryObj).sort(sortObj);

  query.select('competition round team field map startTime');
  query.populate([
    {
      path: 'competition',
      select: 'name rule logo leagues',
    },
    {
      path: 'round',
      select: 'name',
    },
    {
      path: 'team',
      select: 'name league teamCode',
    },
    {
      path: 'field',
      select: 'name',
    },
    {
      path: 'map',
      select:
        'name height width length numberOfDropTiles finished startTile tiles indexCount victims EvacuationAreaLoPIndex',
      populate: {
        path: 'tiles.tileType',
      },
    },
  ]);

  query.lean().exec(async function (err, dbRuns) {
    if (err) {
      logger.error(err);
      res.status(400).send({
        msg: 'Could not get runs',
      });
    } else if (dbRuns) {
      dbRuns.map(run => {
        run.startTime += parseInt(offset)*60*1000;
      })
      await scoreSheetLinePDF2.generateScoreSheet(res, dbRuns);
    }
  });
});
// ===== FIN VERBATIM routes/api/lineRuns.js:663-745 =====
  })();

  S.modulosCargados = S.modulosCargados || {};
  S.modulosCargados['local/render/rutas-cms.js'] = true;
})(window);

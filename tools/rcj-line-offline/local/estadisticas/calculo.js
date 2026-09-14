/*
 * rcj-line-offline — área estadísticas.
 * RCJEstadisticas: carga de datos (RCJLocal.store, solo lectura), análisis por corrida y agregados.
 * Módulo puro: no toca el DOM. Lo consumen estadisticas.html (local/estadisticas/pagina.js) y las pruebas.
 *
 * Fuente de verdad del puntaje: RCJLocal.calculateLineScore (CALC verbatim del CMS d805502).
 * El "desglose" de este archivo NO reemplaza a CALC: repite su recorrida solo para atribuir puntos a cada
 * elemento, y cada corrida verifica que la suma del desglose sea === al raw_score que devuelve CALC.
 * La estructura esperada de cada corrida sale de RCJLocal.initLine (IRD verbatim) sobre el mapa.
 */
(function (global) {
  'use strict';

  var R = global.RCJLocal = global.RCJLocal || {};
  var E = global.RCJEstadisticas = global.RCJEstadisticas || {};

  var COLECCIONES = ['competitions', 'rounds', 'teams', 'fields', 'lineMaps', 'lineRuns', 'tileSets'];

  // Etiquetas de status (lang/en.json admin.lineRun.st0..st6, traducidas)
  E.ESTADOS = [
    { valor: 0, nombre: '0. Antes de la corrida' },
    { valor: 1, nombre: '1. Checkpoints definidos' },
    { valor: 2, nombre: '2. Corrida en curso' },
    { valor: 3, nombre: '3. Revisión del registro' },
    { valor: 4, nombre: '4. Terminada (firmada)' },
    { valor: 5, nombre: '5. Aprobación en curso' },
    { valor: 6, nombre: '6. Aprobada' }
  ];
  E.ESTADO_MINIMO_POR_DEFECTO = 3;

  // Tipos de elemento, en el orden de IRD (initRunData.js:22-83) + pseudo-elementos del puntaje de línea
  E.TIPOS = ['gap', 'intersection', 'obstacle', 'ramp', 'seesaw', 'speedbump', 'checkpoint', 'meta', 'exitBonus', 'inicio'];
  E.NOMBRES = {
    gap: 'Gap',
    intersection: 'Intersección',
    obstacle: 'Obstáculo',
    ramp: 'Rampa',
    seesaw: 'Seesaw (balancín)',
    speedbump: 'Speedbump (lomo)',
    checkpoint: 'Checkpoint (baldosas del tramo)',
    meta: 'Meta (baldosas del tramo final)',
    exitBonus: 'Exit bonus',
    inicio: 'Inicio (+5)'
  };

  var ID_META = '58cfd6549792e9313b1610e0';
  var IDS_EVAC = ['58cfd6549792e9313b1610e1', '58cfd6549792e9313b1610e2', '58cfd6549792e9313b1610e3'];

  function clonar(v) {
    if (v === undefined) return undefined;
    return JSON.parse(JSON.stringify(v));
  }
  E.clonar = clonar;

  // ------------------------------------------------------------------ carga (solo lectura)
  /**
   * RCJEstadisticas.cargarDatos() -> Promise<{competitions, rounds, teams, fields, maps, runs, tipos: Map}>
   * Una sola transacción readonly de IndexedDB (instantánea coherente).
   */
  E.cargarDatos = function () {
    if (!R.store) return Promise.reject(new Error('Falta local/nucleo/store.js'));
    var datos = {};
    return R.store.tx(COLECCIONES, function (t) {
      return Promise.all(COLECCIONES.map(function (c) {
        return t.list(c).then(function (arr) { datos[c] = arr; });
      }));
    }, 'readonly').then(function () {
      var tipos = new Map();
      (datos.tileSets || []).forEach(function (s) {
        (s.tiles || []).forEach(function (e) {
          var tt = e.tileType;
          if (tt && typeof tt === 'object' && tt._id && !tipos.has(tt._id)) tipos.set(tt._id, tt);
        });
      });
      return {
        competitions: datos.competitions || [],
        rounds: datos.rounds || [],
        teams: datos.teams || [],
        fields: datos.fields || [],
        maps: datos.lineMaps || [],
        runs: datos.lineRuns || [],
        tipos: tipos
      };
    });
  };

  // ------------------------------------------------------------------ fechas
  /** Fecha de una corrida: startTime (ms) si es > 0; si no, createdAt. */
  E.fechaCorrida = function (run) {
    if (run && typeof run.startTime === 'number' && run.startTime > 0) return run.startTime;
    var t = run && run.createdAt ? Date.parse(run.createdAt) : NaN;
    return isNaN(t) ? 0 : t;
  };
  function dosDig(n) { return (n < 10 ? '0' : '') + n; }
  E.fechaTexto = function (ms, conHora) {
    if (!ms) return '';
    var d = new Date(ms);
    var s = d.getFullYear() + '-' + dosDig(d.getMonth() + 1) + '-' + dosDig(d.getDate());
    if (conHora) s += ' ' + dosDig(d.getHours()) + ':' + dosDig(d.getMinutes());
    return s;
  };
  /** 'YYYY-MM-DD' -> ms del inicio (o fin, si finDelDia) de ese día en hora local. */
  E.diaAms = function (txt, finDelDia) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(txt || '');
    if (!m) return null;
    var d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 0, 0, 0, 0);
    if (finDelDia) d = new Date(d.getTime() + 86400000 - 1);
    return d.getTime();
  };
  E.segundosTexto = function (s) {
    if (s == null || isNaN(s)) return '';
    s = Math.round(s);
    return Math.floor(s / 60) + ':' + dosDig(s % 60);
  };

  // ------------------------------------------------------------------ mapa preparado
  /**
   * Prepara un mapa para estadísticas: tileType poblado, índices de recorrido, tramos, checkpoints,
   * zona de evacuación y estructura esperada de las corridas (IRD verbatim con scored=false).
   */
  E.prepararMapa = function (mapaDoc, tipos) {
    var map = clonar(mapaDoc);
    var faltanTipos = [];
    (map.tiles || []).forEach(function (tile) {
      var tt = tipos ? tipos.get(tile.tileType) : null;
      if (!tt) faltanTipos.push(tile.tileType);
      tile.tileType = tt ? clonar(tt) : { _id: tile.tileType, image: '', gaps: 0, intersections: 0, seesaw: 0 };
      tile.key = tile.x + ',' + tile.y + ',' + tile.z;
    });
    var indexCount = map.indexCount || 0;
    var porIndice = new Array(indexCount);
    (map.tiles || []).forEach(function (tile) {
      (tile.index || []).forEach(function (i, pasada) {
        if (i >= 0 && i < indexCount && !porIndice[i]) porIndice[i] = { indice: i, key: tile.key, tile: tile, pasada: pasada };
      });
    });
    // tramo de cada índice = checkpoints en índices anteriores (CALC: el checkpoint cierra su tramo)
    var cps = 0, marcador = {};
    for (var i = 0; i < indexCount; i++) {
      var p = porIndice[i];
      if (!p) { porIndice[i] = { indice: i, key: null, tile: null, pasada: 0, tramo: cps }; continue; }
      p.tramo = cps;
      p.esCheckpoint = !!p.tile.checkPoint;
      if (p.esCheckpoint) { cps++; marcador[i] = cps; p.numeroCheckpoint = cps; }
    }
    var st = map.startTile || {}, st2 = map.startTile2 || {};
    var keyInicio = st.x + ',' + st.y + ',' + st.z;
    var keyReinicio = st2.x + ',' + st2.y + ',' + st2.z;
    // salto a la zona de evacuación: baldosa cuyo next (en esa pasada) es el reinicio (PFs traverse)
    var zonaDespuesDe = -1;
    (map.tiles || []).forEach(function (tile) {
      (tile.index || []).forEach(function (i, pasada) {
        if (tile.next && tile.next[pasada] === keyReinicio && porIndice[i + 1] && porIndice[i + 1].key === keyReinicio) zonaDespuesDe = i;
      });
    });
    var hayVictimas = !!(map.victims && (map.victims.live > 0 || map.victims.dead > 0));
    var nTramos = cps + 1;
    var tramos = [];
    for (var k = 0; k < nTramos; k++) {
      tramos.push({
        k: k,
        nombre: (k === 0 ? 'Inicio' : 'CP' + k) + ' → ' + (k === nTramos - 1 ? 'Meta' : 'CP' + (k + 1)),
        esZona: hayVictimas && map.EvacuationAreaLoPIndex === k
      });
    }
    var baldosaMeta = null;
    for (var j = indexCount - 1; j >= 0; j--) {
      if (porIndice[j] && porIndice[j].tile && porIndice[j].tile.tileType._id === ID_META) { baldosaMeta = j; break; }
    }

    // estructura esperada de run.tiles/LoPs (IRD verbatim, regla 2026, scored=false)
    var esperada = null, errorEsperada = null;
    if (typeof R.initLine === 'function' && !faltanTipos.length) {
      try {
        var falsa = { started: false, isNL: false, nl: { liveVictim: [], deadVictim: [] }, rescueOrder: [] };
        R.initLine(falsa, map, '2026', false);
        esperada = {
          items: (falsa.tiles || []).map(function (t) {
            return t.scoredItems.map(function (s) { return s.item + ':' + s.count; }).join('|');
          }),
          lops: (falsa.LoPs || []).length
        };
      } catch (e) {
        errorEsperada = String(e && e.message || e);
      }
    }
    // maxRaw como E7 (lineMaps.js:176-212): todo marcado, exitBonus, LoPs 0
    var maxRaw = null;
    if (esperada && typeof R.calculateLineScore === 'function') {
      try {
        var llena = { started: false, isNL: false, nl: { liveVictim: [], deadVictim: [] }, rescueOrder: [] };
        R.initLine(llena, map, '2026', true);
        llena.exitBonus = true;
        var rmax = R.calculateLineScore(llena);
        if (rmax) maxRaw = rmax.raw_score;
      } catch (e2) { maxRaw = null; }
    }

    return {
      _id: map._id, name: map.name, competition: map.competition, doc: map,
      width: map.width, length: map.length, height: map.height, duration: map.duration || 480,
      indexCount: indexCount, porIndice: porIndice, tramos: tramos, nTramos: nTramos,
      marcadorCheckpoint: marcador, keyInicio: keyInicio, keyReinicio: keyReinicio,
      zonaDespuesDe: zonaDespuesDe, hayVictimas: hayVictimas, victims: map.victims || { live: 0, dead: 0 },
      EvacuationAreaLoPIndex: map.EvacuationAreaLoPIndex, indiceMeta: baldosaMeta,
      baldosas: map.tiles || [], faltanTipos: faltanTipos, esperada: esperada, errorEsperada: errorEsperada,
      maxRaw: maxRaw, esEvac: function (tile) { return IDS_EVAC.indexOf(tile.tileType._id) >= 0; }
    };
  };

  // ------------------------------------------------------------------ análisis de una corrida
  function regla(run, ctx) {
    var comp = ctx.competencias[run.competition];
    var team = ctx.equipos[run.team];
    var liga = team ? team.league : 'Line';
    var l = comp && (comp.leagues || []).find(function (x) { return x.league == liga; });
    return l ? l.rule : null;
  }

  /**
   * Desglose que repite la recorrida de CALC (2026.js:8-95) para atribuir puntos por elemento.
   * Devuelve {elementos[], raw, lopsTotal}. Cada elemento: {indice, tramo, item, count, logrado, posibles, obtenidos}.
   */
  E.desglosar = function (run, mapaPrep) {
    var elementos = [];
    var score = 0;
    var lastCheckPointTile = 0, checkPointCount = 0, totalLops = 0;
    var LoPs = run.LoPs || [];
    for (var a = 0; a < LoPs.length; a++) totalLops += LoPs[a];
    var tiles = run.tiles || [];
    for (var i = 0; i < tiles.length; i++) {
      var its = (tiles[i] && tiles[i].scoredItems) || [];
      for (var j = 0; j < its.length; j++) {
        var s = its[j];
        var el = { indice: i, tramo: checkPointCount, item: s.item, count: s.count, logrado: !!s.scored, posibles: 0, obtenidos: 0 };
        switch (s.item) {
          case 'checkpoint':
            var tileCount = i - lastCheckPointTile;
            el.tileCount = tileCount;
            el.lops = LoPs[checkPointCount];
            el.posibles = Math.max(tileCount * 5, 0);
            el.obtenidos = Math.max(tileCount * (5 - 2 * LoPs[checkPointCount]), 0) * s.scored;
            lastCheckPointTile = i;
            checkPointCount++;
            break;
          case 'gap': el.posibles = 10; el.obtenidos = 10 * s.scored; break;
          case 'intersection': el.posibles = 10 * s.count; el.obtenidos = 10 * s.scored * s.count; break;
          case 'obstacle': el.posibles = 20 * s.count; el.obtenidos = 20 * s.scored * s.count; break;
          case 'speedbump': el.posibles = 10; el.obtenidos = 10 * s.scored; break;
          case 'ramp': el.posibles = 10 * s.count; el.obtenidos = 10 * s.scored * s.count; break;
          case 'seesaw': el.posibles = 20 * s.count; el.obtenidos = 20 * s.scored * s.count; break;
          default: el.ignorado = true; // CALC no puntúa otros items
        }
        score += el.obtenidos;
        elementos.push(el);
      }
    }
    var ultimo = tiles.length - 1;
    var tcFinal = tiles.length - lastCheckPointTile - 1;
    var meta = { indice: mapaPrep && mapaPrep.indiceMeta != null ? mapaPrep.indiceMeta : ultimo, tramo: checkPointCount, item: 'meta', count: 1,
      logrado: !!run.exitBonus, tileCount: tcFinal, lops: LoPs[checkPointCount], posibles: Math.max(tcFinal * 5, 0), obtenidos: 0 };
    var exit = { indice: meta.indice, tramo: checkPointCount, item: 'exitBonus', count: 1, logrado: !!run.exitBonus, posibles: 60, obtenidos: 0 };
    if (run.exitBonus) {
      exit.obtenidos = Math.max(60 - 5 * totalLops, 0);
      score += exit.obtenidos;
      meta.obtenidos = Math.max(tcFinal * (5 - 2 * LoPs[checkPointCount]), 0);
      score += meta.obtenidos;
    }
    var inicio = { indice: 0, tramo: 0, item: 'inicio', count: 1, logrado: false, posibles: 5, obtenidos: 0 };
    if (run.showedUp || score > 0) {
      score += 5;
      inicio.logrado = true;
      inicio.obtenidos = 5;
      inicio.implicito = !run.showedUp;
    }
    elementos.push(meta, exit, inicio);
    return { elementos: elementos, raw: score, lopsTotal: totalLops };
  };

  /** Víctimas según los filtros de CALC (2026.js:59-72). */
  E.analizarVictimas = function (run, mapaDoc) {
    var res = { registradas: 0, efectivas: 0, zonaErronea: 0, vivaEnRoja: 0, muertaEnVerde: 0, muertaAntes: 0, kit: 0, detalle: [] };
    var orden = run.rescueOrder || [];
    var live = mapaDoc && mapaDoc.victims ? mapaDoc.victims.live : undefined;
    var L = (run.LoPs || [])[mapaDoc ? mapaDoc.EvacuationAreaLoPIndex : undefined];
    var liveCount = 0;
    orden.forEach(function (v) {
      res.registradas++;
      var estado;
      if (v.victimType == 'LIVE' && v.zoneType == 'RED') { estado = 'zonaErronea'; res.zonaErronea++; res.vivaEnRoja++; }
      else if (v.victimType == 'DEAD' && v.zoneType == 'GREEN') { estado = 'zonaErronea'; res.zonaErronea++; res.muertaEnVerde++; }
      else if (v.victimType == 'DEAD' && liveCount != live) { estado = 'muertaAntes'; res.muertaAntes++; }
      else {
        estado = 'efectiva'; res.efectivas++;
        if (v.victimType == 'KIT') res.kit++;
        if (v.victimType == 'LIVE') liveCount++;
      }
      res.detalle.push({ victimType: v.victimType, zoneType: v.zoneType, estado: estado });
    });
    res.factor = Math.max(1400 - 50 * L, 1250) / 1000;
    res.multiplicadorSinLopsZona = Math.pow(1.4, res.efectivas);
    return res;
  };

  /** Analiza una corrida contra su mapa preparado. ctx = {competencias, equipos, rondas, canchas, mapas} por _id. */
  E.analizarCorrida = function (run, mapaPrep, ctx) {
    var a = {
      _id: run._id, run: run, fecha: E.fechaCorrida(run), status: run.status,
      equipo: ctx.equipos[run.team] ? ctx.equipos[run.team].name : '(sin equipo)',
      ronda: ctx.rondas[run.round] ? ctx.rondas[run.round].name : '',
      cancha: ctx.canchas[run.field] ? ctx.canchas[run.field].name : '',
      mapa: mapaPrep ? mapaPrep.name : '(mapa inexistente)',
      mapId: run.map, teamId: run.team, roundId: run.round,
      guardado: { score: run.score, raw_score: run.raw_score, multiplier: run.multiplier, adjustment: run.adjustment || 0 },
      LoPs: (run.LoPs || []).slice(), exitBonus: !!run.exitBonus, showedUp: !!run.showedUp,
      tiempo: run.time ? (Number(run.time.minutes) || 0) * 60 + (Number(run.time.seconds) || 0) : 0,
      avisos: []
    };
    a.regla = regla(run, ctx);
    if (!mapaPrep) { a.avisos.push('El mapa de la corrida no existe'); a.estructuraOk = false; return a; }

    // estructura
    var ok = !!mapaPrep.esperada;
    if (!mapaPrep.esperada) {
      a.avisos.push(mapaPrep.faltanTipos.length ? 'Faltan tipos de baldosa (tilesets sin sembrar)' : 'No se pudo derivar la estructura del mapa');
    } else {
      var tiles = run.tiles || [];
      if (!tiles.length) { ok = false; a.avisos.push('Corrida sin baldosas inicializadas'); }
      else if (tiles.length !== mapaPrep.esperada.items.length) { ok = false; a.avisos.push('run.tiles tiene ' + tiles.length + ' índices y el mapa ' + mapaPrep.esperada.items.length); }
      else {
        for (var i = 0; i < tiles.length; i++) {
          var firma = ((tiles[i] && tiles[i].scoredItems) || []).map(function (s) { return s.item + ':' + s.count; }).join('|');
          if (firma !== mapaPrep.esperada.items[i]) { ok = false; a.avisos.push('Elementos del índice ' + i + ' distintos de los del mapa'); break; }
        }
      }
      if ((run.LoPs || []).length !== mapaPrep.esperada.lops) { ok = false; a.avisos.push('LoPs tiene ' + (run.LoPs || []).length + ' tramos y el mapa ' + mapaPrep.esperada.lops); }
    }
    a.estructuraOk = ok;

    // recálculo con CALC verbatim
    if (a.regla !== '2026') {
      a.avisos.push('Regla ' + a.regla + ': el recálculo solo cubre la regla 2026');
    } else if (typeof R.calculateLineScore === 'function') {
      var copia = clonar(run);
      copia.map = mapaPrep.doc;
      var calc = R.calculateLineScore(copia);
      if (!calc) {
        a.recalculado = null;
        a.consistente = false;
        a.avisos.push('CALC lanzó una excepción (el backend respondería 202)');
      } else {
        a.recalculado = { score: calc.score, raw_score: calc.raw_score, multiplier: calc.multiplier };
        a.consistente = calc.score === run.score && calc.raw_score === run.raw_score && calc.multiplier === run.multiplier;
      }
    }
    a.desglose = E.desglosar(run, mapaPrep);
    if (a.recalculado && a.desglose.raw !== a.recalculado.raw_score) a.avisos.push('El desglose no coincide con CALC');
    a.victimas = E.analizarVictimas(run, mapaPrep.doc);
    return a;
  };

  // ------------------------------------------------------------------ índices de apoyo
  function porId(arr) {
    var o = {};
    (arr || []).forEach(function (d) { o[d._id] = d; });
    return o;
  }
  E.contexto = function (datos) {
    return {
      competencias: porId(datos.competitions), equipos: porId(datos.teams), rondas: porId(datos.rounds),
      canchas: porId(datos.fields), mapas: porId(datos.maps)
    };
  };

  // ------------------------------------------------------------------ filtros
  /**
   * filtros = {competition, map ('' = todos), team, round, desde 'YYYY-MM-DD', hasta, estadoMinimo}
   * Devuelve las corridas (documentos) que pasan.
   */
  E.filtrarCorridas = function (datos, f) {
    var desde = E.diaAms(f.desde, false), hasta = E.diaAms(f.hasta, true);
    var min = f.estadoMinimo == null || f.estadoMinimo === '' ? E.ESTADO_MINIMO_POR_DEFECTO : Number(f.estadoMinimo);
    return datos.runs.filter(function (r) {
      if (f.competition && r.competition !== f.competition) return false;
      if (f.map && r.map !== f.map) return false;
      if (f.team && r.team !== f.team) return false;
      if (f.round && r.round !== f.round) return false;
      if ((Number(r.status) || 0) < min) return false;
      var fe = E.fechaCorrida(r);
      if (desde != null && fe < desde) return false;
      if (hasta != null && fe > hasta) return false;
      return true;
    });
  };

  /** Mapa por defecto: ?map= si existe en la competencia; si no, el de más corridas (empate: nombre). */
  E.mapaPorDefecto = function (datos, competition, pedido) {
    var mapas = datos.maps.filter(function (m) { return !competition || m.competition === competition; });
    if (pedido && mapas.some(function (m) { return m._id === pedido; })) return pedido;
    var cuenta = {};
    datos.runs.forEach(function (r) { cuenta[r.map] = (cuenta[r.map] || 0) + 1; });
    mapas.sort(function (a, b) { return (cuenta[b._id] || 0) - (cuenta[a._id] || 0) || String(a.name).localeCompare(String(b.name)); });
    return mapas.length ? mapas[0]._id : '';
  };

  // ------------------------------------------------------------------ agregados
  function nuevoContador() { return { intentos: 0, logrados: 0, posibles: 0, obtenidos: 0 }; }
  function sumar(c, el) {
    c.intentos++;
    if (el.logrado) c.logrados++;
    c.posibles += el.posibles;
    c.obtenidos += el.obtenidos;
  }
  function cerrar(c) {
    c.pct = c.intentos ? c.logrados / c.intentos * 100 : null;
    c.perdidos = c.posibles - c.obtenidos;
    return c;
  }
  function stats(valores) {
    var v = valores.filter(function (x) { return typeof x === 'number' && !isNaN(x); });
    if (!v.length) return { n: 0, promedio: null, mejor: null, peor: null };
    var s = 0;
    v.forEach(function (x) { s += x; });
    return { n: v.length, promedio: s / v.length, mejor: Math.max.apply(null, v), peor: Math.min.apply(null, v), suma: s };
  }
  E.stats = stats;

  /**
   * RCJEstadisticas.calcular(datos, filtros) -> resultado completo para la página.
   */
  E.calcular = function (datos, filtros) {
    var ctx = E.contexto(datos);
    var corridas = E.filtrarCorridas(datos, filtros);
    var preparados = {};
    function prep(id) {
      if (!(id in preparados)) preparados[id] = ctx.mapas[id] ? E.prepararMapa(ctx.mapas[id], datos.tipos) : null;
      return preparados[id];
    }
    var analisis = corridas.map(function (r) { return E.analizarCorrida(r, prep(r.map), ctx); });
    analisis.sort(function (a, b) { return a.fecha - b.fecha || String(a._id).localeCompare(String(b._id)); });

    var mapaSel = filtros.map ? prep(filtros.map) : null;
    var validas = analisis.filter(function (a) { return a.estructuraOk; });

    // ---- por tipo de elemento (todas las corridas con estructura válida, cada una contra su mapa)
    var porTipo = {};
    E.TIPOS.forEach(function (t) { porTipo[t] = nuevoContador(); });
    var total = nuevoContador();
    validas.forEach(function (a) {
      a.desglose.elementos.forEach(function (el) {
        if (el.ignorado) return;
        sumar(porTipo[el.item], el);
        total.posibles += el.posibles;
        total.obtenidos += el.obtenidos;
      });
    });
    var tablaTipos = E.TIPOS.map(function (t) {
      var c = cerrar(porTipo[t]);
      c.tipo = t; c.nombre = E.NOMBRES[t];
      return c;
    }).filter(function (c) { return c.intentos > 0; });
    total.intentos = validas.length;
    total.perdidos = total.posibles - total.obtenidos;

    // ---- por índice y por baldosa física (solo con un mapa elegido)
    var heat = null, tramos = null;
    if (mapaSel) {
      var delMapa = validas.filter(function (a) { return a.mapId === mapaSel._id; });
      var indices = [];
      for (var i = 0; i < mapaSel.indexCount; i++) {
        indices.push({ indice: i, key: mapaSel.porIndice[i].key, tramo: mapaSel.porIndice[i].tramo,
          numeroCheckpoint: mapaSel.porIndice[i].numeroCheckpoint || null, total: nuevoContador(), elementos: {}, fallas: [] });
      }
      delMapa.forEach(function (a) {
        a.desglose.elementos.forEach(function (el) {
          // 'inicio' (+5 por presentarse) no mide al robot en la baldosa 0: queda fuera del mapa de calor
          if (el.ignorado || el.item === 'inicio' || el.indice == null || !indices[el.indice]) return;
          var d = indices[el.indice];
          if (!d.elementos[el.item]) d.elementos[el.item] = nuevoContador();
          sumar(d.elementos[el.item], el);
          sumar(d.total, el);
          if (!el.logrado || el.obtenidos < el.posibles) {
            d.fallas.push({ runId: a._id, equipo: a.equipo, ronda: a.ronda, fecha: a.fecha, item: el.item, logrado: el.logrado, perdidos: el.posibles - el.obtenidos });
          }
        });
      });
      indices.forEach(function (d) {
        cerrar(d.total);
        d.lista = E.TIPOS.filter(function (t) { return d.elementos[t]; }).map(function (t) {
          var c = cerrar(d.elementos[t]);
          c.tipo = t; c.nombre = E.NOMBRES[t];
          return c;
        });
      });
      var baldosas = {};
      mapaSel.baldosas.forEach(function (tile) {
        var b = { key: tile.key, tile: tile, indices: (tile.index || []).slice(), total: nuevoContador(), pasadas: [], elementos: {} };
        b.indices.forEach(function (i) {
          var d = indices[i];
          if (!d) return;
          b.pasadas.push(d);
          ['intentos', 'logrados', 'posibles', 'obtenidos'].forEach(function (k) { b.total[k] += d.total[k]; });
          Object.keys(d.elementos).forEach(function (t) {
            if (!b.elementos[t]) b.elementos[t] = nuevoContador();
            ['intentos', 'logrados', 'posibles', 'obtenidos'].forEach(function (k) { b.elementos[t][k] += d.elementos[t][k]; });
          });
        });
        cerrar(b.total);
        b.lista = E.TIPOS.filter(function (t) { return b.elementos[t]; }).map(function (t) {
          var c = cerrar(b.elementos[t]);
          c.tipo = t; c.nombre = E.NOMBRES[t];
          return c;
        });
        baldosas[tile.key] = b;
      });
      heat = { mapa: mapaSel, corridas: delMapa.length, indices: indices, baldosas: baldosas };

      // ---- LoPs por tramo
      tramos = mapaSel.tramos.map(function (tr) {
        var valores = delMapa.map(function (a) { return a.LoPs[tr.k]; });
        var st = stats(valores);
        var dist = { '0': 0, '1': 0, '2': 0, '3+': 0 };
        valores.forEach(function (v) {
          if (v >= 3) dist['3+']++; else if (v === 2) dist['2']++; else if (v === 1) dist['1']++; else dist['0']++;
        });
        var perdidosLops = 0;
        delMapa.forEach(function (a) {
          a.desglose.elementos.forEach(function (el) {
            if (el.tramo !== tr.k) return;
            if (el.item === 'checkpoint' && el.logrado) perdidosLops += el.posibles - el.obtenidos;
            if (el.item === 'meta' && el.logrado) perdidosLops += el.posibles - el.obtenidos;
          });
        });
        return { k: tr.k, nombre: tr.nombre, esZona: tr.esZona, n: st.n, promedio: st.promedio, maximo: st.mejor, distribucion: dist, perdidosPorLops: perdidosLops };
      });
    }

    // ---- víctimas (corridas cuyo mapa tiene víctimas)
    var conVictimas = analisis.filter(function (a) { var m = prep(a.mapId); return m && m.hayVictimas; });
    var vic = { corridas: conVictimas.length, registradas: 0, efectivas: 0, zonaErronea: 0, vivaEnRoja: 0, muertaEnVerde: 0, muertaAntes: 0, kit: 0, maximoPosible: 0 };
    var mults = [], multsConRescate = [], multsSinLops = [];
    conVictimas.forEach(function (a) {
      var v = a.victimas;
      ['registradas', 'efectivas', 'zonaErronea', 'vivaEnRoja', 'muertaEnVerde', 'muertaAntes', 'kit'].forEach(function (k) { vic[k] += v[k]; });
      var m = prep(a.mapId);
      vic.maximoPosible += (m.victims.live || 0) + (m.victims.dead || 0);
      if (a.recalculado) {
        mults.push(a.recalculado.multiplier);
        if (v.efectivas > 0) { multsConRescate.push(a.recalculado.multiplier); multsSinLops.push(v.multiplicadorSinLopsZona); }
      }
    });
    vic.pctEfectivas = vic.registradas ? vic.efectivas / vic.registradas * 100 : null;
    vic.pctSobreMaximo = vic.maximoPosible ? vic.efectivas / vic.maximoPosible * 100 : null;
    vic.multiplicadorPromedio = stats(mults).promedio;
    vic.multiplicadorPromedioConRescate = stats(multsConRescate).promedio;
    vic.multiplicadorPromedioSinLopsZona = stats(multsSinLops).promedio;

    // ---- exit bonus, tiempo, LoPs, puntaje
    var exitN = analisis.filter(function (a) { return a.exitBonus; }).length;
    var exitPts = stats(analisis.filter(function (a) { return a.desglose; }).map(function (a) {
      return a.desglose.elementos.filter(function (el) { return el.item === 'exitBonus'; })[0].obtenidos;
    }));
    var tiempos = stats(analisis.filter(function (a) { return a.tiempo > 0; }).map(function (a) { return a.tiempo; }));
    var lops = stats(analisis.map(function (a) { return a.desglose ? a.desglose.lopsTotal : NaN; }));
    var serie = analisis.map(function (a) {
      return { runId: a._id, fecha: a.fecha, score: a.guardado.score, raw: a.guardado.raw_score, equipo: a.equipo, ronda: a.ronda, mapa: a.mapa };
    });
    var scoreSt = stats(analisis.map(function (a) { return a.guardado.score; }));
    var rawSt = stats(analisis.map(function (a) { return a.guardado.raw_score; }));
    function quien(valor, campo) {
      var x = analisis.filter(function (a) { return a.guardado[campo] === valor; })[0];
      return x ? { runId: x._id, equipo: x.equipo, ronda: x.ronda, fecha: x.fecha } : null;
    }
    scoreSt.mejorCorrida = scoreSt.n ? quien(scoreSt.mejor, 'score') : null;
    scoreSt.peorCorrida = scoreSt.n ? quien(scoreSt.peor, 'score') : null;

    var inconsistentes = analisis.filter(function (a) { return a.consistente === false; });
    var sinEstructura = analisis.filter(function (a) { return !a.estructuraOk; });

    return {
      filtros: clonar(filtros), corridas: analisis, n: analisis.length, nValidas: validas.length,
      mapa: mapaSel, heat: heat, tramos: tramos, tablaTipos: tablaTipos, totalLinea: total,
      victimas: vic, exitBonus: { n: exitN, pct: analisis.length ? exitN / analisis.length * 100 : null, puntosPromedio: exitPts.promedio },
      tiempo: tiempos, lops: lops, score: scoreSt, raw: rawSt, serie: serie,
      inconsistentes: inconsistentes, sinEstructura: sinEstructura
    };
  };

  // ------------------------------------------------------------------ escala de color (fallo = oscuro)
  // Rampa secuencial de un solo tono (naranja): claro = 100 % de éxito, oscuro = 0 % de éxito.
  var CLARO = [253, 238, 228], OSCURO = [143, 45, 11];
  E.colorExito = function (pct) {
    if (pct == null || isNaN(pct)) return null;
    var f = 1 - Math.max(0, Math.min(100, pct)) / 100;
    var c = CLARO.map(function (v, i) { return Math.round(v + (OSCURO[i] - v) * f); });
    return 'rgb(' + c.join(',') + ')';
  };
  /** Tinta legible sobre el color de la escala (blanco en los tonos oscuros). */
  E.tintaSobre = function (pct) {
    return pct != null && pct < 45 ? '#ffffff' : '#1e293b';
  };
})(window);

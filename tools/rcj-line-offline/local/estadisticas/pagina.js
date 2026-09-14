/*
 * rcj-line-offline — área estadísticas.
 * Controlador de estadisticas.html (módulo AngularJS RCJEstadisticasApp). Página NUEVA: no existe en el CMS.
 * Solo LEE datos (RCJEstadisticas.cargarDatos -> RCJLocal.store en una transacción readonly); nunca escribe.
 * Los cálculos están en local/estadisticas/calculo.js, el CSV en csv.js y los gráficos SVG en graficos.js.
 * El mapa de calor dibuja cada baldosa como templates/tile.html (imagen con rotación, cintas de evacuación,
 * lomos, obstáculo, rampa, inicio y número de checkpoint) con una capa de color encima.
 */
(function (global) {
  'use strict';

  var E = global.RCJEstadisticas;
  var R = global.RCJLocal;
  // La competencia activa que elige el Inicio (misma clave que local/ui/comun.js del área admin)
  var CLAVE_ACTIVA = 'rcjLocalCompetenciaActiva';

  var app = global.app = angular.module('RCJEstadisticasApp', ['ngTouch', 'ngAnimate', 'ui.bootstrap', 'pascalprecht.translate', 'ngCookies', 'ngSanitize']);

  app.filter('num', function () { return function (n, dec) { return E.fmt(n, dec); }; });
  app.filter('pct', function () {
    return function (n, dec) { return n == null || isNaN(n) ? '–' : E.fmt(n, dec == null ? 1 : dec) + ' %'; };
  });
  app.filter('fecha', function () { return function (ms, hora) { return E.fechaTexto(ms, hora); }; });
  app.filter('mmss', function () { return function (s) { return s ? E.segundosTexto(s) : '–'; }; });

  function leerLS(k) {
    try { return global.localStorage.getItem(k) || ''; } catch (e) { return ''; }
  }
  function rango(n) {
    var a = [];
    for (var i = 0; i < n; i++) a.push(i);
    return a;
  }
  function porNombre(a, b) { return String(a.name || '').localeCompare(String(b.name || ''), 'es'); }
  function rgba(pct, alfa) {
    var c = E.colorExito(pct);
    return c ? c.replace('rgb(', 'rgba(').replace(')', ',' + alfa + ')') : null;
  }

  /** Si la base todavía no tiene tilesets (nadie llamó a la API), los tipos salen de data/tilesets.json (solo lectura). */
  function asegurarTipos(datos) {
    if (datos.tipos.size) return Promise.resolve(datos);
    return fetch('data/tilesets.json', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (sets) {
      (sets || []).forEach(function (s) {
        (s.tiles || []).forEach(function (e) {
          var tt = e.tileType;
          if (tt && tt._id && !datos.tipos.has(tt._id)) datos.tipos.set(tt._id, tt);
        });
      });
      return datos;
    }).catch(function () { return datos; });
  }

  app.controller('EstadisticasController', ['$scope', '$sce', '$timeout', '$window', function ($scope, $sce, $timeout, $window) {
    var datos = null;
    var mapaDeGrilla = null;

    $scope.E = E;
    $scope.estados = E.ESTADOS;
    $scope.estado = { cargando: true, error: null };
    $scope.f = { competition: '', map: '', team: '', round: '', desde: '', hasta: '', estadoMinimo: E.ESTADO_MINIMO_POR_DEFECTO };
    $scope.fechas = { desde: null, hasta: null };
    $scope.vista = { modo: 'fisica', pasada: 0, piso: 0, formato: 'excel', seleccion: null, indiceSel: null, compacto: $window.innerWidth < 576 };
    $scope.opciones = { competencias: [], mapas: [], equipos: [], rondas: [] };
    $scope.res = null;
    $scope.grilla = null;
    $scope.svg = {};

    // ---------------------------------------------------------------- carga
    function competenciaInicial() {
      var ids = datos.competitions.map(function (c) { return c._id; });
      var pedida = R.param('competition');
      if (pedida && ids.indexOf(pedida) >= 0) return pedida;
      var mapa = datos.maps.filter(function (m) { return m._id === R.param('map'); })[0];
      if (mapa && ids.indexOf(mapa.competition) >= 0) return mapa.competition;
      var activa = leerLS(CLAVE_ACTIVA);
      if (activa && ids.indexOf(activa) >= 0) return activa;
      var cuenta = {};
      datos.runs.forEach(function (r) { cuenta[r.competition] = (cuenta[r.competition] || 0) + 1; });
      var orden = datos.competitions.slice().sort(function (a, b) { return (cuenta[b._id] || 0) - (cuenta[a._id] || 0) || porNombre(a, b); });
      return orden.length ? orden[0]._id : '';
    }

    function opcionesDeCompetencia() {
      var cid = $scope.f.competition;
      var cuenta = {};
      datos.runs.forEach(function (r) { cuenta[r.map] = (cuenta[r.map] || 0) + 1; });
      $scope.opciones.mapas = datos.maps.filter(function (m) { return !cid || m.competition === cid; }).sort(porNombre).map(function (m) {
        var n = cuenta[m._id] || 0;
        return { _id: m._id, etiqueta: m.name + ' · ' + n + (n === 1 ? ' corrida' : ' corridas') };
      });
      $scope.opciones.equipos = datos.teams.filter(function (t) { return !cid || t.competition === cid; }).sort(porNombre);
      $scope.opciones.rondas = datos.rounds.filter(function (t) { return !cid || t.competition === cid; }).sort(porNombre);
    }

    /** Usa un conjunto de datos (el de la base o, en las pruebas, uno armado en memoria). */
    $scope.usarDatos = function (d) {
      var primera = !datos;
      datos = d;
      $scope.opciones.competencias = d.competitions.slice().sort(porNombre);
      var f = $scope.f;
      if (primera) {
        f.competition = competenciaInicial();
        opcionesDeCompetencia();
        f.map = E.mapaPorDefecto(d, f.competition, R.param('map'));
        f.team = R.param('team');
        f.round = R.param('round');
        if (E.diaAms(R.param('desde'))) { f.desde = R.param('desde'); $scope.fechas.desde = new Date(E.diaAms(f.desde)); }
        if (E.diaAms(R.param('hasta'))) { f.hasta = R.param('hasta'); $scope.fechas.hasta = new Date(E.diaAms(f.hasta)); }
        if (R.param('estado') !== '' && !isNaN(Number(R.param('estado')))) f.estadoMinimo = Number(R.param('estado'));
      } else {
        if (!d.competitions.some(function (c) { return c._id === f.competition; })) f.competition = competenciaInicial();
        opcionesDeCompetencia();
        if (f.map && !$scope.opciones.mapas.some(function (m) { return m._id === f.map; })) f.map = E.mapaPorDefecto(d, f.competition, '');
      }
      recalcular();
    };

    $scope.cargar = function () {
      $scope.estado.cargando = true;
      $scope.estado.error = null;
      return E.cargarDatos().then(asegurarTipos).then(function (d) {
        $scope.usarDatos(d);
      }).catch(function (e) {
        $scope.estado.error = String((e && e.message) || e);
        if (global.console) global.console.warn('[estadísticas]', e);
      }).then(function () {
        $scope.estado.cargando = false;
        $scope.$applyAsync();
      });
    };

    // ---------------------------------------------------------------- filtros
    $scope.cambioCompetencia = function () {
      opcionesDeCompetencia();
      $scope.f.map = E.mapaPorDefecto(datos, $scope.f.competition, '');
      $scope.f.team = '';
      $scope.f.round = '';
      recalcular();
    };
    function diaDe(fecha) {
      // sin instanceof: una fecha puede venir de otra ventana (iframe) y seguir siendo válida
      var ms = fecha && typeof fecha.getTime === 'function' ? fecha.getTime() : NaN;
      return isNaN(ms) ? '' : E.fechaTexto(ms);
    }
    $scope.cambioFechas = function () {
      $scope.f.desde = diaDe($scope.fechas.desde);
      $scope.f.hasta = diaDe($scope.fechas.hasta);
      recalcular();
    };
    $scope.limpiarFiltros = function () {
      var f = $scope.f;
      f.team = ''; f.round = ''; f.desde = ''; f.hasta = '';
      $scope.fechas.desde = null; $scope.fechas.hasta = null;
      f.estadoMinimo = E.ESTADO_MINIMO_POR_DEFECTO;
      recalcular();
    };
    $scope.hayFiltrosExtra = function () {
      var f = $scope.f;
      return !!(f.team || f.round || f.desde || f.hasta || f.estadoMinimo !== E.ESTADO_MINIMO_POR_DEFECTO);
    };

    function actualizarUrl() {
      try {
        var f = $scope.f, q = [];
        ['competition', 'map', 'team', 'round', 'desde', 'hasta'].forEach(function (k) {
          if (f[k]) q.push(k + '=' + encodeURIComponent(f[k]));
        });
        if (f.estadoMinimo !== E.ESTADO_MINIMO_POR_DEFECTO) q.push('estado=' + f.estadoMinimo);
        var nueva = global.location.pathname + (q.length ? '?' + q.join('&') : '');
        if (nueva !== global.location.pathname + global.location.search) global.history.replaceState(null, '', nueva);
      } catch (e) { /* history no disponible */ }
    }

    // ---------------------------------------------------------------- cálculo
    function recalcular() {
      if (!datos) return;
      // la opción vacía de un <select ng-options> deja null: se normaliza a ''
      ['competition', 'map', 'team', 'round'].forEach(function (k) { if ($scope.f[k] == null) $scope.f[k] = ''; });
      var res = E.calcular(datos, $scope.f);
      $scope.res = res;
      $scope.corridasTabla = res.corridas.slice().reverse(); // más nuevas primero
      armarGrilla();
      if ($scope.vista.seleccion && $scope.res.heat && $scope.res.heat.baldosas[$scope.vista.seleccion.key]) {
        $scope.vista.seleccion = armarDetalle($scope.vista.seleccion.key);
      } else {
        $scope.vista.seleccion = null;
        $scope.vista.indiceSel = null;
      }
      renderGraficos();
      actualizarUrl();
    }
    $scope.recalcular = recalcular;

    $scope.nombreEstado = function (s) {
      var e = E.ESTADOS.filter(function (x) { return x.valor === Number(s); })[0];
      return e ? e.nombre : String(s);
    };
    $scope.urlVista = function (id) { return R.ruta('/line/view/' + id); };
    $scope.urlJuez = function (id) { return R.ruta('/line/judge/' + id); };
    $scope.nombreTipo = function (t) { return E.NOMBRES[t] || t; };

    // ---------------------------------------------------------------- mapa de calor
    // tilerotate / evacTapeRot / checkpointNumber / isStart de javascripts/sign/line_2026.js con sRotate = 0
    function tilerotate(rot) {
      if (!rot) return 0;
      var ro = rot;
      if (ro >= 360) ro -= 360;
      else if (ro < 0) ro += 360;
      return ro;
    }
    function evacTapeRot(tile) {
      var rot = 0;
      if (tile.evacEntrance >= 0) rot = tile.evacEntrance;
      else if (tile.evacExit >= 0) rot = tile.evacExit;
      return rot % 360;
    }
    function checkpointNumber(tile, marker) {
      var txt = '';
      for (var i = 0; i < (tile.index || []).length; i++) {
        if (marker[tile.index[i]]) {
          if (txt !== '') txt += '&';
          txt += marker[tile.index[i]];
        } else {
          return txt;
        }
      }
      return txt;
    }
    function mismaPos(t, p) { return p && t.x == p.x && t.y == p.y && t.z == p.z; }

    function lineasElementos(lista) {
      return lista.map(function (c) {
        return c.nombre + ': ' + c.logrados + '/' + c.intentos + ' (' + E.fmt(c.pct, 1) + ' %)' + (c.perdidos ? ' · pierde ' + E.fmt(c.perdidos) + ' pts' : '');
      });
    }

    function armarGrilla() {
      var heat = $scope.res && $scope.res.heat;
      if (!heat) { $scope.grilla = null; mapaDeGrilla = null; return; }
      var mapa = heat.mapa;
      var v = $scope.vista;
      var maxPasadas = 1;
      mapa.baldosas.forEach(function (t) { maxPasadas = Math.max(maxPasadas, (t.index || []).length); });
      if (mapaDeGrilla !== mapa._id) {
        mapaDeGrilla = mapa._id;
        v.piso = Number((mapa.doc.startTile || {}).z) || 0;
        v.pasada = 0;
        v.seleccion = null;
        v.indiceSel = null;
      }
      if (v.pasada >= maxPasadas) v.pasada = 0;
      if (v.piso >= (mapa.height || 1)) v.piso = 0;
      var porKey = {};
      mapa.baldosas.forEach(function (t) { porKey[t.key] = t; });

      function celda(key) {
        var t = porKey[key];
        var o = { key: key, tile: null };
        if (!t) return o;
        var b = heat.baldosas[key];
        o.tile = t;
        o.rot = tilerotate(t.rot);
        o.img = t.tileType.image || '';
        o.evac = t.evacEntrance >= 0 ? 'ev-entrance.png' : (t.evacExit >= 0 ? 'ev-exit.png' : null);
        o.evacRot = evacTapeRot(t);
        o.esInicio = mismaPos(t, mapa.doc.startTile);
        o.esInicio2 = mismaPos(t, mapa.doc.startTile2);
        o.esCheckpoint = !!t.checkPoint;
        o.cp = checkpointNumber(t, mapa.marcadorCheckpoint);
        o.lomos = rango(Math.min(Number((t.items || {}).speedbumps) || 0, 5));
        o.obstaculo = ((t.items || {}).obstacles || 0) > 0;
        o.rampa = !!(t.items || {}).rampPoints;
        o.indices = (t.index || []).slice();
        var fuente = null;
        if (v.modo === 'pasada') {
          var d = heat.indices[o.indices[v.pasada]];
          fuente = d || null;
          o.fueraDePasada = !d;
        } else {
          fuente = b;
        }
        o.pct = fuente && fuente.total.intentos ? fuente.total.pct : null;
        if (o.pct != null) {
          o.fondo = rgba(o.pct, 0.55);
          o.chip = E.colorExito(o.pct);
          o.tinta = E.tintaSobre(o.pct);
          o.texto = Math.round(o.pct) + ' %';
        }
        var titulo = ['Baldosa (' + key + ')'];
        if (!o.indices.length) titulo.push('Fuera del recorrido puntuable');
        else titulo.push((o.indices.length > 1 ? 'Índices ' : 'Índice ') + o.indices.join(', ') + (v.modo === 'pasada' ? ' · pasada ' + (v.pasada + 1) : ''));
        if (fuente && fuente.lista.length) titulo = titulo.concat(lineasElementos(fuente.lista));
        else if (o.indices.length) titulo.push('Sin elementos puntuables' + (o.fueraDePasada ? ' en esta pasada' : ''));
        o.titulo = titulo.join('\n');
        return o;
      }

      var z = v.piso, filas = [];
      for (var r = 0; r < mapa.length; r++) {
        var fila = [];
        for (var c = 0; c < mapa.width; c++) fila.push(celda(c + ',' + r + ',' + z));
        filas.push(fila);
      }
      $scope.grilla = { filas: filas, pisos: rango(mapa.height || 1), pasadas: rango(maxPasadas), maxPasadas: maxPasadas };
    }
    $scope.armarGrilla = function () {
      armarGrilla();
      if ($scope.vista.seleccion) $scope.vista.seleccion = armarDetalle($scope.vista.seleccion.key);
      $timeout(marcarTira, 0, false);
    };
    $scope.cambiarModo = function (modo) { $scope.vista.modo = modo; $scope.armarGrilla(); };
    $scope.cambiarPiso = function (z) { $scope.vista.piso = z; $scope.armarGrilla(); };

    function armarDetalle(key) {
      var heat = $scope.res && $scope.res.heat;
      var b = heat && heat.baldosas[key];
      if (!b) return null;
      var mapa = heat.mapa;
      var fallas = [];
      var pasadas = b.pasadas.map(function (d, p) {
        d.fallas.forEach(function (x) {
          fallas.push({ runId: x.runId, equipo: x.equipo, ronda: x.ronda, fecha: x.fecha, nombre: E.NOMBRES[x.item] || x.item,
            logrado: x.logrado, perdidos: x.perdidos, indice: d.indice, url: $scope.urlVista(x.runId) });
        });
        return { numero: p + 1, indice: d.indice, tramo: mapa.tramos[d.tramo], numeroCheckpoint: d.numeroCheckpoint, total: d.total, lista: d.lista };
      });
      fallas.sort(function (a, c) { return c.fecha - a.fecha || a.indice - c.indice; });
      return { key: key, tile: b.tile, indices: b.indices, total: b.total, lista: b.lista, pasadas: pasadas, fallas: fallas, corridas: heat.corridas };
    }

    $scope.seleccionar = function (celda) {
      if (!celda || !celda.tile) return;
      $scope.vista.seleccion = armarDetalle(celda.key);
      $scope.vista.indiceSel = celda.indices.length ? celda.indices[$scope.vista.modo === 'pasada' ? $scope.vista.pasada : 0] : null;
      $timeout(marcarTira, 0, false);
    };
    $scope.seleccionarKey = function (key, indice) {
      var heat = $scope.res && $scope.res.heat;
      if (!heat || !heat.baldosas[key]) return;
      var z = Number(key.split(',')[2]) || 0;
      if (z !== $scope.vista.piso) { $scope.vista.piso = z; armarGrilla(); }
      $scope.vista.seleccion = armarDetalle(key);
      $scope.vista.indiceSel = indice == null ? (heat.baldosas[key].indices[0] == null ? null : heat.baldosas[key].indices[0]) : indice;
      $timeout(marcarTira, 0, false);
    };
    $scope.clicTira = function (ev) {
      var g = ev && ev.target && ev.target.closest ? ev.target.closest('.celda-indice') : null;
      if (!g) return;
      var key = g.getAttribute('data-key');
      if (key) $scope.seleccionarKey(key, Number(g.getAttribute('data-indice')));
    };

    function marcarTira() {
      var cont = global.document.getElementById('tiraRecorrido');
      if (!cont) return;
      Array.prototype.forEach.call(cont.querySelectorAll('.celda-indice'), function (g) {
        var activa = $scope.vista.indiceSel != null && Number(g.getAttribute('data-indice')) === $scope.vista.indiceSel;
        g.classList.toggle('activa', activa);
      });
    }

    // ---------------------------------------------------------------- gráficos
    function renderGraficos() {
      var res = $scope.res;
      var op = { compacto: $scope.vista.compacto };
      $scope.svg = {
        evolucion: $sce.trustAsHtml(E.svg.evolucion(res.serie, op)),
        lops: $sce.trustAsHtml(res.tramos ? E.svg.lopsTramos(res.tramos, op) : ''),
        tira: $sce.trustAsHtml(res.heat ? E.svg.tira(res.heat) : ''),
        leyenda: $sce.trustAsHtml(E.svg.leyendaEscala())
      };
      $timeout(function () { engancharEvolucion(); marcarTira(); }, 0, false);
    }

    /** Cruz y tarjetita del gráfico de evolución: sigue al puntero (mouse) o al dedo (tocar). */
    function engancharEvolucion() {
      var cont = global.document.getElementById('graficoEvolucion');
      var tip = global.document.getElementById('tipEvolucion');
      if (!cont || !tip) return;
      tip.hidden = true;
      var svg = cont.querySelector('svg');
      if (!svg) return;
      var capa = svg.querySelector('.capa-hover'), cruz = svg.querySelector('.cruz');
      var puntos = Array.prototype.slice.call(svg.querySelectorAll('.punto'));
      var vb = svg.viewBox.baseVal;
      function mover(ev) {
        var rect = svg.getBoundingClientRect();
        if (!rect.width) return;
        var x = (ev.clientX - rect.left) * vb.width / rect.width;
        var mejor = null, dist = Infinity;
        puntos.forEach(function (p) {
          var dd = Math.abs(Number(p.getAttribute('data-x')) - x);
          if (dd < dist) { dist = dd; mejor = p; }
        });
        if (!mejor || !$scope.res) return;
        var s = $scope.res.serie[Number(mejor.getAttribute('data-i'))];
        if (!s) return;
        var px = Number(mejor.getAttribute('data-x'));
        cruz.setAttribute('x1', px);
        cruz.setAttribute('x2', px);
        cruz.setAttribute('visibility', 'visible');
        tip.innerHTML = '<div class="est-tip-fecha">' + E.esc(E.fechaTexto(s.fecha, true)) + '</div>' +
          '<div>' + E.esc(s.equipo + (s.ronda ? ' · ' + s.ronda : '')) + '</div>' +
          '<div><span class="est-punto-ley score"></span>score <b>' + E.esc(E.fmt(s.score)) + '</b> &nbsp;<span class="est-punto-ley raw"></span>raw <b>' + E.esc(E.fmt(s.raw)) + '</b></div>';
        tip.hidden = false;
        var contRect = cont.getBoundingClientRect();
        var izq = rect.left - contRect.left + cont.scrollLeft + px * rect.width / vb.width + 12;
        var max = cont.scrollLeft + cont.clientWidth - tip.offsetWidth - 4;
        if (izq > max) izq = Math.max(4, izq - tip.offsetWidth - 24);
        tip.style.left = Math.max(4, izq) + 'px';
        tip.style.top = '6px';
      }
      capa.addEventListener('pointermove', mover);
      capa.addEventListener('pointerdown', mover);
      capa.addEventListener('pointerleave', function (ev) {
        if (ev.pointerType !== 'mouse') return;
        cruz.setAttribute('visibility', 'hidden');
        tip.hidden = true;
      });
    }

    var esperaResize = null;
    angular.element($window).on('resize', function () {
      if (esperaResize) $timeout.cancel(esperaResize);
      esperaResize = $timeout(function () {
        var compacto = $window.innerWidth < 576;
        if (compacto !== $scope.vista.compacto && $scope.res) {
          $scope.vista.compacto = compacto;
          renderGraficos();
        }
      }, 200);
    });

    // ---------------------------------------------------------------- CSV
    $scope.exportar = function (que, formato) {
      if (!$scope.res) return;
      var texto = que === 'pasadas' ? E.csv.pasadas($scope.res, formato) : E.csv.corridas($scope.res, formato);
      var nombre = 'rcj-estadisticas-' + que + '-' + E.fechaTexto(Date.now()) + (formato === 'excel' ? '-excel' : '') + '.csv';
      $scope.ultimaExportacion = { que: que, formato: formato, nombre: nombre, filas: texto.split('\r\n').length - 2 };
      E.csv.descargar(texto, nombre);
    };

    $scope.cargar();
  }]);
})(window);

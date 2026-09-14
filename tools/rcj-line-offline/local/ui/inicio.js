/*
 * rcj-line-offline — área admin. Página de Inicio (index.html), NUEVA: no existe en el CMS.
 * Siembra los datos (RCJLocal.semillas), elige la competencia activa y ofrece accesos grandes
 * para tablet, la lista de corridas pendientes y la "corrida rápida de práctica".
 * Todos los datos pasan por las rutas /api/* del backend local, salvo el estado "terminado" de los
 * mapas, que la lista del CMS no trae y se lee (solo lectura) de RCJLocal.store.
 */
var app = angular.module('RCJInicio', ['ngTouch', 'ngAnimate', 'ui.bootstrap', 'pascalprecht.translate', 'ngCookies']);

app.controller('RCJInicioController', ['$scope', '$http', '$q', function ($scope, $http, $q) {
  'use strict';
  var UI = window.RCJLocalUI;
  var LIGA = 'Line';

  $scope.version = RCJLocal.version;
  $scope.estado = { cargando: true, error: '', creandoCompetencia: false, creandoCorrida: false };
  $scope.competencias = [];
  $scope.sel = { competencia: '', nombreNueva: '', mapa: '', equipo: '' };
  $scope.resumen = null;
  $scope.textoEstado = UI.textoEstado;

  $scope.url = function (pagina, extra) {
    return UI.url(pagina, Object.assign({ competition: $scope.sel.competencia }, extra || {}));
  };
  $scope.go = function (path) {
    window.location = UI.ruta(path);
  };
  $scope.etiquetaMapa = function (m) {
    return m.name + (m.finished ? '' : ' (sin terminar)');
  };

  function mostrarError(titulo) {
    return function (e) {
      swal(titulo, UI.mensajeError(e), 'error');
    };
  }

  function cargarCompetencias(preferida) {
    return $http.get('/api/competitions/').then(function (r) {
      $scope.competencias = r.data;
      var id = preferida || UI.competenciaActiva();
      var elegida = r.data.find(function (c) { return c._id === id; }) || r.data[0] || null;
      $scope.sel.competencia = elegida ? elegida._id : '';
      UI.setCompetenciaActiva($scope.sel.competencia);
      return cargarResumen();
    });
  }

  function cargarResumen() {
    var cid = $scope.sel.competencia;
    if (!cid) {
      $scope.resumen = null;
      return $q.resolve();
    }
    return $q.all({
      competencia: $http.get('/api/competitions/' + cid),
      mapas: $http.get('/api/competitions/' + cid + '/' + LIGA + '/maps'),
      equipos: $http.get('/api/competitions/' + cid + '/' + LIGA + '/teams'),
      corridas: $http.get('/api/runs/line/competition/' + cid),
      docsMapas: $q.when(RCJLocal.store.list('lineMaps', function (m) { return m.competition === cid; }))
    }).then(function (r) {
      if ($scope.sel.competencia !== cid) return; // cambió la selección mientras cargaba
      var docs = {};
      r.docsMapas.forEach(function (m) { docs[m._id] = m; });
      var mapas = r.mapas.data.map(function (m) {
        var d = docs[m._id] || {};
        return { _id: m._id, name: m.name, finished: !!d.finished, indexCount: d.indexCount };
      });
      var corridas = r.corridas.data.filter(function (run) { return !run.team || run.team.league == LIGA; });
      var pendientes = corridas.filter(function (run) { return run.status < 4; }).sort(function (a, b) {
        return (b.startTime || 0) - (a.startTime || 0);
      });
      $scope.resumen = {
        competencia: r.competencia.data,
        mapas: mapas,
        mapasTerminados: mapas.filter(function (m) { return m.finished; }).length,
        equipos: r.equipos.data,
        corridas: corridas,
        pendientes: pendientes
      };
      if (!mapas.some(function (m) { return m._id === $scope.sel.mapa && m.finished; })) {
        var terminado = mapas.find(function (m) { return m.finished; });
        $scope.sel.mapa = terminado ? terminado._id : '';
      }
      if (!r.equipos.data.some(function (e) { return e._id === $scope.sel.equipo; })) {
        $scope.sel.equipo = r.equipos.data.length ? r.equipos.data[0]._id : '';
      }
    });
  }

  $scope.cambiarCompetencia = function () {
    UI.setCompetenciaActiva($scope.sel.competencia);
    $scope.resumen = null;
    cargarResumen().catch(mostrarError('No se pudo cargar la competencia'));
  };

  $scope.crearCompetencia = function () {
    var nombre = ($scope.sel.nombreNueva || '').trim();
    if (!nombre) return;
    $scope.estado.creandoCompetencia = true;
    $http.post('/api/competitions', { name: nombre }).then(function (r) {
      $scope.sel.nombreNueva = '';
      return cargarCompetencias(r.data.id);
    }).catch(mostrarError('No se pudo crear la competencia')).finally(function () {
      $scope.estado.creandoCompetencia = false;
    });
  };

  $scope.irAPuntuar = function ($event) {
    if ($event) $event.preventDefault();
    var el = document.getElementById('puntuar');
    if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  $scope.puntuar = function (run) {
    window.location = UI.urlJuez(run._id, UI.rutaActual());
  };
  $scope.firmar = function (run) {
    window.location = RCJLocal.ruta('/line/sign/' + run._id + '?return=' + encodeURIComponent(UI.rutaActual()));
  };
  $scope.ver = function (run) {
    window.location = RCJLocal.ruta('/line/view/' + run._id + '?return=' + encodeURIComponent(UI.rutaActual()));
  };

  $scope.corridaRapida = function () {
    if (!$scope.sel.mapa || !$scope.sel.equipo) return;
    $scope.estado.creandoCorrida = true;
    $q.when(UI.crearCorrida({
      competition: $scope.sel.competencia,
      map: $scope.sel.mapa,
      team: $scope.sel.equipo
    })).then(function (res) {
      $scope.ultimaCorridaRapida = res;
      window.location = UI.urlJuez(res.id, UI.rutaActual());
    }).catch(mostrarError('No se pudo crear la corrida')).finally(function () {
      $scope.estado.creandoCorrida = false;
    });
  };

  // Refresco cuando otra pestaña guarda corridas (io() local sobre BroadcastChannel)
  try {
    var socket = io();
    socket.emit('subscribe', 'runs/line');
    socket.on('changed', function () {
      cargarResumen().catch(function () { /* se reintenta en el próximo cambio */ });
    });
  } catch (e) { /* sin io-shim */ }

  // Arranque: datos semilla (idempotente) y competencias
  $q.when(RCJLocal.semillas()).then(function (res) {
    $scope.semillas = res;
    return cargarCompetencias();
  }).catch(function (e) {
    $scope.estado.error = UI.mensajeError(e);
  }).finally(function () {
    $scope.estado.cargando = false;
    window.__inicioListo = true;
  });
}]);

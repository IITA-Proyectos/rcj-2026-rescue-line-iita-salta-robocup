/*
 * rcj-line-offline — área admin. Agregados locales de mapas.html (port de views/admin/maps.pug +
 * javascripts/admin/maps.js). La lista, la selección, el borrado y el modal de impresión son los del
 * CMS; acá se suma lo que en el CMS hacía el servidor o no existía:
 *   - Importar JSON del editor oficial (varios archivos) -> RCJLocal.ingestMap
 *   - Exportar JSON (RCJLocal.exportMap, mismo contenido que el Export del editor)
 *   - Duplicar, marcar terminado (mismo PUT que el Save del editor), crear corrida sobre el mapa,
 *     planilla del mapa (E8 scoresheet) y acceso a estadísticas.
 *   - RCJLocalUI.exportarMapas: reemplaza el window.open('/api/maps/line/export?...') del modal de
 *     impresión (sin servidor, se pide al backend local; si no hay generador masivo, mapa por mapa).
 */
(function () {
  'use strict';

  var UI = window.RCJLocalUI;
  var app = angular.module('MapAdmin');

  app.directive('rcjArchivo', UI.directivaArchivo);

  function escaparHTML(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /**
   * Cuerpo de las salidas E8 de un mapa, igual al que arma el editor en generateOutput
   * (admin/mapEditor/line_2026.js:827-872): el mapa con índices recalculados por el pathFinder
   * cliente (RCJLocal.exportMap lo hace si javascripts/pathFinder.js está cargado).
   */
  UI.cuerpoSalidaMapa = async function (mapId, cid, liga, extra) {
    var exp = await RCJLocal.exportMap(mapId);
    var doc = await UI.pedir('GET', '/api/maps/line/' + mapId);
    var comp = await UI.pedir('GET', '/api/competitions/' + cid);
    return Object.assign({
      name: exp.name,
      height: exp.height,
      width: exp.width,
      length: exp.length,
      tiles: exp.tiles,
      startTile: exp.startTile,
      startTile2: exp.startTile2,
      competitionName: comp.name,
      leagueName: liga,
      paperSize: 'A4',
      EvacuationAreaLoPIndex: doc.EvacuationAreaLoPIndex
    }, extra || {});
  };

  function avisarSalida(res) {
    swal(res.status === 501 ? 'Salida no disponible' : 'No se pudo generar la salida', res.mensaje || ('HTTP ' + res.status), res.status === 501 ? 'info' : 'error');
  }

  /** Reemplazo local del window.open / <a download> del modal de impresión de maps.js. */
  UI.exportarMapas = async function (url, ids, settings, cid, liga) {
    if (!ids || !ids.length) return;
    var res;
    if (settings.exportType === 'Maps' && settings.exportFormat === 'PNG') {
      for (var i = 0; i < ids.length; i++) {
        res = await UI.salidaApi('GET', '/api/maps/line/image/' + ids[i], undefined, { nombreDescarga: ids[i] + '.png', silencioso: true });
        if (!res.ok && res.status === 501) {
          var cuerpoPng = await UI.cuerpoSalidaMapa(ids[i], cid, liga, { paperSize: settings.paperSize });
          res = await UI.salidaApi('POST', '/api/maps/line/map-image-png', cuerpoPng, { nombreDescarga: ids[i] + '.png', silencioso: true });
        }
        if (!res.ok) { avisarSalida(res); return; }
      }
      return;
    }
    // 1) export masivo, como el CMS
    res = await UI.salidaApi('GET', url, undefined, { nombreDescarga: (settings.exportType === 'Scoresheets' ? 'scoresheets_' : 'maps_') + UI.fechaArchivo() + '.pdf', silencioso: true });
    if (res.ok) return;
    if (res.status !== 501) { avisarSalida(res); return; }
    // 2) sin generador masivo: una salida por mapa con las rutas E8 del editor
    var endpoint = settings.exportType === 'Scoresheets' ? 'scoresheet' : (settings.exportType === 'Maps' ? 'map-image-pdf' : null);
    if (!endpoint) { avisarSalida(res); return; }
    for (var j = 0; j < ids.length; j++) {
      var extra = { paperSize: settings.paperSize };
      if (endpoint === 'scoresheet') extra.rule = '2026';
      var cuerpo = await UI.cuerpoSalidaMapa(ids[j], cid, liga, extra);
      res = await UI.salidaApi('POST', '/api/maps/line/' + endpoint, cuerpo, { nombreDescarga: cuerpo.name + '.pdf', silencioso: true });
      if (!res.ok) { avisarSalida(res); return; }
    }
  };

  app.controller('MapasLocalController', ['$scope', '$http', '$q', '$uibModal', function ($scope, $http, $q, $uibModal) {
    var cid = competitionId;
    var liga = leagueId;

    $scope.local = { importando: false, resultados: null, detalles: {} };

    function mostrarError(titulo) {
      return function (e) { swal(titulo, UI.mensajeError(e), 'error'); };
    }
    function parar($event) {
      if ($event) { $event.stopPropagation(); $event.preventDefault(); }
    }
    function recargar() {
      if (typeof $scope.updateMapList === 'function') $scope.updateMapList();
    }
    function aviso(texto) {
      swal({ title: texto, type: 'success', timer: 1400, showConfirmButton: false });
    }

    // Detalles que la lista del CMS no trae (GET /api/competitions/:c/:l/maps solo da nombre y liga)
    function cargarDetalles() {
      return $q.all({
        mapas: $q.when(RCJLocal.store.list('lineMaps', function (m) { return m.competition === cid; })),
        corridas: $q.when(RCJLocal.store.list('lineRuns', function (r) { return r.competition === cid; }))
      }).then(function (r) {
        var det = {};
        r.mapas.forEach(function (m) {
          det[m._id] = {
            finished: !!m.finished,
            indexCount: m.indexCount,
            dimensiones: m.width + '×' + m.length + (m.height > 1 ? '×' + m.height : ''),
            corridas: 0,
            empezadas: 0
          };
        });
        r.corridas.forEach(function (run) {
          var d = det[run.map];
          if (!d) return;
          d.corridas++;
          if (run.started) d.empezadas++;
        });
        $scope.local.detalles = det;
      });
    }
    $scope.$watch('maps', function (maps) { if (maps) cargarDetalles(); });

    // ------------------------------------------------------------ importar
    $scope.importarArchivos = function (archivos) {
      if (!archivos || !archivos.length) return;
      $scope.local.importando = true;
      $scope.local.resultados = [];
      var resultados = [];
      var cadena = $q.resolve();
      archivos.forEach(function (archivo) {
        cadena = cadena.then(function () {
          return $q.when(UI.leerArchivoTexto(archivo)).then(function (texto) {
            var datos;
            try {
              datos = JSON.parse(texto);
            } catch (e) {
              throw new Error('No es un JSON válido (' + e.message + ')');
            }
            var lista = Array.isArray(datos) ? datos : [datos];
            var sub = $q.resolve();
            lista.forEach(function (mapa, i) {
              sub = sub.then(function () {
                if (!mapa || typeof mapa !== 'object' || !mapa.tiles || !mapa.tileSet) {
                  throw new Error('No parece un mapa del editor (faltan "tiles" o "tileSet")');
                }
                return $q.when(RCJLocal.ingestMap(mapa, { competition: cid, league: liga, renombrarSiExiste: true }))
                  .then(function (id) { return $http.get('/api/maps/line/' + id); })
                  .then(function (r) {
                    resultados.push({ archivo: archivo.name + (lista.length > 1 ? ' #' + (i + 1) : ''), ok: true, id: r.data._id, nombre: r.data.name, finished: !!r.data.finished });
                  });
              });
            });
            return sub;
          }).catch(function (e) {
            resultados.push({ archivo: archivo.name, ok: false, error: UI.mensajeError(e) });
          });
        });
      });
      cadena.finally(function () {
        $scope.local.importando = false;
        $scope.local.resultados = resultados;
        recargar();
        cargarDetalles();
      });
    };

    // ------------------------------------------------------------ exportar / duplicar
    $scope.exportarMapa = function (mapa, $event) {
      parar($event);
      $q.when(RCJLocal.exportMap(mapa._id)).then(function (obj) {
        // Mismo contenido que $scope.export del editor (line_2026.js:1012): JSON.stringify sin espacios, archivo <nombre>.json
        UI.descargar(obj.name + '.json', JSON.stringify(obj), 'text/json;charset=utf-8');
      }).catch(mostrarError('No se pudo exportar el mapa'));
    };

    $scope.duplicarMapa = function (mapa, $event) {
      parar($event);
      $q.when(RCJLocal.exportMap(mapa._id)).then(function (obj) {
        return RCJLocal.ingestMap(obj, { competition: cid, league: liga, nombre: obj.name + ' (copia)', renombrarSiExiste: true });
      }).then(function () {
        recargar();
        aviso('Mapa duplicado');
      }).catch(mostrarError('No se pudo duplicar el mapa'));
    };

    // ------------------------------------------------------------ terminado
    $scope.alternarTerminado = function (mapa, $event) {
      parar($event);
      var d = $scope.local.detalles[mapa._id];
      var nuevo = !(d && d.finished);
      $q.when(RCJLocal.exportMap(mapa._id)).then(function (exp) {
        // Mismo cuerpo que el Save del editor (admin/mapEditor/line_2026.js:933-947) con finished cambiado
        var cuerpo = {
          competition: cid,
          tileSet: exp.tileSet,
          name: exp.name,
          length: exp.length,
          height: exp.height,
          width: exp.width,
          duration: exp.duration,
          finished: nuevo,
          startTile: exp.startTile,
          startTile2: exp.startTile2,
          tiles: exp.tiles,
          victims: exp.victims,
          league: liga
        };
        return $http.put('/api/maps/line/' + mapa._id, cuerpo);
      }).then(function () {
        return cargarDetalles();
      }, mostrarError('No se pudo cambiar el estado del mapa'));
    };

    // ------------------------------------------------------------ crear corrida
    $scope.crearCorridaMapa = function (mapa, $event) {
      parar($event);
      var instancia = $uibModal.open({
        templateUrl: 'crearCorridaModal.html',
        controller: 'CrearCorridaModalController',
        size: 'md',
        resolve: {
          datos: function () {
            return { mapa: mapa, terminado: !!($scope.local.detalles[mapa._id] || {}).finished, competencia: cid, liga: liga };
          }
        }
      });
      instancia.result.then(function (res) {
        cargarDetalles();
        if (res.puntuar) {
          window.location = UI.urlJuez(res.id, UI.rutaActual());
        } else {
          aviso('Corrida creada');
        }
      }, function () { /* cancelado */ });
    };

    // ------------------------------------------------------------ planilla y estadísticas
    $scope.planillaMapa = function (mapa, $event) {
      parar($event);
      var ventana = null;
      try { ventana = window.open('', '_blank'); } catch (e) { ventana = null; }
      $q.when(UI.cuerpoSalidaMapa(mapa._id, cid, liga, { rule: '2026' })).then(function (cuerpo) {
        return UI.salidaApi('POST', '/api/maps/line/scoresheet', cuerpo, { tipo: 'application/pdf', ventana: ventana, silencioso: true });
      }).then(function (res) {
        if (res.ok) return;
        swal({
          title: 'Planilla no disponible',
          html: escaparHTML(res.mensaje) + '<br><br>La lista de corridas imprimible está en <a href="' +
            escaparHTML(UI.url('planillas.html', { competition: cid, league: liga })) + '">Planillas</a>.',
          type: 'info'
        });
      }, function (e) {
        if (ventana && !ventana.closed) ventana.close();
        mostrarError('No se pudo generar la planilla')(e);
      });
    };

    $scope.estadisticasMapa = function (mapa, $event) {
      parar($event);
      window.location = UI.url('estadisticas.html', { competition: cid, map: mapa._id });
    };
  }]);

  app.controller('CrearCorridaModalController', ['$scope', '$http', '$q', '$uibModalInstance', 'datos', function ($scope, $http, $q, $uibModalInstance, datos) {
    $scope.mapa = datos.mapa;
    $scope.terminado = datos.terminado;
    $scope.f = { team: null, round: null, field: null, normalizationGroup: '' };
    $scope.equipos = [];
    $scope.rondas = [];
    $scope.pistas = [];
    $scope.creando = false;
    $scope.error = '';

    $q.all({
      equipos: $http.get('/api/competitions/' + datos.competencia + '/' + datos.liga + '/teams'),
      rondas: $http.get('/api/competitions/' + datos.competencia + '/rounds'),
      pistas: $http.get('/api/competitions/' + datos.competencia + '/fields')
    }).then(function (r) {
      $scope.equipos = r.equipos.data;
      $scope.rondas = r.rondas.data;
      $scope.pistas = r.pistas.data;
      if ($scope.equipos.length) $scope.f.team = $scope.equipos[0]._id;
    });

    $scope.crear = function (puntuar) {
      $scope.creando = true;
      $scope.error = '';
      var ronda = $scope.rondas.find(function (r) { return r._id === $scope.f.round; });
      var grupo = ($scope.f.normalizationGroup || '').trim() || (ronda ? ronda.name : undefined);
      $q.when(UI.crearCorrida({
        competition: datos.competencia,
        map: datos.mapa._id,
        team: $scope.f.team,
        round: $scope.f.round || undefined,
        field: $scope.f.field || undefined,
        normalizationGroup: grupo
      })).then(function (res) {
        $uibModalInstance.close({ id: res.id, puntuar: puntuar });
      }, function (e) {
        $scope.error = UI.mensajeError(e);
      }).finally(function () {
        $scope.creando = false;
      });
    };
    $scope.cancelar = function () {
      $uibModalInstance.dismiss('cancel');
    };
  }]);
})();

/*
 * rcj-line-offline — área admin. Página de Configuración (configuracion.html), NUEVA: no existe en el CMS.
 * Flags de ESPEC §2 (RCJLocal.flags / RCJLocal.setFlag), idioma, respaldo completo
 * (RCJLocal.backup.exportar / importar), borrado total con doble confirmación, estado del
 * almacenamiento (navigator.storage) y versión/créditos.
 */
var app = angular.module('RCJConfiguracion', ['ngTouch', 'ngAnimate', 'ui.bootstrap', 'pascalprecht.translate', 'ngCookies']);

app.directive('rcjArchivo', window.RCJLocalUI.directivaArchivo);

app.controller('RCJConfiguracionController', ['$scope', '$q', '$translate', function ($scope, $q, $translate) {
  'use strict';
  var UI = window.RCJLocalUI;

  $scope.version = RCJLocal.version;

  // ------------------------------------------------------------------ flags (ESPEC §2)
  $scope.FLAGS = [
    {
      nombre: 'corregirBugsVisuales', decision: 'D4', titulo: 'Corregir errores visuales del CMS',
      desc: 'Corrige la etiqueta x1.4 de la tabla de rescate del juez, la numeración j*4 del desglose de la firma y la vista, el aviso cuando el servidor responde 202, los íconos de Font Awesome 4 que no se ven y la fila «Regla» vacía. Apagado, las páginas se ven igual que la tablet oficial.'
    },
    {
      nombre: 'tactil', decision: 'D5', titulo: 'Gestos táctiles en el editor',
      desc: 'Arrastrar y soltar baldosas con el dedo (polyfill), pulsación larga como clic derecho y modo selección. Llama a los mismos handlers del editor.'
    },
    {
      nombre: 'persistirTimer', decision: 'D5', titulo: 'El cronómetro del juez sobrevive a una recarga',
      desc: 'Si la página del juez se recarga o se cierra por accidente, el tiempo sigue desde donde estaba. En el CMS se pierde.'
    },
    {
      nombre: 'audioResume', decision: 'D5', titulo: 'Activar el audio con el primer toque',
      desc: 'Reanuda el audio del navegador (AudioContext.resume) en el primer toque, para que se oigan los sonidos del juez en tablets que bloquean la reproducción automática.'
    },
    {
      nombre: 'fotosOpcionales', decision: 'D5', titulo: 'Pre-chequeo sin fotos',
      desc: 'El pre-chequeo del juez funciona aunque el equipo no tenga cargadas las fotos del equipo y del robot.'
    },
    {
      nombre: 'soloFirmaCapitan', decision: 'D6', titulo: 'Solo firma del capitán',
      desc: 'La firma exige únicamente la del capitán (reglamento 8.1.3). Apagado, pide las 3 firmas como el CMS (capitán, árbitro y co-árbitro).'
    },
    {
      nombre: 'recorridoTolerante', decision: 'Entrenamiento', titulo: 'Recorrido tolerante (unir empalmes mal dibujados)',
      desc: 'Si en el mapa la línea apunta a una celda vacía (por ejemplo una recta donde iba una curva), al guardar o importar el mapa la app sigue por la baldosa vecina para que todo el recorrido se pueda puntuar, y el juez avisa dónde unió. Apagado, se comporta como el CMS: el recorrido se corta y esas baldosas no se pueden marcar. Después de cambiarlo, volvé a guardar el mapa.'
    },
    {
      nombre: 'mostrarPorcentaje', decision: 'Entrenamiento', titulo: 'Mostrar "% del máximo" del mapa',
      desc: 'En el juez, la firma y la vista aparece qué porcentaje del puntaje máximo posible del mapa lleva la corrida (el máximo es el de la calculadora del editor: todo logrado, sin LoPs, víctimas en orden y exit bonus). Tocándolo se ve el detalle del puntaje final y del recorrido. No existe en el CMS.'
    }
  ];
  $scope.defectos = RCJLocal.flagsPorDefecto || {};
  $scope.flags = angular.copy(RCJLocal.flags);
  $scope.cambiarFlag = function (f) {
    RCJLocal.setFlag(f.nombre, !!$scope.flags[f.nombre]);
  };
  $scope.flagsPorDefecto = function () {
    return $scope.FLAGS.every(function (f) { return !!$scope.flags[f.nombre] === !!$scope.defectos[f.nombre]; });
  };
  $scope.restablecerFlags = function () {
    $scope.FLAGS.forEach(function (f) {
      $scope.flags[f.nombre] = !!$scope.defectos[f.nombre];
      RCJLocal.setFlag(f.nombre, $scope.flags[f.nombre]);
    });
  };

  // ------------------------------------------------------------------ idioma
  $scope.IDIOMAS = [
    { id: 'es', nombre: 'Español' },
    { id: 'en', nombre: 'English' },
    { id: 'ja', nombre: '日本語' }
  ];
  $scope.idioma = { actual: $translate.proposedLanguage() || $translate.use() || 'es' };
  $scope.cambiarIdioma = function () {
    $translate.use($scope.idioma.actual).then(function () { window.location.reload(); });
  };

  // ------------------------------------------------------------------ almacenamiento
  var NOMBRES_COLECCIONES = {
    competitions: 'Competencias', rounds: 'Rondas', teams: 'Equipos', fields: 'Pistas',
    lineMaps: 'Mapas', lineRuns: 'Corridas', tileSets: 'Sets de baldosas', meta: 'Metadatos'
  };
  $scope.almacen = { soportado: !!(navigator.storage), persistente: null, uso: null, cuota: null, conteos: [], enMemoria: false };
  $scope.bytes = UI.bytesLegibles;
  $scope.porcentajeUso = function () {
    var a = $scope.almacen;
    if (!a.cuota) return 0;
    return Math.min(100, Math.max(0.5, (a.uso / a.cuota) * 100));
  };
  function actualizarAlmacen() {
    var a = $scope.almacen;
    if (navigator.storage && navigator.storage.persisted) {
      $q.when(navigator.storage.persisted()).then(function (p) { a.persistente = p; });
    }
    if (navigator.storage && navigator.storage.estimate) {
      $q.when(navigator.storage.estimate()).then(function (e) { a.uso = e.usage; a.cuota = e.quota; });
    }
    return $q.all(RCJLocal.store.colecciones.map(function (c) {
      return $q.when(RCJLocal.store.count(c)).then(function (n) { return { id: c, nombre: NOMBRES_COLECCIONES[c] || c, cantidad: n }; });
    })).then(function (conteos) {
      a.conteos = conteos;
      a.enMemoria = RCJLocal.store.enMemoria();
    });
  }
  $scope.pedirPersistencia = function () {
    if (!navigator.storage || !navigator.storage.persist) return;
    $q.when(navigator.storage.persist()).then(function (ok) {
      $scope.almacen.persistente = ok;
      if (!ok) {
        swal('No concedido', 'El navegador no concedió el almacenamiento persistente. Suele concederlo si la app se instala o se agrega a la pantalla de inicio. Exportá respaldos seguido.', 'info');
      }
    });
  };

  // ------------------------------------------------------------------ respaldo
  $scope.respaldo = { modo: 'reemplazar', ocupado: false, ultimo: null, elegido: null, error: '' };

  function contar(colecciones) {
    return Object.keys(colecciones || {}).map(function (c) {
      return { id: c, nombre: NOMBRES_COLECCIONES[c] || c, cantidad: Array.isArray(colecciones[c]) ? colecciones[c].length : 0 };
    });
  }

  $scope.exportarRespaldo = function () {
    $scope.respaldo.ocupado = true;
    $q.when(RCJLocal.backup.exportar()).then(function (obj) {
      var texto = JSON.stringify(obj);
      var nombre = 'rcj-line-offline-respaldo_' + UI.fechaArchivo() + '.json';
      UI.descargar(nombre, texto, 'application/json');
      $scope.respaldo.ultimo = { nombre: nombre, bytes: new Blob([texto]).size, conteos: contar(obj.colecciones), fecha: obj.fecha };
    }).catch(function (e) {
      swal('No se pudo exportar el respaldo', UI.mensajeError(e), 'error');
    }).finally(function () {
      $scope.respaldo.ocupado = false;
    });
  };

  $scope.elegirRespaldo = function (archivos) {
    $scope.respaldo.error = '';
    $scope.respaldo.elegido = null;
    if (!archivos || !archivos.length) return;
    var archivo = archivos[0];
    $q.when(UI.leerArchivoTexto(archivo)).then(function (texto) {
      var obj = JSON.parse(texto);
      if (!obj || obj.formato !== 'rcj-line-offline/respaldo' || !obj.colecciones) {
        throw new Error('El archivo no es un respaldo de rcj-line-offline.');
      }
      $scope.respaldo.elegido = { nombre: archivo.name, datos: obj, fecha: obj.fecha, app: obj.app, conteos: contar(obj.colecciones) };
    }).catch(function (e) {
      $scope.respaldo.error = UI.mensajeError(e);
    });
  };

  $scope.importarRespaldo = function () {
    var elegido = $scope.respaldo.elegido;
    if (!elegido) return;
    var modo = $scope.respaldo.modo;
    var texto = modo === 'reemplazar'
      ? 'Se BORRAN todos los datos actuales de este navegador y se reemplazan por los del respaldo.'
      : 'Se agregan los documentos del respaldo; los que tengan el mismo id se sobrescriben.';
    swal({
      title: modo === 'reemplazar' ? '¿Reemplazar todos los datos?' : '¿Fusionar el respaldo?',
      text: texto,
      type: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Importar',
      cancelButtonText: 'Cancelar',
      confirmButtonColor: modo === 'reemplazar' ? '#ef4444' : '#3b82f6'
    }).then(function (r) {
      if (!r.value) return;
      $scope.$applyAsync(function () { $scope.respaldo.ocupado = true; });
      return $q.when(RCJLocal.backup.importar(elegido.datos, { modo: modo })).then(function (res) {
        $scope.respaldo.resultado = res;
        $scope.respaldo.elegido = null;
        return actualizarAlmacen().then(function () {
          swal('Respaldo importado', 'Modo: ' + res.modo + '. Documentos importados: ' +
            Object.keys(res.cuenta).reduce(function (s, k) { return s + res.cuenta[k]; }, 0) + '.', 'success');
        });
      }).catch(function (e) {
        swal('No se pudo importar el respaldo', UI.mensajeError(e), 'error');
      }).finally(function () {
        $scope.respaldo.ocupado = false;
      });
    });
  };

  // ------------------------------------------------------------------ borrar todo (doble confirmación)
  $scope.borrarTodo = function () {
    swal({
      title: '¿Borrar todos los datos?',
      text: 'Se borran competencias, mapas, equipos, rondas, pistas, corridas y sets de baldosas guardados en este navegador. No se puede deshacer: conviene exportar un respaldo antes.',
      type: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Continuar',
      cancelButtonText: 'Cancelar',
      confirmButtonColor: '#ef4444'
    }).then(function (r1) {
      if (!r1.value) return null;
      return swal({
        title: 'Confirmación final',
        text: 'Escribí BORRAR para confirmar.',
        type: 'warning',
        input: 'text',
        inputPlaceholder: 'BORRAR',
        showCancelButton: true,
        confirmButtonText: 'Borrar todo',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#ef4444',
        inputValidator: function (v) { return v !== 'BORRAR' && 'Tenés que escribir BORRAR'; }
      });
    }).then(function (r2) {
      if (!r2 || !r2.value) return;
      var cadena = Promise.resolve();
      RCJLocal.store.colecciones.forEach(function (c) {
        cadena = cadena.then(function () { return RCJLocal.store.clear(c); });
      });
      return cadena.then(function () {
        UI.setCompetenciaActiva('');
        window.__datosBorrados = true;
        return swal('Datos borrados', 'Al volver al Inicio se crean de nuevo los datos semilla.', 'success');
      }).then(function () {
        window.location = UI.url('index.html');
      });
    }).catch(function (e) {
      swal('No se pudieron borrar los datos', UI.mensajeError(e), 'error');
    });
  };

  actualizarAlmacen().finally(function () { window.__configListo = true; });
}]);

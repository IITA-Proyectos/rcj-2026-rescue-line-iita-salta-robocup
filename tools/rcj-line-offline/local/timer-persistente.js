/*
 * rcj-line-offline — área juez. Desvío D5 `persistirTimer` (08 §5.8 desvío 5; default true).
 *
 * En el CMS el cronómetro del juez vive solo en memoria: recargar la página con el reloj corriendo
 * lo detiene y el tiempo vuelve al último valor guardado en el servidor (02 §5.2). Con el flag activo,
 * este archivo guarda en localStorage (clave `rcjJuezTimer:<runId>`) el estado del reloj MIENTRAS
 * CORRE y, al recargar, lo reanuda desde donde iba.
 *
 * No toca javascripts/judge/line_2026.js: observa el scope de ddController y, para reanudar, usa el
 * mismo handler que el botón Start (`toggleTime`), que arranca `tick` y manda `{status:2}` como
 * siempre. Después corre `startUnixTime` hacia atrás lo necesario para que `tick` calcule
 * `time = prevTime + (ahora - startUnixTime)` = tiempo que llevaba el reloj.
 *
 * Con el reloj detenido no se guarda nada (se borra la clave): en ese estado el juez ya mandó el
 * tiempo al backend (Stop, Reset, exit bonus y fin de tiempo llaman a saveEverything), así que la
 * recarga se comporta igual que el original.
 */
(function () {
  'use strict';

  var PREFIJO = 'rcjJuezTimer:';
  // Un estado guardado hace más de 15 min no se reanuda (una corrida dura como mucho 8 min): evita
  // que un reloj abandonado dispare "Time Up!" y pise el tiempo guardado de una corrida terminada.
  var EDAD_MAXIMA_MS = 15 * 60 * 1000;

  function activo() {
    try { return !!(window.RCJLocal && window.RCJLocal.flags && window.RCJLocal.flags.persistirTimer); } catch (e) { return false; }
  }
  function leer(clave) {
    try {
      var txt = window.localStorage.getItem(clave);
      return txt ? JSON.parse(txt) : null;
    } catch (e) {
      return null;
    }
  }
  function escribir(clave, obj) {
    try { window.localStorage.setItem(clave, JSON.stringify(obj)); } catch (e) { /* sin almacenamiento: no se persiste */ }
  }
  function borrar(clave) {
    try { window.localStorage.removeItem(clave); } catch (e) { /* nada */ }
  }

  function valido(g, ahora) {
    return g && g.startedTime === true && isFinite(g.prev) && isFinite(g.startUnixTime) && isFinite(g.guardadoEn) &&
      g.startUnixTime <= ahora && ahora - g.guardadoEn >= 0 && ahora - g.guardadoEn <= EDAD_MAXIMA_MS;
  }

  function reanudar(scope, g) {
    var ahora = Date.now();
    var objetivo = g.prev + (ahora - g.startUnixTime); // tiempo que marcaría el reloj si no se hubiera recargado
    var base = scope.time;                            // = prevTime del controlador, recién leído del backend
    scope.toggleTime();                               // mismo handler que el botón Start
    scope.startUnixTime = ahora - (objetivo - base);
    console.log('[rcj-line-offline] cronómetro reanudado tras recargar: ' + Math.floor(objetivo / 1000) + ' s');
  }

  function instalar(scope) {
    var clave = PREFIJO + scope.runId;
    var guardado = leer(clave);

    // Esperar a que loadNewRun termine: $scope.duration se define al recibir el mapa, y para entonces
    // $scope.time ya tiene el tiempo del backend.
    var quitarEspera = scope.$watch('duration', function (duracion) {
      if (duracion === undefined) return;
      quitarEspera();

      if (guardado) {
        if (valido(guardado, Date.now()) && !scope.startedTime) reanudar(scope, guardado);
        else borrar(clave);
      }

      var ultimo = null;
      scope.$watchGroup(['startedTime', 'startUnixTime', 'time'], function () {
        if (!scope.startedTime) {
          ultimo = null;
          borrar(clave);
          return;
        }
        var prev;
        if (!ultimo || ultimo.startUnixTime !== scope.startUnixTime) {
          // Recién arrancado (toggleTime o reanudar): todavía no corrió tick, time == prevTime.
          prev = scope.time;
        } else {
          // Tick: time = prevTime + (ahora - startUnixTime) con prevTime constante mientras corre. Se conserva
          // el valor tomado al arrancar (recalcularlo con otro Date.now() lo corría 1-2 ms).
          prev = ultimo.prev;
        }
        ultimo = { startUnixTime: scope.startUnixTime, prev: prev };
        escribir(clave, { runId: scope.runId, startedTime: true, startUnixTime: scope.startUnixTime, prev: prev, time: scope.time, guardadoEn: Date.now() });
      });
    });
  }

  if (!window.angular) return;
  angular.module('ddApp').run(['$timeout', function ($timeout) {
    if (!activo()) return;
    // Los bloques run corren antes de compilar el DOM: esperar a que exista el scope del controlador.
    $timeout(function () {
      var scope = angular.element(document.body).scope();
      if (!scope || typeof scope.toggleTime !== 'function' || !scope.runId) return;
      instalar(scope);
    }, 0);
  }]);
})();

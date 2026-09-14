/*
 * rcj-line-offline — avisos del recorrido en el juez (desvío declarado, cambios/aviso-recorrido.md).
 * No cambia el puntaje ni el comportamiento del juez.
 * - Amarillo: hay baldosas con puntos sin numerar (el juez oficial las ignora en silencio).
 * - Azul: el mapa se unió con el recorrido tolerante (flag recorridoTolerante); dice dónde.
 */
(function () {
  'use strict';

  var EVAC_IDS = ['58cfd6549792e9313b1610e1', '58cfd6549792e9313b1610e2', '58cfd6549792e9313b1610e3'];

  function puntuable(t) {
    var it = t.items || {};
    var tt = t.tileType || {};
    return it.obstacles > 0 || it.speedbumps > 0 || tt.gaps > 0 || tt.intersections > 0 ||
      tt.seesaw > 0 || !!it.rampPoints;
  }

  function celda(x, y, z) {
    return 'columna ' + (x + 1) + ', fila ' + (y + 1) + (z ? ', piso ' + z : '');
  }

  function caja(id, fondo, borde, texto, titulo, lineas) {
    if (document.getElementById(id)) return;
    var d = document.createElement('div');
    d.id = id;
    d.setAttribute('role', 'alert');
    d.style.cssText = 'position:fixed;left:8px;right:8px;top:64px;z-index:100000;background:' + fondo + ';color:' + texto +
      ';border:2px solid ' + borde + ';border-radius:8px;padding:10px 12px;font:14px/1.4 system-ui,sans-serif;' +
      'box-shadow:0 4px 12px rgba(0,0,0,.25)';
    var t = document.createElement('strong');
    t.textContent = titulo;
    d.appendChild(t);
    lineas.forEach(function (l) {
      var p = document.createElement('div');
      p.style.marginTop = '4px';
      p.textContent = l;
      d.appendChild(p);
    });
    var cerrar = document.createElement('button');
    cerrar.type = 'button';
    cerrar.textContent = 'Entendido';
    cerrar.style.cssText = 'margin-top:8px;background:' + borde + ';color:#fff;border:0;border-radius:6px;padding:6px 14px;font-weight:600';
    cerrar.addEventListener('click', function () { d.parentNode.removeChild(d); });
    d.appendChild(cerrar);
    document.body.appendChild(d);
  }

  function sinNumero(tiles, soloPuntuables) {
    return tiles.filter(function (t) {
      if (!t || !t.tileType || !t.tileType.paths || EVAC_IDS.indexOf(t.tileType._id) >= 0) return false;
      if (t.index && t.index.length) return false;
      return soloPuntuables ? puntuable(t) : true;
    });
  }

  function revisar() {
    var el = document.querySelector('[ng-controller]');
    if (!window.angular || !el) return false;
    var s = window.angular.element(el).scope();
    if (!s || !s.mtiles || !Object.keys(s.mtiles).length) return false;

    var R = window.RCJLocal || {};
    var tolerante = !(R.flags && R.flags.recorridoTolerante === false);
    var tiles = Object.keys(s.mtiles).map(function (k) { return s.mtiles[k]; });

    var fuera = sinNumero(tiles, true);
    if (fuera.length) {
      var lineas = [fuera.map(function (t) { return celda(t.x, t.y, t.z); }).join(' · '),
        'Coordenadas del editor (columna y fila desde arriba a la izquierda). Revisá que la línea sea continua desde el ' +
        'inicio y desde el reinicio después de la zona de evacuación.'];
      if (tolerante) {
        lineas.push('Con "Recorrido tolerante" activado alcanza con tocar Guardar en el editor (o volver a importar el mapa) ' +
          'para que la app una los empalmes y se puedan puntuar. Después creá una corrida nueva.');
      }
      caja('rcj-aviso-recorrido', '#fef3c7', '#f59e0b', '#78350f', 'Recorrido cortado: ' + fuera.length +
        (fuera.length === 1 ? ' baldosa' : ' baldosas') + ' con puntos no forman parte del recorrido y no se pueden marcar.', lineas);
      return true;
    }

    // ¿El mapa quedó completo gracias al recorrido tolerante? Se detecta repitiendo el recorrido oficial sobre una copia.
    if (tolerante && R.PFs && R.PFtolerante && s.startTile && s.startTile.x >= 0) {
      try {
        var copia = function () {
          return {
            startTile: JSON.parse(JSON.stringify(s.startTile)),
            startTile2: JSON.parse(JSON.stringify(s.startTile2 || { x: -1, y: -1, z: -1 })),
            tiles: tiles.map(function (t) { return JSON.parse(JSON.stringify(t)); })
          };
        };
        var oficial = copia();
        R.PFs.findPath(oficial);
        if (sinNumero(oficial.tiles, false).length) {
          var unida = copia();
          var uniones = R.PFtolerante.findPath(unida);
          if (uniones.length) {
            caja('rcj-aviso-union', '#dbeafe', '#3b82f6', '#1e3a8a', 'Recorrido unido automáticamente (' + uniones.length +
              (uniones.length === 1 ? ' empalme' : ' empalmes') + ')',
              [uniones.map(function (u) { return celda(u.desde.x, u.desde.y, u.desde.z) + ' → ' + celda(u.hacia.x, u.hacia.y, u.hacia.z); }).join(' · '),
                'En el dibujo la línea no empalma ahí; la app siguió por la baldosa vecina para que se pueda puntuar. ' +
                'Se desactiva en Configuración ("Recorrido tolerante").']);
          }
        }
      } catch (e) {
        console.warn('[aviso-recorrido] no se pudo verificar el recorrido tolerante:', e);
      }
    }
    return true;
  }

  var intentos = 0;
  var timer = setInterval(function () {
    intentos++;
    if (revisar() || intentos > 120) clearInterval(timer);
  }, 500);
})();

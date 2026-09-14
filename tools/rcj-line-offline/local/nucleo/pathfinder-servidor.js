/*
 * rcj-line-offline — área backend.
 * PFs: helper/pathFinder.js del CMS (robocup-junior/rcj-rescue-cms, commit d805502) copiado VERBATIM.
 * Único agregado: este envoltorio IIFE (module/exports/require locales) para no pisar las funciones
 * globales del pathFinder.js del cliente (traverse, exitDir, nextCoord, ...), y la exportación a
 * window.RCJLocal.PFs. Sin tope de profundidad (ver cambios/backend.md).
 */
(function () {
  var module = { exports: {} };
  var exports = module.exports;
  function require() { return { mainLogger: console }; }

// ===== INICIO VERBATIM helper/pathFinder.js (rcj-rescue-cms d805502) =====
const logger = require('../config/logger').mainLogger;

module.exports.findPath = function (map) {
  const tiles = [];
  for (let i = 0; i < map.tiles.length; i++) {
    const tile = map.tiles[i];
    tile.index = [];
    tile.next = [];
    tile.next_dir = [];
    tiles[`${tile.x},${tile.y},${tile.z}`] = tile;
  }

  const startTile =
    tiles[`${map.startTile.x},${map.startTile.y},${map.startTile.z}`];

  let startDir = '';
  const startPaths = startTile.tileType.paths;
  Object.keys(startPaths).forEach(function (dir, index) {
    const nextTile =
      tiles[nextCoord(startTile, rotateDir(dir, startTile.rot))];
    if (nextTile !== undefined) {
      startDir = rotateDir(dir, startTile.rot);
    }
  });

  traverse(startTile, startDir, tiles, map, 0, 0, false);
};

function evacTile(tile) {
  return (
    tile.tileType._id == '58cfd6549792e9313b1610e1' ||
    tile.tileType._id == '58cfd6549792e9313b1610e2' ||
    tile.tileType._id == '58cfd6549792e9313b1610e3'
  );
}

/**
 *
 * @param curTile
 * @param entryDir {
 * @param tiles
 * @param map
 * @param index {Number}
 */
function traverse(curTile, entryDir, tiles, map, index, chpCount, restartFlag) {
  if (curTile.checkPoint) chpCount++;
  let next_Coord = nextCoord(curTile, entryDir);
  curTile.index.push(index);
  map.indexCount = index + 1;
  const nextTile = tiles[next_Coord];

  if (curTile.tileType._id == '58cfd6549792e9313b1610e0') {
    return;
  }

  curTile.next_dir.push(exitDir(curTile, entryDir));
  if (nextTile === undefined || evacTile(nextTile)) {
    if (nextTile) {
      nextTile.evacEntrance = dir2num(flipDir(exitDir(curTile, entryDir)));
    }
    const startTile2 =
      tiles[`${map.startTile2.x},${map.startTile2.y},${map.startTile2.z}`];
    if (!startTile2 || restartFlag) {
      map.EvacuationAreaLoPIndex = chpCount;
      return;
    }
    curTile.next.push(
      `${map.startTile2.x},${map.startTile2.y},${map.startTile2.z}`
    );
    

    let startDir2 = '';
    const startPaths2 = startTile2.tileType.paths;

    for (const [key, value] of Object.entries(startPaths2)) {
      if (key == '$init') continue;
      if (!value) continue;

      const entryDir2 = rotateDir(key, startTile2.rot);
      const fromTile = tiles[fromCoord(startTile2, entryDir2)];
      if (fromTile !== undefined) {
        if (evacTile(fromTile)) {
          fromTile.evacExit = dir2num(flipDir(entryDir2));
          startDir2 = entryDir2;

          break;
        }
      }
    }
    restartFlag = true;
    map.EvacuationAreaLoPIndex = chpCount;

    traverse(
      startTile2,
      startDir2,
      tiles,
      map,
      index + 1,
      chpCount,
      restartFlag
    );
    return;
  }
  curTile.next.push(next_Coord);

  traverse(
    nextTile,
    flipDir(exitDir(curTile, entryDir)),
    tiles,
    map,
    index + 1,
    chpCount,
    restartFlag
  );
}

function exitDir(curTile, entryDir) {
  const dir = rotateDir(entryDir, -curTile.rot);
  return rotateDir(curTile.tileType.paths[dir], curTile.rot);
}

function nextCoord(curTile, entryDir) {
  const exit = exitDir(curTile, entryDir);
  let coord;
  switch (exit) {
    case 'top':
      coord = `${curTile.x},${curTile.y - 1}`;
      break;
    case 'right':
      coord = `${curTile.x + 1},${curTile.y}`;
      break;
    case 'bottom':
      coord = `${curTile.x},${curTile.y + 1}`;
      break;
    case 'left':
      coord = `${curTile.x - 1},${curTile.y}`;
      break;
  }

  if (curTile.levelUp !== undefined && exit == curTile.levelUp) {
    coord += `,${curTile.z + 1}`;
  } else if (curTile.levelDown !== undefined && exit == curTile.levelDown) {
    coord += `,${curTile.z - 1}`;
  } else {
    coord += `,${curTile.z}`;
  }

  return coord;
}

function fromCoord(curTile, fromDir) {
  let coord;
  switch (fromDir) {
    case 'top':
      coord = `${curTile.x},${curTile.y - 1}`;
      break;
    case 'right':
      coord = `${curTile.x + 1},${curTile.y}`;
      break;
    case 'bottom':
      coord = `${curTile.x},${curTile.y + 1}`;
      break;
    case 'left':
      coord = `${curTile.x - 1},${curTile.y}`;
      break;
  }
  coord += `,${curTile.z}`;
  return coord;
}

function rotateDir(dir, rot) {
  switch (rot) {
    case 0:
      return dir;

    case -270:
    case 90:
      switch (dir) {
        case 'top':
          return 'right';
        case 'right':
          return 'bottom';
        case 'bottom':
          return 'left';
        case 'left':
          return 'top';
      }

    case -180:
    case 180:
      return flipDir(dir);

    case -90:
    case 270:
      switch (dir) {
        case 'top':
          return 'left';
        case 'right':
          return 'top';
        case 'bottom':
          return 'right';
        case 'left':
          return 'bottom';
      }
  }
}

function flipDir(dir) {
  switch (dir) {
    case 'top':
      return 'bottom';
    case 'right':
      return 'left';
    case 'bottom':
      return 'top';
    case 'left':
      return 'right';
  }
}

function dir2num(dir) {
  switch (dir) {
    case 'top':
      return 0;
    case 'right':
      return 90;
    case 'bottom':
      return 180;
    case 'left':
      return 270;
  }
}
// ===== FIN VERBATIM helper/pathFinder.js =====

  // ===== AGREGADO rcj-line-offline (NO es del CMS): recorrido tolerante =====
  // Desvío declarado (cambios/aviso-recorrido.md), flag RCJLocal.flags.recorridoTolerante.
  // Igual que traverse(), salvo un caso: cuando la línea apunta a una celda VACÍA, antes de tratarlo
  // como entrada a la evacuación busca una baldosa vecina todavía no recorrida que tenga entrada desde
  // ese lado y sigue por ahí (une un empalme mal dibujado). No toca el código verbatim de arriba.
  const LADOS = ['top', 'right', 'bottom', 'left'];

  function vecinoQueEmpalma(curTile, entryDir, tiles) {
    for (const lado of LADOS) {
      if (lado === entryDir) continue; // por ahí entró el robot
      const vecino = tiles[fromCoord(curTile, lado)];
      if (!vecino || !vecino.tileType || !vecino.tileType.paths || evacTile(vecino)) continue;
      if (vecino.index.length) continue; // solo baldosas todavía no recorridas: no crea lazos
      const entrada = flipDir(lado);
      if (vecino.tileType.paths[rotateDir(entrada, -vecino.rot)] === undefined) continue;
      return { tile: vecino, lado: lado, entrada: entrada };
    }
    return null;
  }

  function traverseTolerante(curTile, entryDir, tiles, map, index, chpCount, restartFlag, uniones) {
    if (curTile.checkPoint) chpCount++;
    const next_Coord = nextCoord(curTile, entryDir);
    curTile.index.push(index);
    map.indexCount = index + 1;
    const nextTile = tiles[next_Coord];

    if (curTile.tileType._id == '58cfd6549792e9313b1610e0') return;

    curTile.next_dir.push(exitDir(curTile, entryDir));

    if (nextTile === undefined) {
      const v = vecinoQueEmpalma(curTile, entryDir, tiles);
      if (v) {
        curTile.next_dir[curTile.next_dir.length - 1] = v.lado;
        curTile.next.push(`${v.tile.x},${v.tile.y},${v.tile.z}`);
        uniones.push({
          desde: { x: curTile.x, y: curTile.y, z: curTile.z },
          hacia: { x: v.tile.x, y: v.tile.y, z: v.tile.z }
        });
        traverseTolerante(v.tile, v.entrada, tiles, map, index + 1, chpCount, restartFlag, uniones);
        return;
      }
    }

    if (nextTile === undefined || evacTile(nextTile)) {
      if (nextTile) nextTile.evacEntrance = dir2num(flipDir(exitDir(curTile, entryDir)));
      const startTile2 = tiles[`${map.startTile2.x},${map.startTile2.y},${map.startTile2.z}`];
      if (!startTile2 || restartFlag) {
        map.EvacuationAreaLoPIndex = chpCount;
        return;
      }
      curTile.next.push(`${map.startTile2.x},${map.startTile2.y},${map.startTile2.z}`);
      let startDir2 = '';
      for (const [key, value] of Object.entries(startTile2.tileType.paths)) {
        if (key == '$init') continue;
        if (!value) continue;
        const entryDir2 = rotateDir(key, startTile2.rot);
        const fromTile = tiles[fromCoord(startTile2, entryDir2)];
        if (fromTile !== undefined && evacTile(fromTile)) {
          fromTile.evacExit = dir2num(flipDir(entryDir2));
          startDir2 = entryDir2;
          break;
        }
      }
      map.EvacuationAreaLoPIndex = chpCount;
      traverseTolerante(startTile2, startDir2, tiles, map, index + 1, chpCount, true, uniones);
      return;
    }
    curTile.next.push(next_Coord);
    traverseTolerante(nextTile, flipDir(exitDir(curTile, entryDir)), tiles, map, index + 1, chpCount, restartFlag, uniones);
  }

  // Devuelve la lista de uniones hechas ([] si no hizo falta ninguna).
  function findPathTolerante(map) {
    const tiles = [];
    for (let i = 0; i < map.tiles.length; i++) {
      const tile = map.tiles[i];
      tile.index = [];
      tile.next = [];
      tile.next_dir = [];
      tile.evacEntrance = -1;
      tile.evacExit = -1;
      tiles[`${tile.x},${tile.y},${tile.z}`] = tile;
    }
    const startTile = tiles[`${map.startTile.x},${map.startTile.y},${map.startTile.z}`];
    let startDir = '';
    Object.keys(startTile.tileType.paths).forEach(function (dir) {
      if (tiles[nextCoord(startTile, rotateDir(dir, startTile.rot))] !== undefined) {
        startDir = rotateDir(dir, startTile.rot);
      }
    });
    const uniones = [];
    traverseTolerante(startTile, startDir, tiles, map, 0, 0, false, uniones);
    return uniones;
  }

  window.RCJLocal = window.RCJLocal || {};
  window.RCJLocal.PFs = module.exports;
  window.RCJLocal.PFtolerante = { findPath: findPathTolerante };
})();

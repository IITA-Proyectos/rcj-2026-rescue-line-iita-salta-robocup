/*
 * rcj-line-offline — área backend.
 * RCJLocal.store: persistencia en IndexedDB ('rcj-line-offline', versión 1) con transacciones.
 *   get(col, id)  list(col, filtroFn?)  put(col, doc)  del(col, id)  clear(col)  tx(cols, fn, modo?)
 * Todas devuelven Promise. `tx` ejecuta fn(t) con la MISMA transacción IndexedDB; fn no debe
 * esperar nada ajeno a IndexedDB (fetch, setTimeout), porque la transacción se cerraría.
 * Si IndexedDB no está disponible se usa un almacén en memoria con la misma interfaz (se avisa
 * por consola: los datos no sobreviven a la recarga).
 */
(function () {
  'use strict';

  var R = window.RCJLocal = window.RCJLocal || {};

  var NOMBRE_BASE = 'rcj-line-offline';
  var VERSION_BASE = 1;
  var COLECCIONES = ['competitions', 'rounds', 'teams', 'fields', 'lineMaps', 'lineRuns', 'tileSets', 'meta'];
  var INDICES = {
    rounds: ['competition'],
    teams: ['competition'],
    fields: ['competition'],
    lineMaps: ['competition', 'tileSet'],
    lineRuns: ['competition', 'map', 'team', 'round', 'field']
  };

  // ---------------------------------------------------------------- IndexedDB
  var promesaBase = null;
  var enMemoria = null;

  // Aviso visible: sin IndexedDB lo que se puntúa se pierde al recargar (p.ej. modo incógnito).
  function avisarModoMemoria() {
    function pintar() {
      if (!document.body || document.getElementById('rcj-aviso-memoria')) return;
      var d = document.createElement('div');
      d.id = 'rcj-aviso-memoria';
      d.setAttribute('role', 'alert');
      d.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:100000;background:#b91c1c;color:#fff;' +
        'padding:10px 14px;font:600 14px/1.35 system-ui,sans-serif;text-align:center;box-shadow:0 -2px 8px rgba(0,0,0,.3)';
      d.textContent = 'Atención: este navegador no deja guardar datos (IndexedDB). Lo que cargues se pierde al ' +
        'recargar o cerrar la pestaña. Salí del modo incógnito o usá otro navegador.';
      document.body.appendChild(d);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', pintar);
    else pintar();
  }

  function abrirBase() {
    if (promesaBase) return promesaBase;
    promesaBase = new Promise(function (resolve, reject) {
      var req;
      try {
        req = window.indexedDB.open(NOMBRE_BASE, VERSION_BASE);
      } catch (e) {
        reject(e);
        return;
      }
      req.onupgradeneeded = function () {
        var db = req.result;
        COLECCIONES.forEach(function (col) {
          if (!db.objectStoreNames.contains(col)) {
            var os = db.createObjectStore(col, { keyPath: '_id' });
            (INDICES[col] || []).forEach(function (campo) {
              os.createIndex(campo, campo, { unique: false });
            });
          }
        });
      };
      req.onsuccess = function () {
        var db = req.result;
        db.onversionchange = function () { db.close(); promesaBase = null; };
        resolve(db);
      };
      req.onerror = function () { reject(req.error); };
      req.onblocked = function () { console.warn('[RCJLocal.store] apertura bloqueada por otra pestaña'); };
    }).catch(function (e) {
      console.warn('[RCJLocal.store] IndexedDB no disponible, se usa memoria:', e);
      enMemoria = crearMemoria();
      avisarModoMemoria();
      return null;
    });
    try {
      if (navigator.storage && navigator.storage.persist) {
        navigator.storage.persist().then(function (ok) { R.store.persistente = ok; }, function () {});
      }
    } catch (e) { /* sin StorageManager */ }
    return promesaBase;
  }

  function promesaDe(req) {
    return new Promise(function (resolve, reject) {
      req.onsuccess = function () { resolve(req.result); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function envolverTx(tx) {
    return {
      get: function (col, id) {
        if (id == null || id === '') return Promise.resolve(null);
        return promesaDe(tx.objectStore(col).get(String(id))).then(function (v) { return v === undefined ? null : v; });
      },
      list: function (col, filtro) {
        return promesaDe(tx.objectStore(col).getAll()).then(function (arr) {
          return typeof filtro === 'function' ? arr.filter(filtro) : arr;
        });
      },
      porIndice: function (col, indice, valor) {
        return promesaDe(tx.objectStore(col).index(indice).getAll(valor));
      },
      put: function (col, doc) {
        return promesaDe(tx.objectStore(col).put(doc)).then(function () { return doc; });
      },
      del: function (col, id) {
        return promesaDe(tx.objectStore(col).delete(String(id))).then(function () { return undefined; });
      },
      clear: function (col) {
        return promesaDe(tx.objectStore(col).clear()).then(function () { return undefined; });
      },
      count: function (col) {
        return promesaDe(tx.objectStore(col).count());
      }
    };
  }

  function txIndexedDB(db, cols, fn, modo) {
    return new Promise(function (resolve, reject) {
      var tx;
      try {
        tx = db.transaction(cols, modo || 'readwrite');
      } catch (e) {
        reject(e);
        return;
      }
      var t = envolverTx(tx);
      var resultado, error = null, fnTermino = false, txTermino = false, abortada = false;

      function cerrar() {
        if (!fnTermino || !txTermino) return;
        if (error) reject(error);
        else if (abortada) reject(tx.error || new Error('Transacción abortada'));
        else resolve(resultado);
      }

      tx.oncomplete = function () { txTermino = true; cerrar(); };
      tx.onabort = function () { abortada = true; txTermino = true; cerrar(); };
      tx.onerror = function (ev) { /* se resuelve en onabort */ };

      Promise.resolve().then(function () { return fn(t); }).then(function (r) {
        resultado = r;
        fnTermino = true;
        cerrar();
      }, function (e) {
        error = e;
        fnTermino = true;
        try { tx.abort(); } catch (x) { /* ya cerrada */ }
        // Si la transacción ya había terminado, onabort no vuelve a dispararse
        if (txTermino) cerrar();
      });
    });
  }

  // ---------------------------------------------------------------- memoria (respaldo)
  function clonar(v) {
    if (v === undefined) return undefined;
    try { return structuredClone(v); } catch (e) { return JSON.parse(JSON.stringify(v)); }
  }

  function crearMemoria() {
    var datos = {};
    COLECCIONES.forEach(function (c) { datos[c] = new Map(); });
    var cola = Promise.resolve();
    return {
      tx: function (cols, fn) {
        var ejecutar = function () {
          var respaldo = {};
          cols.forEach(function (c) { respaldo[c] = new Map(Array.from(datos[c].entries()).map(function (e) { return [e[0], clonar(e[1])]; })); });
          var t = {
            get: function (col, id) { return Promise.resolve(datos[col].has(String(id)) ? clonar(datos[col].get(String(id))) : null); },
            list: function (col, filtro) {
              var arr = Array.from(datos[col].keys()).sort().map(function (k) { return clonar(datos[col].get(k)); });
              return Promise.resolve(typeof filtro === 'function' ? arr.filter(filtro) : arr);
            },
            porIndice: function (col, indice, valor) {
              return t.list(col, function (d) { return d[indice] === valor; });
            },
            put: function (col, doc) { datos[col].set(String(doc._id), clonar(doc)); return Promise.resolve(doc); },
            del: function (col, id) { datos[col].delete(String(id)); return Promise.resolve(); },
            clear: function (col) { datos[col].clear(); return Promise.resolve(); },
            count: function (col) { return Promise.resolve(datos[col].size); }
          };
          return Promise.resolve().then(function () { return fn(t); }).catch(function (e) {
            cols.forEach(function (c) { datos[c] = respaldo[c]; });
            throw e;
          });
        };
        var p = cola.then(ejecutar, ejecutar);
        cola = p.catch(function () {});
        return p;
      }
    };
  }

  // ---------------------------------------------------------------- API pública
  var store = {
    nombreBase: NOMBRE_BASE,
    colecciones: COLECCIONES.slice(),
    persistente: null,

    abrir: function () { return abrirBase(); },

    tx: function (cols, fn, modo) {
      if (typeof cols === 'string') cols = [cols];
      return abrirBase().then(function (db) {
        if (!db) return enMemoria.tx(cols, fn, modo);
        return txIndexedDB(db, cols, fn, modo);
      });
    },

    get: function (col, id) {
      return store.tx([col], function (t) { return t.get(col, id); }, 'readonly');
    },
    list: function (col, filtro) {
      return store.tx([col], function (t) { return t.list(col, filtro); }, 'readonly');
    },
    put: function (col, doc) {
      return store.tx([col], function (t) { return t.put(col, doc); }, 'readwrite');
    },
    del: function (col, id) {
      return store.tx([col], function (t) { return t.del(col, id); }, 'readwrite');
    },
    clear: function (col) {
      return store.tx([col], function (t) { return t.clear(col); }, 'readwrite');
    },
    count: function (col) {
      return store.tx([col], function (t) { return t.count(col); }, 'readonly');
    },
    enMemoria: function () { return !!enMemoria; }
  };

  R.store = store;
})();

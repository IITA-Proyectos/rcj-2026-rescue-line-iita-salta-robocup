/*
 * rcj-line-offline — área backend.
 * copyProperties: routes/api/lineMaps.js:214-239 del CMS (commit d805502) copiado VERBATIM
 * (idéntico a routes/api/lineRuns.js:561-586 salvo sangría). Itera en orden de inserción y corta
 * en la primera clave ilegal; los Error de niveles internos se descartan (H3).
 * Sobre objetos planos `dbObj.get` es undefined: la lista blanca es hasOwnProperty. El casteo de
 * mongoose se emula aparte en api.js (ver cambios/backend.md).
 */
(function () {
// ===== INICIO VERBATIM routes/api/lineMaps.js:214-239 (rcj-rescue-cms d805502) =====
// Recursively updates properties in "dbObj" from "obj"
const copyProperties = function (obj, dbObj) {
  for (const prop in obj) {
    if (
      obj.constructor == Array ||
      (obj.hasOwnProperty(prop) &&
        (dbObj.hasOwnProperty(prop) ||
          (dbObj.get !== undefined && dbObj.get(prop) !== undefined)))
    ) {
      // Mongoose objects don't have hasOwnProperty
      if (typeof obj[prop] === 'object' && dbObj[prop] != null) {
        // Catches object and array
        copyProperties(obj[prop], dbObj[prop]);

        if (dbObj.markModified !== undefined) {
          dbObj.markModified(prop);
        }
      } else if (obj[prop] !== undefined) {
        // logger.debug("copy " + prop)
        dbObj[prop] = obj[prop];
      }
    } else {
      return new Error(`Illegal key: ${prop}`);
    }
  }
};
// ===== FIN VERBATIM routes/api/lineMaps.js:214-239 =====

  window.RCJLocal = window.RCJLocal || {};
  window.RCJLocal.copyProperties = copyProperties;
})();

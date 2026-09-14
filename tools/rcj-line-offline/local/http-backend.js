/*
 * rcj-line-offline — área backend.
 * RCJLocal.instalarBackend(nombreModuloAngular): decora $httpBackend para que todo pedido a /api/*
 * lo atienda RCJLocal.api.request en el navegador; el resto (templates, lang, imágenes) va al
 * $httpBackend real. Se decora $httpBackend (y no un interceptor de $http) para conservar
 * angular.toJson (quita $$hashKey), responseType 'arraybuffer'/'blob', headers() y statusText.
 *
 * También parchea jQuery.ajax: el $.ajax síncrono de tileCount del editor (L26:480-485) se
 * responde con la caché en memoria; otros $.ajax a /api/* se atienden asíncronos; el resto pasa al
 * $.ajax original.
 *
 * Uso: cargar después de angular (y de jQuery) y del JS de la página, y llamar
 *   RCJLocal.instalarBackend('NombreDelModulo');
 * antes de que Angular arranque (ng-app arranca en DOMContentLoaded).
 */
(function () {
  'use strict';

  var R = window.RCJLocal = window.RCJLocal || {};

  function urlApi(url) {
    if (typeof url !== 'string') return null;
    try {
      var u = new URL(url, window.location.href);
      if (u.origin !== window.location.origin) return null;
      return /^\/api(\/|$)/.test(u.pathname) ? u : null;
    } catch (e) {
      return null;
    }
  }

  function esPromesa(x) { return x && typeof x.then === 'function'; }

  function textoJSON(data) {
    if (data === undefined || data === null) return '';
    if (typeof data === 'string') return data;
    return JSON.stringify(data);
  }

  function aArrayBuffer(data) {
    if (data instanceof ArrayBuffer) return Promise.resolve(data);
    if (ArrayBuffer.isView(data)) return Promise.resolve(data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength));
    if (typeof Blob !== 'undefined' && data instanceof Blob) return data.arrayBuffer();
    return Promise.resolve(new TextEncoder().encode(textoJSON(data)).buffer);
  }

  function aBlob(data, tipo) {
    if (typeof Blob !== 'undefined' && data instanceof Blob) return Promise.resolve(data);
    if (data instanceof ArrayBuffer || ArrayBuffer.isView(data)) return Promise.resolve(new Blob([data], { type: tipo || '' }));
    return Promise.resolve(new Blob([textoJSON(data)], { type: tipo || '' }));
  }

  function aTexto(data) {
    if (typeof Blob !== 'undefined' && data instanceof Blob) return data.text();
    if (data instanceof ArrayBuffer || ArrayBuffer.isView(data)) return Promise.resolve(new TextDecoder().decode(data));
    return Promise.resolve(textoJSON(data));
  }

  function cadenaHeaders(headers) {
    return Object.keys(headers || {}).map(function (k) { return k + ': ' + headers[k]; }).join('\n');
  }

  function tipoContenido(headers) {
    var k = Object.keys(headers || {}).find(function (h) { return h.toLowerCase() === 'content-type'; });
    return k ? headers[k] : '';
  }

  // Codifica la respuesta como la entregaría un XMLHttpRequest con ese responseType
  function codificar(r, responseType) {
    var p;
    if (responseType === 'arraybuffer') p = aArrayBuffer(r.data);
    else if (responseType === 'blob') p = aBlob(r.data, tipoContenido(r.headers));
    else if (responseType === 'json') {
      p = aTexto(r.data).then(function (txt) {
        try { return txt === '' ? null : JSON.parse(txt); } catch (e) { return null; }
      });
    } else p = aTexto(r.data);
    return p.then(function (cuerpo) {
      return { status: r.status, response: cuerpo, headersString: cadenaHeaders(r.headers), statusText: r.statusText || '' };
    });
  }
  R._codificarRespuesta = codificar;

  /**
   * Instala el backend local en un módulo AngularJS ya definido.
   */
  R.instalarBackend = function (nombreModulo) {
    if (!window.angular) throw new Error('RCJLocal.instalarBackend: AngularJS no está cargado');
    var modulo = window.angular.module(nombreModulo);
    var listo = (R.api && R.api.listo) ? R.api.listo().catch(function (e) {
      console.error('[RCJLocal.http] no se pudo inicializar el backend local', e);
    }) : Promise.resolve();

    modulo.config(['$provide', function ($provide) {
      $provide.decorator('$httpBackend', ['$delegate', function ($delegate) {
        return function backendLocal(method, url, post, callback, headers, timeout, withCredentials, responseType, eventHandlers, uploadEventHandlers) {
          var u = urlApi(url);
          if (!u) return $delegate.apply(this, arguments);

          var terminado = false;
          var idTimeout;
          function completar(status, response, headersString, statusText, xhrStatus) {
            if (terminado) return;
            terminado = true;
            if (idTimeout !== undefined) clearTimeout(idTimeout);
            callback(status, response, headersString, statusText, xhrStatus);
          }
          if (timeout > 0) {
            idTimeout = setTimeout(function () { completar(-1, null, null, '', 'timeout'); }, timeout);
          } else if (esPromesa(timeout)) {
            timeout.then(function () { completar(-1, null, null, '', 'abort'); });
          }

          listo.then(function () {
            return R.api.request(method, u.pathname + u.search, post, { responseType: responseType, headers: headers });
          }).then(function (r) {
            return codificar(r, responseType);
          }).then(function (c) {
            completar(c.status, c.response, c.headersString, c.statusText, 'complete');
          }, function (e) {
            console.error('[RCJLocal.http]', method, url, e);
            var cuerpo = JSON.stringify({ msg: 'Error interno del backend local', err: String((e && e.message) || e) });
            codificar({ status: 500, data: cuerpo, headers: { 'Content-Type': 'application/json; charset=utf-8' }, statusText: 'Internal Server Error' }, responseType)
              .then(function (c) { completar(c.status, c.response, c.headersString, c.statusText, 'complete'); });
          });
        };
      }]);
    }]);

    R.parchearJQuery();
    return modulo;
  };

  // ------------------------------------------------------------------ jQuery.ajax
  function jqXHRSincrono(r, opciones) {
    var $ = window.jQuery;
    var ok = r.status >= 200 && r.status < 300 || r.status === 304;
    var texto = textoJSON(r.data);
    var json;
    if (typeof r.data === 'object' && r.data !== null) json = r.data;
    else { try { json = texto ? JSON.parse(texto) : undefined; } catch (e) { json = undefined; } }
    var xhr = {
      readyState: 4,
      status: r.status,
      statusText: ok ? 'success' : 'error',
      responseText: texto,
      responseJSON: json,
      getResponseHeader: function (nombre) {
        var k = Object.keys(r.headers || {}).find(function (h) { return h.toLowerCase() === String(nombre).toLowerCase(); });
        return k ? r.headers[k] : null;
      },
      getAllResponseHeaders: function () { return cadenaHeaders(r.headers); },
      abort: function () { return xhr; },
      setRequestHeader: function () { return xhr; },
      overrideMimeType: function () { return xhr; },
      statusCode: function () { return xhr; }
    };
    var dato = (opciones.dataType === 'json' || json !== undefined) ? json : texto;
    var d = $ && $.Deferred ? $.Deferred() : null;
    if (d) {
      if (ok) d.resolveWith(opciones.context || xhr, [dato, 'success', xhr]);
      else d.rejectWith(opciones.context || xhr, [xhr, 'error', r.statusText]);
      d.promise(xhr);
      xhr.success = xhr.done;
      xhr.error = xhr.fail;
    }
    try {
      if (ok && typeof opciones.success === 'function') opciones.success.call(opciones.context || xhr, dato, 'success', xhr);
      if (!ok && typeof opciones.error === 'function') opciones.error.call(opciones.context || xhr, xhr, 'error', r.statusText);
      if (typeof opciones.complete === 'function') opciones.complete.call(opciones.context || xhr, xhr, ok ? 'success' : 'error');
    } catch (e) {
      console.error(e);
    }
    return xhr;
  }

  R.parchearJQuery = function () {
    var $ = window.jQuery;
    if (!$ || !$.ajax || $.ajax.__rcjLocal) return false;
    var original = $.ajax;
    var nuevo = function (url, opciones) {
      if (typeof url === 'object' && url !== null) {
        opciones = url;
        url = undefined;
      }
      opciones = opciones || {};
      var destino = url || opciones.url;
      var u = urlApi(destino);
      if (!u) return original.apply(this, arguments);
      var metodo = String(opciones.type || opciones.method || 'GET').toUpperCase();
      var ruta = u.pathname + u.search;
      if (opciones.data && metodo === 'GET' && typeof opciones.data === 'object') {
        ruta += (u.search ? '&' : '?') + $.param(opciones.data);
      }
      if (opciones.async === false) {
        return jqXHRSincrono(R.api.requestSync(metodo, ruta, opciones.data), opciones);
      }
      var d = $.Deferred();
      var xhr = d.promise({ readyState: 1, abort: function () {} });
      R.api.request(metodo, ruta, metodo === 'GET' ? undefined : opciones.data).then(function (r) {
        var sincro = jqXHRSincrono(r, {});
        Object.assign(xhr, {
          readyState: 4, status: sincro.status, statusText: sincro.statusText, responseText: sincro.responseText,
          responseJSON: sincro.responseJSON, getResponseHeader: sincro.getResponseHeader, getAllResponseHeaders: sincro.getAllResponseHeaders
        });
        var ok = r.status >= 200 && r.status < 300;
        var dato = (opciones.dataType === 'json' || sincro.responseJSON !== undefined) ? sincro.responseJSON : sincro.responseText;
        if (ok) {
          if (typeof opciones.success === 'function') opciones.success.call(opciones.context || xhr, dato, 'success', xhr);
          d.resolveWith(opciones.context || xhr, [dato, 'success', xhr]);
        } else {
          if (typeof opciones.error === 'function') opciones.error.call(opciones.context || xhr, xhr, 'error', r.statusText);
          d.rejectWith(opciones.context || xhr, [xhr, 'error', r.statusText]);
        }
        if (typeof opciones.complete === 'function') opciones.complete.call(opciones.context || xhr, xhr, ok ? 'success' : 'error');
      });
      return xhr;
    };
    nuevo.__rcjLocal = true;
    nuevo.original = original;
    $.ajax = nuevo;
    return true;
  };

  // Si jQuery ya está cargado se parchea de inmediato (el editor lo usa aunque no se instale Angular)
  if (window.jQuery) R.parchearJQuery();
})();

/*
 * rcj-line-offline — área salidas.
 * Entorno "Node" mínimo para correr en el navegador, sin tocar su lógica, los generadores del CMS
 * (helper/lineSSR, helper/lineMapPDF.js, helper/scoreSheetPDF*.js y los handlers de routes/api):
 *
 *   - require() por tabla y registro de módulos con semántica de CommonJS (el objeto `exports`
 *     se crea antes de cargar el módulo, así un require "circular" o anticipado ve las funciones
 *     cuando se llaman).
 *   - path.join y un fs sincrónico: los estáticos (public/..., scoresheet_generation/...) se
 *     descargan con fetch y quedan en caché; tmp/course/* vive en memoria (como el disco del
 *     servidor). Si un archivo no está, readFileSync/statSync lanzan ENOENT como Node.
 *   - @napi-rs/canvas → <canvas> del navegador (toBuffer devuelve una Promise<ArrayBuffer>).
 *   - pdfkit → components/pdfkit 0.12.3 standalone (la misma versión del CMS). Solo se agrega que
 *     doc.image('ruta') lea los bytes del fs local (pdfkit standalone no tiene disco).
 *   - qr-image → qrcode-generator + codificador PNG gris de 8 bits (mismos defaults: nivel M,
 *     5 px por módulo).
 *   - archiver('zip') → ZIP sin compresión (STORE).
 *   - res de Express + stream escribible para doc.pipe(res).
 *
 * Lo carga local/render/registrar.js bajo demanda; no incluirlo a mano en las páginas.
 */
(function (global) {
  'use strict';

  var R = global.RCJLocal = global.RCJLocal || {};
  var S = R.salidas = R.salidas || {};
  if (S.comun) return;
  var C = S.comun = {};

  C.base = function () { return R.base || '/'; };

  // ------------------------------------------------------------------ módulos CommonJS
  var registro = {};
  C.exportsDe = function (nombre) {
    if (!registro[nombre]) registro[nombre] = {};
    return registro[nombre];
  };
  C.modulo = function (nombre) {
    return { id: nombre, exports: C.exportsDe(nombre) };
  };
  // Si el módulo reasignó module.exports, se copian sus claves al objeto registrado
  C.publicar = function (module) {
    var destino = C.exportsDe(module.id);
    if (module.exports !== destino) Object.assign(destino, module.exports);
    return destino;
  };
  C.requireDe = function (tabla) {
    return function require(nombre) {
      if (!Object.prototype.hasOwnProperty.call(tabla, nombre)) {
        throw new Error("[rcj-line-offline] require no soportado en el navegador: '" + nombre + "'");
      }
      var v = tabla[nombre];
      if (typeof v === 'function' && v.__perezoso) return v();
      return typeof v === 'string' ? C.exportsDe(v) : v;
    };
  };
  // Valor que se resuelve recién cuando el módulo hace require (p.ej. la clase de pdfkit)
  C.perezoso = function (fn) { fn.__perezoso = true; return fn; };

  C.logger = {
    info: function () { console.info.apply(console, arguments); },
    warn: function () { console.warn.apply(console, arguments); },
    error: function () { console.error.apply(console, arguments); },
    debug: function () { console.debug.apply(console, arguments); }
  };

  // process.env que usa scoreSheetPDFLineRules/2026.js:161 (server.js:14-15 con package.json:3-4)
  C.process = {
    env: {
      cms_copyright: '2016-2026 RoboCupJunior Rescue CMS Development SubCommittee',
      cms_version: '26.0.2'
    }
  };

  // ------------------------------------------------------------------ path
  function normalizar(p) {
    p = String(p).replace(/\\/g, '/');
    var absoluta = p.charAt(0) === '/';
    var partes = [];
    p.split('/').forEach(function (s) {
      if (s === '' || s === '.') return;
      if (s === '..') {
        if (partes.length && partes[partes.length - 1] !== '..') partes.pop();
        else if (!absoluta) partes.push('..');
        return;
      }
      partes.push(s);
    });
    return (absoluta ? '/' : '') + partes.join('/');
  }
  C.path = {
    join: function () {
      return normalizar(Array.prototype.slice.call(arguments).map(String).filter(function (x) { return x !== ''; }).join('/'));
    },
    normalize: normalizar,
    extname: function (p) { var m = /(\.[^./]*)$/.exec(String(p)); return m ? m[1] : ''; }
  };

  // ------------------------------------------------------------------ fs
  var memoria = new Map();      // tmp/... escrito por el propio generador
  var directorios = new Set();
  var descargados = new Map();  // ruta -> ArrayBuffer | null (estáticos de la app)
  var enCurso = new Map();

  // Rutas relativas a la raíz del CMS -> URL de la app offline
  C.urlDe = function (ruta) {
    var n = normalizar(ruta);
    if (n.indexOf('public/') === 0) return C.base() + n.slice('public/'.length);
    if (n.indexOf('scoresheet_generation/') === 0) return C.base() + n;
    return null;
  };

  function enoent(syscall, ruta) {
    var e = new Error("ENOENT: no such file or directory, " + syscall + " '" + ruta + "'");
    e.errno = -2;
    e.code = 'ENOENT';
    e.syscall = syscall;
    e.path = ruta;
    return e;
  }

  function aArrayBuffer(datos) {
    if (datos instanceof ArrayBuffer) return datos;
    if (ArrayBuffer.isView(datos)) return datos.buffer.slice(datos.byteOffset, datos.byteOffset + datos.byteLength);
    return new TextEncoder().encode(String(datos)).buffer;
  }
  C.aArrayBuffer = aArrayBuffer;

  async function descargar(n) {
    if (descargados.has(n)) return descargados.get(n);
    var url = C.urlDe(n);
    if (!url) return null;
    if (enCurso.has(n)) return enCurso.get(n);
    var p = (async function () {
      var valor = null;
      try {
        var r = await fetch(url);
        var tipo = r.headers.get('Content-Type') || '';
        // Un 404 "blando" (SPA/Service Worker que devuelve HTML) cuenta como archivo inexistente
        if (r.ok && !/^text\/html/i.test(tipo)) valor = await r.arrayBuffer();
      } catch (e) {
        valor = null;
      }
      descargados.set(n, valor);
      enCurso.delete(n);
      return valor;
    })();
    enCurso.set(n, p);
    return p;
  }

  C.fs = {
    // Versión asíncrona de existsSync para los estáticos (lineSSR/2026.js:22)
    existe: async function (ruta) {
      var n = normalizar(ruta);
      if (memoria.has(n) || directorios.has(n)) return true;
      return (await descargar(n)) !== null;
    },
    precargar: function (lista) {
      return Promise.all((lista || []).map(function (r) { return descargar(normalizar(r)); }));
    },
    existsSync: function (ruta) {
      var n = normalizar(ruta);
      return memoria.has(n) || directorios.has(n) || !!descargados.get(n);
    },
    statSync: function (ruta) {
      var n = normalizar(ruta);
      var datos = memoria.get(n) || descargados.get(n);
      var esDir = directorios.has(n);
      if (!datos && !esDir) throw enoent('stat', ruta);
      var ahora = new Date();
      return {
        size: datos ? datos.byteLength : 0, birthtime: ahora, ctime: ahora, mtime: ahora,
        isFile: function () { return !!datos; }, isDirectory: function () { return esDir; }
      };
    },
    readFileSync: function (ruta) {
      if (typeof ruta !== 'string') throw new TypeError('The "path" argument must be of type string. Received ' + typeof ruta);
      var n = normalizar(ruta);
      var datos = memoria.has(n) ? memoria.get(n) : descargados.get(n);
      if (!datos) throw enoent('open', ruta);
      return datos;
    },
    writeFileSync: function (ruta, datos) {
      var n = normalizar(ruta);
      memoria.set(n, aArrayBuffer(datos));
    },
    mkdirSync: function (ruta) {
      var n = normalizar(ruta);
      var partes = n.split('/');
      for (var i = 1; i <= partes.length; i++) directorios.add(partes.slice(0, i).join('/'));
    },
    // scoreSheetPDFLine2.js:5-11 lista las reglas: en el navegador solo está portada la 2026
    readdirSync: function (ruta) {
      var n = normalizar(ruta);
      if (n === 'helper/scoreSheetPDFLineRules') return ['2026.js'];
      throw enoent('scandir', ruta);
    },
    _memoria: memoria,
    _descargados: descargados
  };

  // Recursos que la planilla lee sincrónicamente (scoreSheetPDFLineRules/2026.js)
  C.RECURSOS_PLANILLA = [
    'scoresheet_generation/line/base2024.png',
    'scoresheet_generation/line/start.png',
    'scoresheet_generation/line/checkpoint.png',
    'scoresheet_generation/line/checkpointE.png',
    'scoresheet_generation/line/element.png',
    'scoresheet_generation/line/after_final.png',
    'scoresheet_generation/line/after_finalE.png',
    'scoresheet_generation/line/obstacle.png',
    'scoresheet_generation/line/ramp.png',
    'scoresheet_generation/line/speedbump.png',
    'public/images/logo.png'
  ];

  // glob y guesslanguage (scoreSheetPDFLineRules/2026.js:5-6): la carpeta fonts/ del CMS está vacía,
  // así que el resultado siempre es "sin fuente" (Helvetica).
  C.glob = { sync: function () { return []; } };
  C.guessLanguage = { guessLanguage: { name: function (texto, cb) { cb('unknown'); } } };

  // ------------------------------------------------------------------ @napi-rs/canvas
  C.canvas = {
    createCanvas: function (ancho, alto) {
      var lienzo;
      if (typeof document !== 'undefined') {
        lienzo = document.createElement('canvas');
        lienzo.width = ancho;
        lienzo.height = alto;
        lienzo.toBuffer = function (tipo) {
          return new Promise(function (resolver, rechazar) {
            lienzo.toBlob(function (blob) {
              if (!blob) return rechazar(new Error('canvas.toBlob devolvió null (¿lienzo de ' + ancho + 'x' + alto + ' demasiado grande?)'));
              blob.arrayBuffer().then(resolver, rechazar);
            }, tipo || 'image/png');
          });
        };
      } else {
        lienzo = new OffscreenCanvas(ancho, alto);
        lienzo.toBuffer = function (tipo) {
          return lienzo.convertToBlob({ type: tipo || 'image/png' }).then(function (b) { return b.arrayBuffer(); });
        };
      }
      return lienzo;
    },
    loadImage: async function (ruta) {
      var datos = C.fs.readFileSync(ruta);
      return await createImageBitmap(new Blob([datos]));
    }
  };

  // ------------------------------------------------------------------ CRC32 / Adler32 / PNG
  var TABLA_CRC = (function () {
    var t = new Int32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      t[n] = c;
    }
    return t;
  })();
  function crc32(bytes, inicial) {
    var c = inicial === undefined ? -1 : inicial;
    for (var i = 0; i < bytes.length; i++) c = TABLA_CRC[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    return c;
  }
  C.crc32 = function (bytes) { return (crc32(bytes) ^ -1) >>> 0; };
  function adler32(bytes) {
    var a = 1, b = 0;
    for (var i = 0; i < bytes.length; i++) {
      a = (a + bytes[i]) % 65521;
      b = (b + a) % 65521;
    }
    return ((b << 16) | a) >>> 0;
  }

  // zlib con bloques "stored" (sin compresión): válido para cualquier lector PNG/zlib
  function zlibSinCompresion(datos) {
    var n = datos.length;
    var bloques = Math.max(1, Math.ceil(n / 65535));
    var out = new Uint8Array(2 + n + bloques * 5 + 4);
    var p = 0;
    out[p++] = 0x78; out[p++] = 0x01;
    var i = 0;
    for (var b = 0; b < bloques; b++) {
      var largo = Math.min(65535, n - i);
      out[p++] = (b === bloques - 1) ? 1 : 0;
      out[p++] = largo & 0xFF; out[p++] = (largo >>> 8) & 0xFF;
      out[p++] = (~largo) & 0xFF; out[p++] = ((~largo) >>> 8) & 0xFF;
      out.set(datos.subarray(i, i + largo), p);
      p += largo; i += largo;
    }
    var ad = adler32(datos);
    out[p++] = (ad >>> 24) & 0xFF; out[p++] = (ad >>> 16) & 0xFF; out[p++] = (ad >>> 8) & 0xFF; out[p++] = ad & 0xFF;
    return out;
  }

  function u32(v) { return [(v >>> 24) & 0xFF, (v >>> 16) & 0xFF, (v >>> 8) & 0xFF, v & 0xFF]; }
  function chunkPNG(tipo, datos) {
    var tipoBytes = new TextEncoder().encode(tipo);
    var cuerpo = new Uint8Array(tipoBytes.length + datos.length);
    cuerpo.set(tipoBytes, 0);
    cuerpo.set(datos, tipoBytes.length);
    var out = new Uint8Array(12 + datos.length);
    out.set(u32(datos.length), 0);
    out.set(cuerpo, 4);
    out.set(u32(C.crc32(cuerpo)), 8 + datos.length);
    return out;
  }
  // PNG gris de 8 bits; `filas` ya trae el byte de filtro (0) al comienzo de cada fila
  C.pngGris8 = function (ancho, alto, filas) {
    var ihdr = new Uint8Array(13);
    ihdr.set(u32(ancho), 0);
    ihdr.set(u32(alto), 4);
    ihdr[8] = 8; ihdr[9] = 0; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
    var partes = [
      new Uint8Array([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
      chunkPNG('IHDR', ihdr),
      chunkPNG('IDAT', zlibSinCompresion(filas)),
      chunkPNG('IEND', new Uint8Array(0))
    ];
    var total = partes.reduce(function (s, x) { return s + x.length; }, 0);
    var out = new Uint8Array(total);
    var p = 0;
    partes.forEach(function (x) { out.set(x, p); p += x.length; });
    return out.buffer;
  };

  // ------------------------------------------------------------------ qr-image
  // qr.imageSync(texto, opciones): PNG con los defaults de qr-image para png
  // (ec_level 'M', size 5 px por módulo, margin 4; la planilla pasa margin 2).
  C.qrImage = {
    imageSync: function (texto, opciones) {
      if (typeof opciones === 'string') opciones = { ec_level: opciones };
      opciones = opciones || {};
      if (typeof global.qrcode !== 'function') throw new Error('[rcj-line-offline] falta components/qrcode-generator/qrcode.js');
      var nivel = opciones.ec_level || 'M';
      var tam = opciones.size || 5;
      var margen = ('margin' in opciones) ? opciones.margin : 4;
      var qr = global.qrcode(0, nivel);
      qr.addData(String(texto), 'Byte');
      qr.make();
      var N = qr.getModuleCount();
      var X = (N + 2 * margen) * tam;
      var filas = new Uint8Array((X + 1) * X);
      filas.fill(255);
      for (var f = 0; f < X; f++) filas[f * (X + 1)] = 0;
      for (var r = 0; r < N; r++) {
        for (var c = 0; c < N; c++) {
          if (!qr.isDark(r, c)) continue;
          for (var dy = 0; dy < tam; dy++) {
            var fila = (margen + r) * tam + dy;
            var inicio = fila * (X + 1) + 1 + (margen + c) * tam;
            filas.fill(0, inicio, inicio + tam);
          }
        }
      }
      return C.pngGris8(X, X, filas);
    }
  };

  // ------------------------------------------------------------------ archiver('zip')
  C.archiver = function (formato) {
    if (formato !== 'zip') throw new Error('[rcj-line-offline] archiver: solo zip');
    var entradas = [];
    var destino = null;
    function fechaDOS(d) {
      return {
        hora: ((d.getHours() << 11) | (d.getMinutes() << 5) | (Math.floor(d.getSeconds() / 2))) & 0xFFFF,
        fecha: (((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate()) & 0xFFFF
      };
    }
    var archivo = {
      pipe: function (dest) { destino = dest; return dest; },
      on: function () { return archivo; },
      append: function (datos, info) {
        entradas.push({ nombre: String((info && info.name) || ('archivo' + entradas.length)), bytes: new Uint8Array(aArrayBuffer(datos)) });
        return archivo;
      },
      finalize: function () {
        var partes = [], central = [], desplazamiento = 0;
        var dos = fechaDOS(new Date());
        entradas.forEach(function (e) {
          var nombre = new TextEncoder().encode(e.nombre);
          var crc = C.crc32(e.bytes);
          var local = new DataView(new ArrayBuffer(30));
          local.setUint32(0, 0x04034b50, true); local.setUint16(4, 20, true); local.setUint16(6, 0x0800, true);
          local.setUint16(8, 0, true); local.setUint16(10, dos.hora, true); local.setUint16(12, dos.fecha, true);
          local.setUint32(14, crc, true); local.setUint32(18, e.bytes.length, true); local.setUint32(22, e.bytes.length, true);
          local.setUint16(26, nombre.length, true); local.setUint16(28, 0, true);
          partes.push(new Uint8Array(local.buffer), nombre, e.bytes);
          var cd = new DataView(new ArrayBuffer(46));
          cd.setUint32(0, 0x02014b50, true); cd.setUint16(4, 20, true); cd.setUint16(6, 20, true); cd.setUint16(8, 0x0800, true);
          cd.setUint16(10, 0, true); cd.setUint16(12, dos.hora, true); cd.setUint16(14, dos.fecha, true);
          cd.setUint32(16, crc, true); cd.setUint32(20, e.bytes.length, true); cd.setUint32(24, e.bytes.length, true);
          cd.setUint16(28, nombre.length, true); cd.setUint16(30, 0, true); cd.setUint16(32, 0, true);
          cd.setUint16(34, 0, true); cd.setUint16(36, 0, true); cd.setUint32(38, 0, true); cd.setUint32(42, desplazamiento, true);
          central.push(new Uint8Array(cd.buffer), nombre);
          desplazamiento += 30 + nombre.length + e.bytes.length;
        });
        var tamCentral = central.reduce(function (s, x) { return s + x.length; }, 0);
        var fin = new DataView(new ArrayBuffer(22));
        fin.setUint32(0, 0x06054b50, true); fin.setUint16(8, entradas.length, true); fin.setUint16(10, entradas.length, true);
        fin.setUint32(12, tamCentral, true); fin.setUint32(16, desplazamiento, true);
        var todo = partes.concat(central, [new Uint8Array(fin.buffer)]);
        if (destino) {
          todo.forEach(function (x) { destino.write(x); });
          destino.end();
        }
        return Promise.resolve();
      }
    };
    return archivo;
  };

  // ------------------------------------------------------------------ pdfkit
  var ClasePDF = null;
  C.PDFDocument = C.perezoso(function () {
    if (ClasePDF) return ClasePDF;
    var Base = global.PDFDocument;
    if (typeof Base !== 'function') throw new Error('[rcj-line-offline] falta components/pdfkit/js/pdfkit.standalone.js');
    // Única diferencia con pdfkit en Node: doc.image('ruta/relativa.png') lee del fs local.
    // Se registra con la misma clave y el mismo contador de etiquetas (I1, I2, ...) que en Node.
    ClasePDF = class PDFDocument extends Base {
      openImage(src) {
        if (typeof src === 'string' && !this._imageRegistry[src] && !/^data:.+;base64,(.*)$/.test(src)) {
          var datos = C.fs.readFileSync(src);
          var imagen = super.openImage(datos);
          this._imageRegistry[src] = imagen;
          return imagen;
        }
        return super.openImage(src);
      }
    };
    return ClasePDF;
  });

  // ------------------------------------------------------------------ res de Express (+ Writable)
  var CT_JSON = 'application/json; charset=utf-8';
  var CT_HTML = 'text/html; charset=utf-8';

  function Respuesta() {
    var self = this;
    this.statusCode = 200;
    this.headers = {};
    this.finished = false;
    this.headersSent = false;
    this._trozos = [];
    this._eventos = {};
    this.terminado = new Promise(function (resolver) { self._resolver = resolver; });
  }
  Respuesta.prototype.on = function (ev, fn) {
    (this._eventos[ev] = this._eventos[ev] || []).push(fn);
    return this;
  };
  Respuesta.prototype.addListener = Respuesta.prototype.on;
  Respuesta.prototype.prependListener = function (ev, fn) {
    (this._eventos[ev] = this._eventos[ev] || []).unshift(fn);
    return this;
  };
  Respuesta.prototype.once = function (ev, fn) {
    var self = this;
    function envoltura() {
      self.removeListener(ev, envoltura);
      return fn.apply(this, arguments);
    }
    envoltura.listener = fn;
    return this.on(ev, envoltura);
  };
  Respuesta.prototype.removeListener = function (ev, fn) {
    var lista = this._eventos[ev];
    if (!lista) return this;
    for (var i = lista.length - 1; i >= 0; i--) {
      if (lista[i] === fn || lista[i].listener === fn) { lista.splice(i, 1); break; }
    }
    return this;
  };
  Respuesta.prototype.off = Respuesta.prototype.removeListener;
  Respuesta.prototype.listeners = function (ev) { return (this._eventos[ev] || []).slice(); };
  Respuesta.prototype.listenerCount = function (ev) { return (this._eventos[ev] || []).length; };
  Respuesta.prototype.emit = function (ev) {
    var args = Array.prototype.slice.call(arguments, 1);
    var lista = (this._eventos[ev] || []).slice();
    for (var i = 0; i < lista.length; i++) lista[i].apply(this, args);
    return lista.length > 0;
  };
  Respuesta.prototype.setHeader = function (k, v) { this.headers[k] = v; return this; };
  Respuesta.prototype.getHeader = function (k) {
    var clave = Object.keys(this.headers).find(function (h) { return h.toLowerCase() === String(k).toLowerCase(); });
    return clave ? this.headers[clave] : undefined;
  };
  Respuesta.prototype.set = Respuesta.prototype.setHeader;
  Respuesta.prototype.status = function (codigo) { this.statusCode = codigo; return this; };
  // res.attachment de Express 4: Content-Type por extensión + Content-Disposition
  Respuesta.prototype.attachment = function (nombre) {
    if (nombre) {
      if (/\.zip$/i.test(nombre)) this.setHeader('Content-Type', 'application/zip');
      else if (/\.pdf$/i.test(nombre)) this.setHeader('Content-Type', 'application/pdf');
      else if (/\.png$/i.test(nombre)) this.setHeader('Content-Type', 'image/png');
      this.setHeader('Content-Disposition', 'attachment; filename="' + nombre + '"');
    } else {
      this.setHeader('Content-Disposition', 'attachment');
    }
    return this;
  };
  Respuesta.prototype.write = function (trozo) {
    if (this.finished) return false;
    if (typeof trozo === 'string') trozo = new TextEncoder().encode(trozo);
    this._trozos.push(new Uint8Array(trozo));
    return true;
  };
  Respuesta.prototype._finalizar = function (datos) {
    if (this.finished) return;
    this.finished = true;
    this.headersSent = true;
    this._resolver({ status: this.statusCode, data: datos, headers: Object.assign({}, this.headers) });
  };
  Respuesta.prototype.end = function (trozo) {
    if (this.finished) return this;
    if (trozo) this.write(trozo);
    var total = this._trozos.reduce(function (s, x) { return s + x.length; }, 0);
    var out = new Uint8Array(total);
    var p = 0;
    this._trozos.forEach(function (x) { out.set(x, p); p += x.length; });
    this._trozos = [];
    this._finalizar(out.buffer);
    this.emit('finish');
    this.emit('close');
    return this;
  };
  // res.send de Express 4: string -> html, Buffer -> octet-stream, objeto -> json
  Respuesta.prototype.send = function (cuerpo) {
    if (this.finished) return this;
    if (cuerpo === null || cuerpo === undefined) {
      this._finalizar('');
    } else if (typeof cuerpo === 'string') {
      if (!this.getHeader('Content-Type')) this.setHeader('Content-Type', CT_HTML);
      this._finalizar(cuerpo);
    } else if (cuerpo instanceof ArrayBuffer || ArrayBuffer.isView(cuerpo)) {
      if (!this.getHeader('Content-Type')) this.setHeader('Content-Type', 'application/octet-stream');
      this._finalizar(aArrayBuffer(cuerpo).slice(0));
    } else {
      return this.json(cuerpo);
    }
    this.emit('finish');
    return this;
  };
  Respuesta.prototype.json = function (obj) {
    if (this.finished) return this;
    if (!this.getHeader('Content-Type')) this.setHeader('Content-Type', CT_JSON);
    this._finalizar(obj);
    this.emit('finish');
    return this;
  };
  C.Respuesta = Respuesta;

  // ------------------------------------------------------------------ Express: routers y ejecución
  var rutas = [];
  C.Router = function (montaje) {
    function agregar(metodo) {
      return function (ruta, handler) {
        rutas.push({ metodo: metodo, montaje: montaje, ruta: ruta, handler: handler });
      };
    }
    return { get: agregar('GET'), post: agregar('POST'), put: agregar('PUT'), delete: agregar('DELETE'), all: function () {} };
  };
  C.buscarRuta = function (metodo, montaje, ruta) {
    return rutas.find(function (r) { return r.metodo === metodo && r.montaje === montaje && r.ruta === ruta; }) || null;
  };
  C.rutas = rutas;

  var peticionActual = null;
  C.peticionActual = function () { return peticionActual; };

  /**
   * Corre un handler de Express y devuelve Promise<{status, data, headers}>.
   * next() sin error = ninguna otra ruta del CMS atiende -> 404 de app.js:280-282.
   * Excepción o promesa rechazada antes de responder (en el CMS: pedido colgado o 500) -> 500.
   */
  C.ejecutarExpress = function (handler, req) {
    return new Promise(function (resolver) {
      var listo = false;
      function terminar(r) { if (!listo) { listo = true; resolver(r); } }
      var res = new Respuesta();
      res.terminado.then(terminar);
      var ctx = {
        fallar: function (e) {
          console.error('[RCJLocal.salidas]', req.method, req.url, e);
          terminar({ status: 500, data: { msg: 'Error interno del backend local', err: String((e && e.message) || e) }, headers: { 'Content-Type': CT_JSON } });
        }
      };
      var next = function (err) {
        if (err) return ctx.fallar(err);
        terminar({ status: 404, data: { message: '404 Not found' }, headers: { 'Content-Type': CT_JSON } });
      };
      var previa = peticionActual;
      peticionActual = ctx;
      try {
        var p = handler(req, res, next);
        if (p && typeof p.then === 'function') p.then(null, ctx.fallar);
      } catch (e) {
        ctx.fallar(e);
      } finally {
        peticionActual = previa;
      }
    });
  };
})(window);

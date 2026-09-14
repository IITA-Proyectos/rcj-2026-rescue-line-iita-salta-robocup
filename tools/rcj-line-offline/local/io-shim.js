/*
 * rcj-line-offline — área backend.
 * io() falso compatible con el uso de socket.io-client que hacen las páginas de línea 2026:
 *   - sign/line_2026.js:114-176   io(origin, {transports}); emit('subscribe', 'runs/<id>'); on('data', fn)
 *   - ranking/line_2026.js:110-123 io({transports}).connect(origin); on('connect'); emit('subscribe', ...); on('changed')
 *   - line_competition.js:52-60   io(origin, {...}); emit('subscribe', 'runs/line/<cid>/status'); on('StatusChanged')
 *   - admin/games.js:58-71 y admin/gamesPrint/line_2026.js:52-65: igual que ranking
 *   - emit('unsubscribe', sala) antes de navegar / en beforeunload
 * El "servidor" (RCJLocal.emitirSocket en api.js) publica {tipo:'io', room, event, payload} en el
 * BroadcastChannel 'rcj-line-offline' y entrega en la misma ventana; cada socket entrega a sus
 * handlers solo si se suscribió a la sala (server.js:74-83). Alcance: pestañas y marcos del mismo
 * navegador y origen.
 * Cargar DESPUÉS de components/socket.io-client (si la página lo carga) para que este io() gane.
 */
(function () {
  'use strict';

  var R = window.RCJLocal = window.RCJLocal || {};
  if (!R.instanciaId) {
    R.instanciaId = (Date.now().toString(16) + Math.random().toString(16).slice(2)).slice(0, 24);
  }

  var sockets = [];
  var canal = null;
  try {
    canal = new BroadcastChannel('rcj-line-offline');
  } catch (e) {
    canal = null;
  }

  function copia(v) {
    return v === undefined ? undefined : JSON.parse(JSON.stringify(v));
  }

  function entregar(msg) {
    if (!msg || msg.tipo !== 'io') return;
    sockets.slice().forEach(function (s) { s._entregar(msg.room, msg.event, msg.payload, 'payload' in msg); });
  }

  if (canal) {
    canal.onmessage = function (ev) {
      var msg = ev.data;
      // lo emitido por esta misma ventana ya se entregó con R._ioLocal
      if (!msg || msg.origen === R.instanciaId) return;
      entregar(msg);
    };
  }
  R._ioLocal = entregar;

  var contador = 0;

  function SocketFalso() {
    var self = this;
    contador++;
    this.id = 'local-' + R.instanciaId.slice(-6) + '-' + contador;
    this.connected = false;
    this.disconnected = true;
    this.rooms = new Set();
    this._handlers = {};
    this.io = { opts: {}, engine: { transport: { name: 'broadcastchannel' } } };
    setTimeout(function () {
      if (self._cerrado) return;
      self.connected = true;
      self.disconnected = false;
      self._disparar('connect', []);
    }, 0);
  }

  SocketFalso.prototype.on = function (evento, fn) {
    if (typeof fn !== 'function') return this;
    (this._handlers[evento] = this._handlers[evento] || []).push(fn);
    return this;
  };
  SocketFalso.prototype.addEventListener = SocketFalso.prototype.on;
  SocketFalso.prototype.once = function (evento, fn) {
    var self = this;
    function envoltorio() {
      self.off(evento, envoltorio);
      return fn.apply(this, arguments);
    }
    envoltorio.fn = fn;
    return this.on(evento, envoltorio);
  };
  SocketFalso.prototype.off = function (evento, fn) {
    if (evento === undefined) { this._handlers = {}; return this; }
    if (fn === undefined) { delete this._handlers[evento]; return this; }
    var lista = this._handlers[evento] || [];
    this._handlers[evento] = lista.filter(function (h) { return h !== fn && h.fn !== fn; });
    return this;
  };
  SocketFalso.prototype.removeListener = SocketFalso.prototype.off;
  SocketFalso.prototype.removeAllListeners = function (evento) { return this.off(evento); };
  SocketFalso.prototype.hasListeners = function (evento) { return !!(this._handlers[evento] && this._handlers[evento].length); };
  SocketFalso.prototype.listeners = function (evento) { return (this._handlers[evento] || []).slice(); };

  SocketFalso.prototype.emit = function (evento, datos) {
    if (evento === 'subscribe') this.rooms.add(String(datos));
    else if (evento === 'unsubscribe') this.rooms.delete(String(datos));
    // el servidor del CMS no atiende otros eventos del cliente (server.js:74-83)
    return this;
  };
  SocketFalso.prototype.send = function () { return this; };

  SocketFalso.prototype.connect = function () {
    if (this._cerrado) {
      this._cerrado = false;
      if (sockets.indexOf(this) < 0) sockets.push(this);
      var self = this;
      setTimeout(function () { self.connected = true; self.disconnected = false; self._disparar('connect', []); }, 0);
    }
    return this;
  };
  SocketFalso.prototype.open = SocketFalso.prototype.connect;

  SocketFalso.prototype.disconnect = function () {
    this._cerrado = true;
    this.connected = false;
    this.disconnected = true;
    var i = sockets.indexOf(this);
    if (i >= 0) sockets.splice(i, 1);
    this._disparar('disconnect', ['io client disconnect']);
    return this;
  };
  SocketFalso.prototype.close = SocketFalso.prototype.disconnect;

  SocketFalso.prototype._entregar = function (sala, evento, payload, conPayload) {
    if (this._cerrado || !this.rooms.has(sala)) return;
    this._disparar(evento, conPayload ? [copia(payload)] : []);
  };

  SocketFalso.prototype._disparar = function (evento, args) {
    var lista = (this._handlers[evento] || []).slice();
    for (var i = 0; i < lista.length; i++) {
      try {
        lista[i].apply(this, args);
      } catch (e) {
        console.error('[RCJLocal.io] error en el handler de "' + evento + '":', e);
      }
    }
  };

  function io() {
    var s = new SocketFalso();
    sockets.push(s);
    return s;
  }
  io.connect = io;
  io.Socket = SocketFalso;
  io.protocol = 5;
  io.local = true;

  window.io = io;
  R.io = { canal: 'rcj-line-offline', sockets: sockets, Socket: SocketFalso };
})();

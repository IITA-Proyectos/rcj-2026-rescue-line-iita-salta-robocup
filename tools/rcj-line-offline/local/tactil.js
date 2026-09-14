/*
 * rcj-line-offline — área editor. Capa táctil del editor de mapas 2026 (ESPEC D5, flag RCJLocal.flags.tactil).
 *
 * No cambia la lógica del CMS: cada gesto termina en los MISMOS handlers de
 * javascripts/admin/mapEditor/line_2026.js (directivas lvl-draggable / lvl-drop-target, ng-right-click,
 * ng-click de la baldosa, listener de teclado y funciones del scope del controlador).
 *
 *  - Arrastrar y soltar: polyfill mobile-drag-drop (components/) que traduce touch en dragstart / dragover /
 *    drop con dataTransfer (setData/getData), más scroll-behaviour para desplazar el mapa al arrastrar cerca
 *    del borde. Mantener apretado ~300 ms y mover = arrastrar; deslizar rápido = desplazar (scroll nativo).
 *    Las celdas VACÍAS del mapa no inician arrastre (así se puede desplazar desde ellas).
 *  - Pulsación larga (~500 ms) sobre una celda del mapa = evento 'contextmenu' (abre el modal de propiedades,
 *    o el "Oops!" si la celda está vacía, como el clic derecho). Si el navegador ya dispara su propio menú
 *    contextual (Chrome Android) no se duplica. Después de la pulsación larga se descarta el clic de ese toque.
 *  - Botón "Selección": con el modo activo, tocar una baldosa = Ctrl+clic (se re-despacha el mismo clic con
 *    ctrlKey=true, así pasa por ng-click -> handleTileClick igual que en escritorio).
 *  - Botones Deshacer / Rehacer / Cortar / Salir del sello / Borrar selección: undo(), redo(),
 *    cutSelection(), la tecla Esc del listener de teclado y bulkDelete().
 *  - Paneo: scroll nativo del contenedor con uno o dos dedos. El marquee sigue siendo solo de mouse.
 *  - Modal de propiedades con scroll interno: el pie (Cancel / Save) queda a la vista en 768 px de alto.
 *
 * Sin pantalla táctil, o con RCJLocal.flags.tactil === false, no hace nada.
 */
(function (window, document) {
  'use strict';

  var R = window.RCJLocal = window.RCJLocal || {};
  var T = R.tactil = R.tactil || {};

  var PULSACION_LARGA_MS = 500;
  var ESPERA_ARRASTRE_MS = 300;
  var TOLERANCIA_PX = 10;
  var SUPRIMIR_CLICK_MS = 800;

  T.activo = false;
  T.polyfillAplicado = false;
  T.modoSeleccion = false;
  T.config = { pulsacionLargaMs: PULSACION_LARGA_MS, esperaArrastreMs: ESPERA_ARRASTRE_MS, toleranciaPx: TOLERANCIA_PX };

  function flagActivo() {
    return !(R.flags && R.flags.tactil === false);
  }

  function hayPantallaTactil() {
    try {
      return ('ontouchstart' in window) || (navigator.maxTouchPoints || 0) > 0 || (navigator.msMaxTouchPoints || 0) > 0;
    } catch (e) {
      return false;
    }
  }

  if (!flagActivo() || !hayPantallaTactil()) return; // escritorio: no cambia nada

  T.activo = true;
  document.documentElement.classList.add('rcj-tactil');

  // ------------------------------------------------------------------ acceso al controlador del editor
  function scopeEditor() {
    if (!window.angular || !document.body) return null;
    var s = window.angular.element(document.body).scope();
    return (s && typeof s.copySelection === 'function') ? s : null;
  }

  function aplicar(fn) {
    var s = scopeEditor();
    if (!s) return;
    if (s.$root && s.$root.$$phase) fn(s);
    else s.$apply(function () { fn(s); });
  }

  function celdaDelMapa(nodo) {
    if (!nodo || !nodo.closest) return null;
    var el = nodo.closest('tile');
    return (el && el.closest('#map-container')) ? el : null;
  }

  function celdaVacia(el) {
    try {
      var s = window.angular.element(el).isolateScope();
      return !(s && s.tile);
    } catch (e) {
      return false;
    }
  }

  // ------------------------------------------------------------------ pulsación larga = clic derecho
  var toque = null; // { id, x, y, el, timer, disparado }
  var suprimirClickHasta = 0;

  function cancelarPulsacion() {
    if (toque && toque.timer) {
      clearTimeout(toque.timer);
      toque.timer = null;
    }
  }

  function dispararMenuContextual() {
    if (!toque) return;
    toque.timer = null;
    if (toque.disparado || !toque.el) return;
    toque.disparado = true;
    var ev = new MouseEvent('contextmenu', {
      bubbles: true, cancelable: true, view: window, button: 2, buttons: 2,
      clientX: toque.x, clientY: toque.y, screenX: toque.x, screenY: toque.y
    });
    toque.el.dispatchEvent(ev);
  }

  function tocaIdentificador(lista, id) {
    for (var i = 0; i < lista.length; i++) if (lista[i].identifier === id) return lista[i];
    return null;
  }

  document.addEventListener('touchstart', function (e) {
    if (e.touches.length !== 1) {
      // segundo dedo: es paneo, no pulsación larga
      cancelarPulsacion();
      return;
    }
    var t = e.changedTouches[0];
    var el = celdaDelMapa(e.target);
    toque = { id: t.identifier, x: t.clientX, y: t.clientY, el: el, timer: null, disparado: false };
    if (el) toque.timer = setTimeout(dispararMenuContextual, PULSACION_LARGA_MS);
  }, { capture: true, passive: true });

  document.addEventListener('touchmove', function (e) {
    if (!toque || !toque.timer) return;
    var t = tocaIdentificador(e.changedTouches, toque.id);
    if (t && (Math.abs(t.clientX - toque.x) > TOLERANCIA_PX || Math.abs(t.clientY - toque.y) > TOLERANCIA_PX)) {
      cancelarPulsacion();
    }
  }, { capture: true, passive: true });

  document.addEventListener('touchend', function (e) {
    if (!toque || !tocaIdentificador(e.changedTouches, toque.id)) return;
    cancelarPulsacion();
    if (toque.disparado) {
      // Sin eventos de mouse de compatibilidad ni clic: el clic rotaría la baldosa o cerraría el modal
      // (el backdrop queda debajo del dedo).
      suprimirClickHasta = Date.now() + SUPRIMIR_CLICK_MS;
      if (e.cancelable) e.preventDefault();
    }
    toque = null;
  }, { capture: true, passive: false });

  document.addEventListener('touchcancel', function () {
    cancelarPulsacion();
    toque = null;
  }, { capture: true, passive: true });

  // Si empieza un arrastre, no es pulsación larga
  document.addEventListener('dragstart', cancelarPulsacion, true);

  window.addEventListener('contextmenu', function (e) {
    if (!e.isTrusted || !toque) return;
    if (toque.disparado) {
      // ya se abrió con el gesto propio: no duplicar el modal
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }
    // El navegador disparó su propio menú contextual durante el toque: se deja pasar (lo atiende
    // ng-right-click) y se marca como pulsación larga para no repetirlo ni arrastrar.
    cancelarPulsacion();
    toque.disparado = true;
  }, true);

  // ------------------------------------------------------------------ clics: supresión y modo selección
  window.addEventListener('click', function (e) {
    if (suprimirClickHasta && Date.now() < suprimirClickHasta) {
      suprimirClickHasta = 0;
      e.preventDefault();
      e.stopImmediatePropagation();
      return;
    }
    if (!T.modoSeleccion || e.ctrlKey || e.metaKey || e.shiftKey) return;
    if (!celdaDelMapa(e.target)) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    var copia = new MouseEvent('click', {
      bubbles: true, cancelable: true, view: window, detail: e.detail,
      screenX: e.screenX, screenY: e.screenY, clientX: e.clientX, clientY: e.clientY,
      button: 0, buttons: 0, ctrlKey: true, altKey: e.altKey
    });
    e.target.dispatchEvent(copia);
  }, true);

  // ------------------------------------------------------------------ polyfill de arrastrar y soltar
  // Regla por defecto de mobile-drag-drop (tryFindDraggableTarget), más: una celda vacía del mapa no arrastra.
  function arrastrableDesde(ev) {
    var el = ev.target;
    do {
      if (!el || el.draggable === false) continue;
      if (el.draggable === true) return el;
      if (el.getAttribute && el.getAttribute('draggable') === 'true') return el;
    } while ((el = el && el.parentNode) && el !== document.body);
    return undefined;
  }

  function iniciarPolyfill() {
    var MDD = window.MobileDragDrop;
    if (!MDD || typeof MDD.polyfill !== 'function') {
      console.warn('[rcj-line-offline] tactil: no se encontró mobile-drag-drop; arrastrar con el dedo no va a funcionar');
      return;
    }
    T.polyfillAplicado = MDD.polyfill({
      forceApply: true, // la detección de pantalla táctil ya la hizo este archivo
      holdToDrag: ESPERA_ARRASTRE_MS,
      dragImageTranslateOverride: MDD.scrollBehaviourDragImageTranslateOverride,
      tryFindDraggableTarget: function (ev) {
        var celda = celdaDelMapa(ev.target);
        if (celda && celdaVacia(celda)) return undefined;
        return arrastrableDesde(ev);
      },
      dragStartConditionOverride: function (ev) {
        if (toque && toque.disparado) return false; // después de la pulsación larga no se arrastra
        return ev.touches.length === 1;
      }
    });
    // iOS: sin un listener no pasivo, preventDefault() en touchmove no frena el scroll durante el arrastre
    window.addEventListener('touchmove', function () {}, { passive: false });
    // mobile-drag-drop sigue la especificación: un elemento pasa a ser destino solo si cancela 'dragenter'; si no,
    // el destino queda en <body> y nunca llega 'drop'. Las directivas lvlDropTarget del CMS solo cancelan 'dragover'
    // (Chrome de escritorio acepta el soltar igual). Se cancela 'dragenter' sobre los destinos del CMS
    // (atributo x-lvl-drop-target: celdas del mapa e imágenes de la paleta) para que el soltar con el dedo llegue al
    // MISMO handler 'drop' de la directiva. No toca la lógica: el handler 'dragenter' del CMS sigue corriendo.
    document.addEventListener('dragenter', function (e) {
      var t = e.target;
      if (t && t.closest && t.closest('[x-lvl-drop-target]')) e.preventDefault();
    }, true);
  }

  iniciarPolyfill();

  // ------------------------------------------------------------------ botones flotantes
  function teclaEscape() {
    var ev = new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true });
    if (ev.keyCode !== 27) {
      try {
        Object.defineProperty(ev, 'keyCode', { get: function () { return 27; } });
        Object.defineProperty(ev, 'which', { get: function () { return 27; } });
      } catch (err) { /* navegador sin redefinición: queda el key */ }
    }
    document.dispatchEvent(ev); // lo atiende el listener de teclado del editor (L26: Esc sale del modo sello)
  }

  var ACCIONES = [
    { id: 'seleccion', icono: 'fa-hand-pointer', texto: 'Selección', titulo: 'Modo selección: tocar una baldosa equivale a Ctrl+clic' },
    { id: 'deshacer', icono: 'fa-undo', texto: 'Deshacer', titulo: 'Deshacer (Ctrl+Z)' },
    { id: 'rehacer', icono: 'fa-redo', texto: 'Rehacer', titulo: 'Rehacer (Ctrl+Y)' },
    { id: 'cortar', icono: 'fa-cut', texto: 'Cortar', titulo: 'Cortar la selección (Ctrl+X)' },
    { id: 'salirSello', icono: 'fa-times-circle', texto: 'Salir del sello', titulo: 'Salir del modo sello (Esc)' },
    { id: 'borrar', icono: 'fa-trash-alt', texto: 'Borrar selección', titulo: 'Borrar la selección (Supr)' }
  ];

  T.acciones = {
    seleccion: function () { T.modoSeleccion = !T.modoSeleccion; actualizarBarra(); },
    deshacer: function () { aplicar(function (s) { s.undo(); }); },
    rehacer: function () { aplicar(function (s) { s.redo(); }); },
    cortar: function () { aplicar(function (s) { s.cutSelection(); }); },
    salirSello: teclaEscape,
    borrar: function () { aplicar(function (s) { s.bulkDelete(); }); }
  };

  function actualizarBarra() {
    var barra = document.getElementById('rcj-tactil-barra');
    if (!barra) return;
    var s = scopeEditor();
    var habilitado = {
      seleccion: true,
      deshacer: !!(s && s.canUndo()),
      rehacer: !!(s && s.canRedo()),
      cortar: !!(s && s.hasSelection()),
      salirSello: !!(s && s.isPasting),
      borrar: !!(s && s.hasSelection())
    };
    ACCIONES.forEach(function (a) {
      var b = barra.querySelector('[data-accion="' + a.id + '"]');
      if (b) b.disabled = !habilitado[a.id];
    });
    var bs = barra.querySelector('[data-accion="seleccion"]');
    bs.classList.toggle('activo', T.modoSeleccion);
    bs.setAttribute('aria-pressed', T.modoSeleccion ? 'true' : 'false');
    document.documentElement.classList.toggle('rcj-modo-seleccion', T.modoSeleccion);
  }
  T.actualizarBarra = actualizarBarra;

  var CSS = [
    'html.rcj-tactil tile, html.rcj-tactil .toolbox-tile, html.rcj-tactil .tile-palette-item {',
    '  -webkit-touch-callout: none; -webkit-user-select: none; user-select: none; }',
    '/* modal de propiedades: scroll interno, el pie (Cancel / Save) siempre a la vista */',
    'html.rcj-tactil .modal-dialog { max-height: calc(100vh - 3rem); max-height: calc(100dvh - 3rem); }',
    'html.rcj-tactil .modal-content { display: flex; flex-direction: column; max-height: calc(100vh - 3rem); max-height: calc(100dvh - 3rem); }',
    'html.rcj-tactil .modal-content > .premium-modal-body { flex: 1 1 auto; min-height: 0; overflow-y: auto;',
    '  -webkit-overflow-scrolling: touch; overscroll-behavior: contain; }',
    'html.rcj-tactil .modal-content > .modal-header, html.rcj-tactil .modal-content > .modal-footer { flex-shrink: 0; }',
    '.rcj-tactil-barra { position: fixed; left: 90px; bottom: 14px; z-index: 1035; display: flex; gap: 6px; padding: 6px;',
    '  background: rgba(15, 23, 42, 0.92); border-radius: 14px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25); }',
    '.rcj-tactil-barra button { min-width: 58px; min-height: 52px; padding: 4px 8px; border: 0; border-radius: 10px;',
    '  background: #334155; color: #fff; font-size: 0.7rem; font-weight: 700; line-height: 1.1; display: flex;',
    '  flex-direction: column; align-items: center; justify-content: center; gap: 4px; touch-action: manipulation; }',
    '.rcj-tactil-barra button i { font-size: 1.1rem; }',
    '.rcj-tactil-barra button:disabled { opacity: 0.35; }',
    '.rcj-tactil-barra button.activo { background: #4f46e5; box-shadow: inset 0 0 0 2px #a5b4fc; }',
    'html.rcj-modo-seleccion #map-container { outline: 3px dashed #4f46e5; outline-offset: -3px; }',
    '/* la barra no tapa el pie de la página al llegar al final */',
    'html.rcj-tactil body { padding-bottom: 76px; }',
    '/* celular: la barra ocupa todo el ancho, seis botones iguales */',
    '@media (max-width: 767.98px) {',
    '  .rcj-tactil-barra { left: 4px; right: 4px; bottom: 4px; gap: 4px; padding: 4px; justify-content: space-between; }',
    '  .rcj-tactil-barra button { flex: 1 1 0; min-width: 0; min-height: 50px; padding: 2px; font-size: 0.6rem; }',
    '}'
  ].join('\n');

  function montar() {
    var estilo = document.createElement('style');
    estilo.id = 'rcj-tactil-estilos';
    estilo.textContent = CSS;
    document.head.appendChild(estilo);

    var barra = document.createElement('div');
    barra.id = 'rcj-tactil-barra';
    barra.className = 'rcj-tactil-barra';
    barra.setAttribute('role', 'toolbar');
    barra.setAttribute('aria-label', 'Herramientas táctiles del editor');
    ACCIONES.forEach(function (a) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('data-accion', a.id);
      b.title = a.titulo;
      var i = document.createElement('i');
      i.className = 'fas ' + a.icono;
      var span = document.createElement('span');
      span.textContent = a.texto;
      b.appendChild(i);
      b.appendChild(span);
      b.addEventListener('click', function (ev) {
        ev.preventDefault();
        T.acciones[a.id]();
        actualizarBarra();
      });
      barra.appendChild(b);
    });
    document.body.appendChild(barra);
    actualizarBarra();

    // Cuando arranque Angular (el editor puede diferir el arranque), mantener los botones al día
    var intentos = 0;
    (function esperarEditor() {
      var s = scopeEditor();
      if (!s) {
        if (++intentos < 600) setTimeout(esperarEditor, 100);
        return;
      }
      s.$watch(function () {
        return [s.canUndo(), s.canRedo(), s.hasSelection(), !!s.isPasting].join('|');
      }, actualizarBarra);
    })();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', montar);
  else montar();
})(window, document);

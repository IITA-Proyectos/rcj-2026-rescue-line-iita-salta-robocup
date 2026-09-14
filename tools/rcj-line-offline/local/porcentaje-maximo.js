/*
 * rcj-line-offline — sección "En vivo": % del máximo del mapa (NUEVO, no es del CMS; flag mostrarPorcentaje).
 * Se inserta en el panel izquierdo (arriba de la tarjeta de LoPs) del juez, la firma y la vista, y se
 * actualiza sola mientras se puntúa. El máximo es el de la calculadora del editor (GET maxScore): todo
 * logrado sin LoPs, víctimas en orden y exit bonus. Si no encuentra el panel, muestra una píldora flotante.
 * Lee la corrida directo del store: GET /api/runs/line/:id re-inicializa corridas no empezadas.
 */
(function () {
  'use strict';

  var R = window.RCJLocal || {};
  if (R.flags && R.flags.mostrarPorcentaje === false) return;

  var maximos = {};
  var datos = null;

  function porciento(valor, maximo) {
    return maximo > 0 ? Math.round(valor * 1000 / maximo) / 10 : 0;
  }

  function coma(n, decimales) {
    var v = decimales == null ? String(n) : Number(n).toFixed(decimales);
    return v.replace('.', ',');
  }

  function tarjetaLoPs() {
    var lops = document.getElementById('lops');
    if (lops) return lops;
    var iconos = document.querySelectorAll('.card > .card-header .fa-step-forward');
    return iconos.length ? iconos[0].closest('.card') : null;
  }

  function htmlSeccion(d) {
    var color = d.p >= 80 ? 'bg-success' : d.p >= 50 ? 'bg-warning' : 'bg-danger';
    return '<h3 class="card-header"><i class="fas fa-chart-line" aria-hidden="true"></i> En vivo</h3>' +
      '<div class="card-body" style="padding:10px 14px;">' +
      '<div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;flex-wrap:wrap;">' +
      '<span style="font-size:2rem;font-weight:700;line-height:1.1;">' + coma(d.p) + ' %</span>' +
      '<span class="text-muted small">del máximo del mapa</span></div>' +
      '<div class="progress" style="height:10px;margin:6px 0 8px;"><div class="progress-bar ' + color +
      '" role="progressbar" style="width:' + Math.min(d.p, 100) + '%;"></div></div>' +
      '<div class="small">Puntaje: <b>' + d.score + '</b> de ' + d.maxScore + '</div>' +
      '<div class="small">Recorrido: <b>' + d.raw + '</b> de ' + d.maxRaw + ' (' + coma(d.pRaw) + ' %)</div>' +
      '<div class="small">Multiplicador: <b>×' + coma(d.mult, 3) + '</b> de ×' + coma(d.maxMult, 3) + '</div>' +
      '</div>';
  }

  function pintar() {
    if (!datos) return;
    var ancla = tarjetaLoPs();
    var pildora = document.getElementById('rcj-porcentaje');
    if (ancla && ancla.parentNode) {
      if (pildora) pildora.parentNode.removeChild(pildora);
      var sec = document.getElementById('rcj-en-vivo');
      if (!sec || sec.nextElementSibling !== ancla) {
        if (sec) sec.parentNode.removeChild(sec);
        sec = document.createElement('div');
        sec.id = 'rcj-en-vivo';
        sec.className = 'card';
        sec.style.marginBottom = '10px';
        ancla.parentNode.insertBefore(sec, ancla);
      }
      sec.innerHTML = htmlSeccion(datos);
      return;
    }
    // Sin panel (p.ej. pre-chequeo del juez): píldora flotante debajo de la barra.
    if (!pildora) {
      pildora = document.createElement('div');
      pildora.id = 'rcj-porcentaje';
      pildora.style.cssText = 'position:fixed;right:8px;z-index:99990;background:rgba(17,24,39,.9);color:#fff;border-radius:14px;' +
        'padding:4px 12px;font:600 13px/1.35 system-ui,sans-serif;box-shadow:0 2px 6px rgba(0,0,0,.35)';
      document.body.appendChild(pildora);
    }
    var nav = document.querySelector('nav.navbar, .navbar');
    pildora.style.top = Math.max((nav ? nav.getBoundingClientRect().bottom : 50) + 6, 6) + 'px';
    pildora.textContent = coma(datos.p) + ' % del máximo';
  }

  async function actualizar() {
    if (!R.store || !R.api || typeof window.runId === 'undefined' || !window.runId) return;
    var run = await R.store.get('lineRuns', window.runId);
    if (!run) return;
    var mapId = (run.map && run.map._id) ? run.map._id : run.map;
    if (!maximos[mapId]) {
      var m = await R.api.request('GET', '/api/maps/line/' + mapId + '/maxScore');
      if (m.status !== 200 || !m.data || !(m.data.score > 0)) return;
      maximos[mapId] = m.data;
    }
    var max = maximos[mapId];
    datos = {
      score: Number(run.score) || 0,
      raw: Number(run.raw_score) || 0,
      mult: Number(run.multiplier) || 1,
      maxScore: Number(max.score),
      maxRaw: Number(max.raw_score),
      maxMult: Number(max.multiplier) || 1
    };
    datos.p = porciento(datos.score, datos.maxScore);
    datos.pRaw = porciento(datos.raw, datos.maxRaw);
    pintar();
  }

  function ciclo() {
    actualizar().catch(function (e) { console.warn('[en-vivo]', e); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ciclo);
  else ciclo();
  setInterval(ciclo, 2000);
  window.addEventListener('resize', pintar);
})();

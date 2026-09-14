/*
 * rcj-line-offline — área estadísticas.
 * RCJEstadisticas.svg: gráficos en SVG inline generados como texto (sin librerías).
 *   evolucion(serie)      líneas score / raw_score por fecha, marcadores con <title> y capa para la cruz
 *   lopsTramos(tramos)    barras 100 % apiladas con la distribución de LoPs por tramo
 *   tira(heat)            recorrido lineal por índice, coloreado por % de éxito
 *   leyendaEscala()       barra de la escala de color de éxito
 * Todo texto variable pasa por esc(). Colores: categóricos 1-2 y rampa azul ordinal de la paleta de referencia
 * (skill dataviz); escala de éxito naranja de un solo tono (RCJEstadisticas.colorExito).
 */
(function (global) {
  'use strict';

  var E = global.RCJEstadisticas = global.RCJEstadisticas || {};

  var COL = {
    score: '#2a78d6', raw: '#eb6834', superficie: '#ffffff', grilla: '#e1e0d9', eje: '#c3c2b7',
    tenue: '#898781', tinta: '#1e293b', tinta2: '#52514e',
    lops: ['#86b6ef', '#3987e5', '#1c5cab', '#0d366b']
  };
  E.COLORES = COL;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  E.esc = esc;

  function fmt(n, dec) {
    if (n == null || isNaN(n)) return '–';
    var v = dec == null ? n : Number(n.toFixed(dec));
    return String(v).replace('.', ',');
  }
  E.fmt = fmt;

  function paso(max) {
    if (max <= 0) return 1;
    var bruto = max / 5;
    var mag = Math.pow(10, Math.floor(Math.log10(bruto)));
    var norm = bruto / mag;
    var p = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
    return p * mag;
  }

  function diaCorto(ms) {
    var d = new Date(ms);
    return ('0' + d.getDate()).slice(-2) + '/' + ('0' + (d.getMonth() + 1)).slice(-2);
  }

  // ------------------------------------------------------------------ evolución
  E.svg = E.svg || {};
  E.svg.evolucion = function (serie, opciones) {
    var compacto = !!(opciones && opciones.compacto); // celular: viewBox angosto para que el texto no quede diminuto
    var W = compacto ? 380 : 760, H = compacto ? 250 : 280, ml = compacto ? 40 : 48, mr = compacto ? 12 : 20, mt = 16, mb = 40;
    var iw = W - ml - mr, ih = H - mt - mb;
    if (!serie || !serie.length) return '';
    var maxY = 0;
    serie.forEach(function (p) { maxY = Math.max(maxY, Number(p.score) || 0, Number(p.raw) || 0); });
    var st = paso(maxY || 1);
    var topY = Math.max(st, Math.ceil(maxY / st) * st);
    var fechas = serie.map(function (p) { return p.fecha; });
    var fmin = Math.min.apply(null, fechas), fmax = Math.max.apply(null, fechas);
    var porOrden = fmax === fmin;
    function X(p, i) {
      if (porOrden) return ml + (serie.length === 1 ? iw / 2 : iw * i / (serie.length - 1));
      return ml + iw * (p.fecha - fmin) / (fmax - fmin);
    }
    function Y(v) { return mt + ih - ih * (Number(v) || 0) / topY; }
    var o = [];
    o.push('<svg class="rcj-grafico" viewBox="0 0 ' + W + ' ' + H + '" width="100%" role="img" aria-label="Evolución de score y raw score por fecha" xmlns="http://www.w3.org/2000/svg" style="max-width:' + W + 'px">');
    // grilla y eje Y
    for (var v = 0; v <= topY + 1e-9; v += st) {
      var y = Y(v);
      o.push('<line x1="' + ml + '" x2="' + (W - mr) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" stroke="' + (v === 0 ? COL.eje : COL.grilla) + '" stroke-width="1"/>');
      o.push('<text x="' + (ml - 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="end" font-size="11" fill="' + COL.tenue + '" style="font-variant-numeric:tabular-nums">' + esc(fmt(v)) + '</text>');
    }
    // ticks X (hasta 6)
    var nt = Math.min(compacto ? 4 : 6, serie.length);
    var usados = {};
    for (var t = 0; t < nt; t++) {
      var idx = nt === 1 ? 0 : Math.round(t * (serie.length - 1) / (nt - 1));
      var p = serie[idx];
      var x = X(p, idx);
      var etiqueta = porOrden ? '#' + (idx + 1) : diaCorto(p.fecha);
      if (usados[etiqueta]) continue;
      usados[etiqueta] = true;
      o.push('<text x="' + x.toFixed(1) + '" y="' + (H - mb + 18) + '" text-anchor="middle" font-size="11" fill="' + COL.tenue + '">' + esc(etiqueta) + '</text>');
    }
    o.push('<text x="' + (ml + iw / 2) + '" y="' + (H - 6) + '" text-anchor="middle" font-size="11" fill="' + COL.tenue + '">' + (porOrden ? 'corrida (misma fecha)' : 'fecha') + '</text>');
    // líneas
    [['raw', COL.raw], ['score', COL.score]].forEach(function (s) {
      var d = serie.map(function (p, i) { return (i ? 'L' : 'M') + X(p, i).toFixed(1) + ' ' + Y(p[s[0]]).toFixed(1); }).join(' ');
      o.push('<path d="' + d + '" fill="none" stroke="' + s[1] + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" class="serie-' + s[0] + '"/>');
    });
    // marcadores con anillo de superficie y <title>
    serie.forEach(function (p, i) {
      var x = X(p, i);
      var titulo = E.fechaTexto(p.fecha, true) + ' · ' + p.equipo + (p.ronda ? ' · ' + p.ronda : '') + '\nscore ' + fmt(p.score) + ' · raw ' + fmt(p.raw);
      o.push('<g class="punto" data-i="' + i + '" data-x="' + x.toFixed(1) + '" data-run="' + esc(p.runId) + '">');
      o.push('<title>' + esc(titulo) + '</title>');
      o.push('<circle cx="' + x.toFixed(1) + '" cy="' + Y(p.raw).toFixed(1) + '" r="4" fill="' + COL.raw + '" stroke="' + COL.superficie + '" stroke-width="2"/>');
      o.push('<circle cx="' + x.toFixed(1) + '" cy="' + Y(p.score).toFixed(1) + '" r="4" fill="' + COL.score + '" stroke="' + COL.superficie + '" stroke-width="2"/>');
      o.push('<circle cx="' + x.toFixed(1) + '" cy="' + Y(Math.max(p.score, p.raw) / 2).toFixed(1) + '" r="14" fill="transparent"/>');
      o.push('</g>');
    });
    o.push('<line class="cruz" x1="0" x2="0" y1="' + mt + '" y2="' + (mt + ih) + '" stroke="' + COL.tenue + '" stroke-width="1" visibility="hidden"/>');
    o.push('<rect class="capa-hover" x="' + ml + '" y="' + mt + '" width="' + iw + '" height="' + ih + '" fill="transparent"/>');
    o.push('</svg>');
    return o.join('');
  };

  // ------------------------------------------------------------------ LoPs por tramo
  E.svg.lopsTramos = function (tramos, opciones) {
    if (!tramos || !tramos.length) return '';
    // compacto (celular): nombre arriba, barra a todo el ancho y promedio debajo
    var compacto = !!(opciones && opciones.compacto);
    var W = compacto ? 380 : 760, fila = compacto ? 68 : 44, mt = 8, lw = compacto ? 0 : 190, bw = compacto ? 378 : 440, alto = 20;
    var H = mt + tramos.length * fila + 4;
    var o = ['<svg class="rcj-grafico" viewBox="0 0 ' + W + ' ' + H + '" width="100%" role="img" aria-label="Distribución de LoPs por tramo" xmlns="http://www.w3.org/2000/svg" style="max-width:' + W + 'px">'];
    var claves = ['0', '1', '2', '3+'];
    tramos.forEach(function (tr, i) {
      var y0 = mt + i * fila;
      var yb = compacto ? y0 + 22 : y0 + (fila - alto) / 2;
      o.push('<text x="0" y="' + (compacto ? y0 + 14 : y0 + (tr.esZona ? 17 : 26)) + '" font-size="13" font-weight="700" fill="' + COL.tinta + '">' + esc(tr.nombre) + '</text>');
      if (tr.esZona) {
        var zx = compacto ? W - 134 : 0, zy = compacto ? y0 + 1 : y0 + 23;
        o.push('<rect x="' + zx + '" y="' + zy + '" width="132" height="16" rx="8" fill="#fef3c7" stroke="#f59e0b" stroke-width="1"/>');
        o.push('<text x="' + (zx + 66) + '" y="' + (zy + 12) + '" text-anchor="middle" font-size="10" font-weight="700" fill="#92400e" class="marca-zona">ZONA DE EVACUACIÓN</text>');
      }
      var n = tr.n || 0;
      o.push('<clipPath id="clip-tramo-' + i + '"><rect x="' + lw + '" y="' + yb + '" width="' + bw + '" height="' + alto + '" rx="4"/></clipPath>');
      if (!n) {
        o.push('<rect x="' + lw + '" y="' + yb + '" width="' + bw + '" height="' + alto + '" rx="4" fill="#f1f5f9"/>');
      } else {
        var x = lw;
        o.push('<g clip-path="url(#clip-tramo-' + i + ')">');
        claves.forEach(function (k, j) {
          var c = tr.distribucion[k] || 0;
          if (!c) return;
          var w = bw * c / n;
          var ancho = Math.max(0, w - (x + w < lw + bw - 0.5 ? 2 : 0));
          o.push('<rect x="' + x.toFixed(1) + '" y="' + yb + '" width="' + ancho.toFixed(1) + '" height="' + alto + '" fill="' + COL.lops[j] + '"><title>' + esc(tr.nombre + ': ' + c + ' de ' + n + ' corridas con ' + k + ' LoP' + (k === '1' ? '' : 's')) + '</title></rect>');
          if (ancho >= 26) {
            o.push('<text x="' + (x + ancho / 2).toFixed(1) + '" y="' + (yb + 14) + '" text-anchor="middle" font-size="11" font-weight="700" fill="' + (j === 0 ? COL.tinta : '#ffffff') + '">' + c + '</text>');
          }
          x += w;
        });
        o.push('</g>');
      }
      o.push('<text x="' + (compacto ? 0 : lw + bw + 14) + '" y="' + (compacto ? yb + alto + 16 : y0 + 26) + '" font-size="12" fill="' + COL.tinta2 + '" style="font-variant-numeric:tabular-nums">prom. ' + esc(fmt(tr.promedio, 2)) + ' · máx. ' + esc(fmt(tr.maximo)) + '</text>');
    });
    o.push('</svg>');
    return o.join('');
  };

  // ------------------------------------------------------------------ tira del recorrido
  E.svg.tira = function (heat) {
    if (!heat || !heat.indices.length) return '';
    var mapa = heat.mapa;
    var celda = 34, sep = 2, ml = 4, yBanda = 4, hBanda = 20, yCelda = 30;
    var n = heat.indices.length;
    var zonaGap = mapa.zonaDespuesDe >= 0 ? 14 : 0;
    function X(i) { return ml + i * (celda + sep) + (mapa.zonaDespuesDe >= 0 && i > mapa.zonaDespuesDe ? zonaGap : 0); }
    var W = X(n - 1) + celda + ml;
    var H = yCelda + celda + 34;
    var o = ['<svg class="rcj-grafico rcj-tira" viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '" role="img" aria-label="Recorrido por índice" xmlns="http://www.w3.org/2000/svg">'];
    // bandas de tramo
    mapa.tramos.forEach(function (tr) {
      var idx = heat.indices.filter(function (d) { return d.tramo === tr.k; }).map(function (d) { return d.indice; });
      if (!idx.length) return;
      var x0 = X(Math.min.apply(null, idx)), x1 = X(Math.max.apply(null, idx)) + celda;
      o.push('<rect x="' + x0 + '" y="' + yBanda + '" width="' + (x1 - x0) + '" height="' + hBanda + '" rx="4" fill="' + (tr.esZona ? '#fef3c7' : (tr.k % 2 ? '#eef2f7' : '#f8fafc')) + '" stroke="' + (tr.esZona ? '#f59e0b' : '#e2e8f0') + '" stroke-width="1"/>');
      o.push('<text x="' + ((x0 + x1) / 2) + '" y="' + (yBanda + 14) + '" text-anchor="middle" font-size="10" font-weight="700" fill="' + (tr.esZona ? '#92400e' : COL.tinta2) + '">' + esc(tr.nombre + (tr.esZona ? ' · zona' : '')) + '</text>');
    });
    if (mapa.zonaDespuesDe >= 0) {
      var xz = X(mapa.zonaDespuesDe) + celda + (sep + zonaGap) / 2;
      o.push('<rect class="marca-zona" x="' + (xz - 3) + '" y="' + (yCelda - 2) + '" width="6" height="' + (celda + 4) + '" rx="3" fill="#f59e0b"><title>Zona de evacuación (salto al reinicio)</title></rect>');
    }
    heat.indices.forEach(function (d) {
      var x = X(d.indice);
      var pct = d.total.pct;
      var fondo = pct == null ? '#f1f5f9' : E.colorExito(pct);
      var titulo = 'Índice ' + d.indice + ' · ' + (mapa.tramos[d.tramo] ? mapa.tramos[d.tramo].nombre : '') + (d.key ? ' · baldosa ' + d.key : '');
      d.lista.forEach(function (c) { titulo += '\n' + c.nombre + ': ' + c.logrados + '/' + c.intentos + ' (' + fmt(c.pct, 1) + ' %)'; });
      if (!d.lista.length) titulo += '\nsin elementos puntuables';
      o.push('<g class="celda-indice" data-indice="' + d.indice + '" data-key="' + esc(d.key || '') + '" style="cursor:pointer">');
      o.push('<title>' + esc(titulo) + '</title>');
      o.push('<rect x="' + x + '" y="' + yCelda + '" width="' + celda + '" height="' + celda + '" rx="4" fill="' + fondo + '"/>');
      if (pct != null) {
        o.push('<text x="' + (x + celda / 2) + '" y="' + (yCelda + 21) + '" text-anchor="middle" font-size="10" font-weight="700" fill="' + E.tintaSobre(pct) + '">' + Math.round(pct) + '</text>');
      } else {
        o.push('<text x="' + (x + celda / 2) + '" y="' + (yCelda + 21) + '" text-anchor="middle" font-size="10" fill="' + COL.tenue + '">–</text>');
      }
      o.push('<text x="' + (x + celda / 2) + '" y="' + (yCelda + celda + 13) + '" text-anchor="middle" font-size="10" fill="' + COL.tenue + '">' + d.indice + '</text>');
      if (d.numeroCheckpoint) {
        o.push('<text x="' + (x + celda / 2) + '" y="' + (yCelda + celda + 26) + '" text-anchor="middle" font-size="10" font-weight="700" fill="#d97706">CP' + d.numeroCheckpoint + '</text>');
      }
      o.push('</g>');
    });
    o.push('</svg>');
    return o.join('');
  };

  // ------------------------------------------------------------------ leyenda de la escala
  E.svg.leyendaEscala = function () {
    var W = 260, H = 34;
    var o = ['<svg viewBox="0 0 ' + W + ' ' + H + '" width="' + W + '" height="' + H + '" role="img" aria-label="Escala: claro 100 % de éxito, oscuro 0 % de éxito" xmlns="http://www.w3.org/2000/svg">'];
    o.push('<defs><linearGradient id="grad-exito" x1="0" x2="1" y1="0" y2="0">');
    [100, 75, 50, 25, 0].forEach(function (p, i) {
      o.push('<stop offset="' + (i * 25) + '%" stop-color="' + E.colorExito(p) + '"/>');
    });
    o.push('</linearGradient></defs>');
    o.push('<rect x="1" y="2" width="' + (W - 2) + '" height="12" rx="4" fill="url(#grad-exito)"/>');
    o.push('<text x="1" y="30" font-size="11" fill="' + COL.tinta2 + '">100 % éxito</text>');
    o.push('<text x="' + (W / 2) + '" y="30" text-anchor="middle" font-size="11" fill="' + COL.tinta2 + '">50 %</text>');
    o.push('<text x="' + (W - 1) + '" y="30" text-anchor="end" font-size="11" fill="' + COL.tinta2 + '">0 % (falla siempre)</text>');
    o.push('</svg>');
    return o.join('');
  };
})(window);

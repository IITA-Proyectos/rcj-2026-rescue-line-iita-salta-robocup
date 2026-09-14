/*
 * rcj-line-offline — área estadísticas.
 * RCJEstadisticas.csv: exportación de la tabla de corridas y de los elementos por pasada.
 *   formato 'excel'    -> separador ';', coma decimal, BOM UTF-8, CRLF (Excel en español abre directo)
 *   formato 'estandar' -> separador ',', punto decimal, sin BOM, CRLF (RFC 4180)
 * En el formato Excel, los textos que empiezan con = + - @ (o tab/CR) llevan un apóstrofo delante para que
 * Excel no los interprete como fórmula (inyección CSV). Los números nunca se tocan.
 */
(function (global) {
  'use strict';

  var E = global.RCJEstadisticas = global.RCJEstadisticas || {};

  var FORMATOS = {
    excel: { sep: ';', decimal: ',', bom: true, protegerFormulas: true },
    estandar: { sep: ',', decimal: '.', bom: false, protegerFormulas: false }
  };

  function numero(n, fmt, decimales) {
    if (n == null || typeof n !== 'number' || isNaN(n)) return '';
    var v = decimales == null ? n : Number(n.toFixed(decimales));
    var s = String(v);
    return fmt.decimal === ',' ? s.replace('.', ',') : s;
  }

  function texto(v, fmt) {
    var s = v == null ? '' : String(v);
    if (fmt.protegerFormulas && /^[=+\-@\t\r]/.test(s)) s = "'" + s;
    return s;
  }

  function celda(v, fmt) {
    // v: {n, dec} para números; cualquier otra cosa es texto
    var s = (v && typeof v === 'object' && 'n' in v) ? numero(v.n, fmt, v.dec) : texto(v, fmt);
    if (s.indexOf(fmt.sep) >= 0 || s.indexOf('"') >= 0 || /[\r\n]/.test(s) || /^\s|\s$/.test(s)) {
      s = '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  function armar(filas, formato) {
    var fmt = FORMATOS[formato] || FORMATOS.estandar;
    var out = filas.map(function (fila) {
      return fila.map(function (v) { return celda(v, fmt); }).join(fmt.sep);
    }).join('\r\n') + '\r\n';
    return (fmt.bom ? '﻿' : '') + out;
  }

  function N(n, dec) { return { n: n, dec: dec }; }

  function nombreEstado(status) {
    var e = (E.ESTADOS || []).filter(function (x) { return x.valor === Number(status); })[0];
    return e ? e.nombre : String(status);
  }

  var COLUMNAS_CORRIDAS = ['fecha', 'equipo', 'ronda', 'cancha', 'mapa', 'estado', 'LoPs por tramo', 'LoPs total',
    'víctimas efectivas', 'víctimas registradas', 'exit bonus', 'tiempo (s)', 'raw guardado', 'multiplicador guardado',
    'score guardado', 'ajuste (%)', 'raw recalculado', 'multiplicador recalculado', 'score recalculado', 'consistente',
    'avisos', 'id'];

  function filasCorridas(resultado) {
    var filas = [COLUMNAS_CORRIDAS.slice()];
    resultado.corridas.forEach(function (a) {
      var rc = a.recalculado;
      filas.push([
        E.fechaTexto(a.fecha, true), a.equipo, a.ronda, a.cancha, a.mapa, nombreEstado(a.status),
        a.LoPs.join('|'), N(a.desglose ? a.desglose.lopsTotal : null),
        N(a.victimas ? a.victimas.efectivas : null), N(a.victimas ? a.victimas.registradas : null),
        a.exitBonus ? 'sí' : 'no', N(a.tiempo),
        N(a.guardado.raw_score), N(a.guardado.multiplier), N(a.guardado.score), N(a.guardado.adjustment),
        N(rc ? rc.raw_score : null), N(rc ? rc.multiplier : null), N(rc ? rc.score : null),
        a.consistente === true ? 'sí' : (a.consistente === false ? 'no' : ''),
        a.avisos.join(' / '), a._id
      ]);
    });
    return filas;
  }

  var COLUMNAS_PASADAS = ['mapa', 'índice', 'baldosa (x,y,z)', 'tramo', 'elemento', 'intentos', 'logrados', '% éxito',
    'puntos posibles', 'puntos obtenidos', 'puntos perdidos'];

  function filasPasadas(resultado) {
    var filas = [COLUMNAS_PASADAS.slice()];
    if (!resultado.heat) return filas;
    var mapa = resultado.heat.mapa;
    resultado.heat.indices.forEach(function (d) {
      d.lista.forEach(function (c) {
        filas.push([mapa.name, N(d.indice), d.key || '', mapa.tramos[d.tramo] ? mapa.tramos[d.tramo].nombre : '',
          c.nombre, N(c.intentos), N(c.logrados), N(c.pct, 1), N(c.posibles), N(c.obtenidos), N(c.perdidos)]);
      });
    });
    return filas;
  }

  E.csv = {
    formatos: FORMATOS,
    armar: armar,
    numero: function (n, formato, dec) { return numero(n, FORMATOS[formato] || FORMATOS.estandar, dec); },
    filasCorridas: filasCorridas,
    filasPasadas: filasPasadas,
    corridas: function (resultado, formato) { return armar(filasCorridas(resultado), formato); },
    pasadas: function (resultado, formato) { return armar(filasPasadas(resultado), formato); },
    /** Descarga el texto como archivo (Blob + <a download>). Devuelve el nombre usado. */
    descargar: function (textoCsv, nombre) {
      var blob = new Blob([textoCsv], { type: 'text/csv;charset=utf-8' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = nombre;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 1000);
      return nombre;
    }
  };
})(window);

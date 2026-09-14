/*
 * rcj-line-offline — área salidas.
 * Planilla PDF 2026 (E8 scoresheet, export type=scoresheets y runs/line/scoresheet2):
 * port de helper/scoreSheetUtil.js, helper/scoreSheetPDFUtil.js,
 * helper/scoreSheetPDFLineRules/2026.js y helper/scoreSheetPDFLine2.js (CMS d805502).
 * Sin cambios de lógica (marcas VERBATIM, tests/salidas-verbatim.py). Mismas coordenadas en pt,
 * fuente estándar Helvetica (la carpeta fonts/ del CMS está vacía), QR "L;<runId>" con
 * qrcode-generator. Título "${competition.name}  Rescue Line": desde el editor sale
 * "Competition" (C6), porque scoreSheetPDFLine2.js:72 lee map.competition.name.
 *
 * Adaptaciones de entorno (local/render/comun.js): pdfkit standalone lee 'ruta.png' del fs local
 * (estáticos precargados + tmp/course en memoria), qr-image, glob, guesslanguage y process.env.
 * Solo existe la regla 2026 (readdirSync devuelve ['2026.js']).
 */
(function (global) {
  var S = global.RCJLocal && global.RCJLocal.salidas;
  if (!S || !S.comun) throw new Error('local/render/planilla-pdf.js: falta local/render/comun.js (incluir solo local/render/registrar.js)');
  var C = S.comun;

  // ---------------------------------------------------------------- helper/scoreSheetUtil.js
  var mUtil = C.modulo('helper/scoreSheetUtil');
  (function (module, exports, require, __dirname, __filename) {
// ===== INICIO VERBATIM helper/scoreSheetUtil.js:1-19 =====
/**
 * Defines four orientations
 * @type {Readonly<{RIGHT: number, BOTTOM: number, LEFT: number, TOP: number}>}
 */
const DirsEnum = Object.freeze({ RIGHT: 1, BOTTOM: 2, LEFT: 3, TOP: 4 });
module.exports.DirsEnum = DirsEnum;

const InputTypeEnum = Object.freeze({
  FIELD: 'fld',
  FIELDTILE: 'fldtl',
  POSMARK: 'pos',
  CHECKBOX: 'cb',
  TEXT: 'txt',
  MATRIXROW: 'mrow',
  MATRIX: 'm',
  MATRIXTEXT: 'mt',
  QR: 'qr',
});
module.exports.InputTypeEnum = InputTypeEnum;
// ===== FIN VERBATIM helper/scoreSheetUtil.js:1-19 =====
  })(mUtil, mUtil.exports, C.requireDe({}), 'helper', 'helper/scoreSheetUtil.js');
  C.publicar(mUtil);

  // ---------------------------------------------------------------- helper/scoreSheetPDFUtil.js
  var mPdfUtil = C.modulo('helper/scoreSheetPDFUtil');
  (function (module, exports, require, __dirname, __filename) {
// ===== INICIO VERBATIM helper/scoreSheetPDFUtil.js:1-53 =====
const qr = require('qr-image');
const defs = require('./scoreSheetUtil');

/**
 * Draws a checkbox with text
 * @param doc The document to draw the checkbox in
 * @param pos_x absolute x-position
 * @param pos_y absolute y-position
 * @param size size of the checkbox
 * @param text text to be shown next to the checkbox (no text if empty string)
 * @param dir direction of the checkbox where the text should be shown
 * @param color
 */

module.exports.drawText = function (doc, pos_x, pos_y, text, size, color) {
  doc.fontSize(size).fillColor(color).text(text, pos_x, pos_y);
};

module.exports.drawTextWithAlign = function (
  doc,
  pos_x,
  pos_y,
  text,
  size,
  color,
  width,
  align
) {
  doc
    .fontSize(size)
    .fillColor(color)
    .text(text, pos_x, pos_y, { width, align });
};

module.exports.drawImage = function (
  doc,
  pos_x,
  pos_y,
  uri,
  width,
  height,
  align,
  rot = 0
) {
  doc
    .rotate(rot, { origin: [pos_x + width / 2, pos_y + height / 2] })
    .image(uri, pos_x, pos_y, { fit: [width, height], align });
  doc.rotate(-rot, { origin: [pos_x + width / 2, pos_y + height / 2] });
};

module.exports.drawRectangle = function (doc, pos_x, pos_y, width, height) {
  doc.rect(pos_x, pos_y, width, height).lineWidth(0.3).stroke();
};
// ===== FIN VERBATIM helper/scoreSheetPDFUtil.js:1-53 =====
  })(mPdfUtil, mPdfUtil.exports, C.requireDe({
    'qr-image': C.qrImage,
    './scoreSheetUtil': 'helper/scoreSheetUtil'
  }), 'helper', 'helper/scoreSheetPDFUtil.js');
  C.publicar(mPdfUtil);

  // ---------------------------------------------------------------- helper/scoreSheetPDFLineRules/2026.js
  var mRegla = C.modulo('helper/scoreSheetPDFLineRules/2026');
  (function (module, exports, require, __dirname, __filename, process) {
// ===== INICIO VERBATIM helper/scoreSheetPDFLineRules/2026.js:1-461 =====
const PDFDocument = require('pdfkit');
const pdf = require('../scoreSheetPDFUtil');
const qr = require('qr-image');
const fs = require('fs');
const { guessLanguage } = require('guesslanguage/lib/guessLanguage');
const glob = require('glob');
/**
 * Defines some important numbers for the placement of different objects in the scoresheet.
 */
const globalConfig = {
  paperSize: { x: 841.89, y: 595.28 },
};

function isExistFile(file) {
  try {
    fs.statSync(file);
    return true;
  } catch (err) {
    if (err.code === 'ENOENT') return false;
  }
}

function guessLanguagePromise(text) {
  return new Promise((resolve) => {
    guessLanguage.name(text, (name) => {
      return resolve(name);
    });
  });
}

function getFontPath(lang) {
  const list = glob.sync(`${__dirname}/../fonts/${lang}*`);
  if (list.length > 0) {
    return list[0];
  }
  return null;
}

async function drawRun(doc, config, scoringRun) {
  // Set template image as a background
  pdf.drawImage(
    doc,
    0,
    0,
    'scoresheet_generation/line/base2024.png',
    841.89,
    595.28,
    'center'
  );

  // Draw competition name & logo
  pdf.drawTextWithAlign(
    doc,
    90,
    15,
    `${scoringRun.competition.name}  Rescue Line`,
    20,
    'black',
    660,
    'center'
  );

  if (
    scoringRun.competition.logo != '' &&
    scoringRun.competition.logo != '/images/noLogo.png'
  )
    pdf.drawImage(doc, 730, 5, scoringRun.competition.logo, 100, 30, 'right');
  else pdf.drawImage(doc, 730, 5, 'public/images/logo.png', 100, 30, 'right');

  // Draw run QR code
  if (scoringRun._id && scoringRun._id.toString() !== '000000000000000000000000' && !scoringRun.noQR) {
    doc.image(
      qr.imageSync(`L;${scoringRun._id.toString()}`, { margin: 2 }),
      10,
      10,
      { width: 70 }
    );
  }

  let drawTeamName = scoringRun.team.name;
  if (scoringRun.team.teamCode) {
    drawTeamName = `${scoringRun.team.teamCode} ${drawTeamName}`
  }
  // Draw team name
  pdf.drawTextWithAlign(
    doc,
    124,
    41,
    drawTeamName,
    15,
    'black',
    310,
    'center'
  );

  // Draw start time
  if (scoringRun.startTime) {
    const dateTime = new Date(scoringRun.startTime);
    pdf.drawTextWithAlign(
      doc,
      124,
      60,
      `${`0${dateTime.getUTCHours()}`.slice(-2)}:${`0${dateTime.getUTCMinutes()}`.slice(
        -2
      )}`,
      15,
      'black',
      68,
      'center'
    );
  }

  // Draw round name
  pdf.drawTextWithAlign(
    doc,
    227,
    60,
    scoringRun.round.name,
    15,
    'black',
    103,
    'center'
  );

  // Draw field name
  pdf.drawTextWithAlign(
    doc,
    365,
    60,
    scoringRun.field.name,
    15,
    'black',
    70,
    'center'
  );

  // Draw map image
  if (scoringRun.mapImageBuffer) {
    pdf.drawImage(
      doc,
      20,
      85,
      scoringRun.mapImageBuffer,
      413,
      485,
      'center'
    );
  } else if (isExistFile(`${__dirname}/../../tmp/course/${scoringRun.map._id}.png`)) {
    pdf.drawImage(
      doc,
      20,
      85,
      `tmp/course/${scoringRun.map._id}.png`,
      413,
      485,
      'center'
    );
  }

  // System version
  pdf.drawText(doc, 20, 580, `©${process.env.cms_copyright}. This score sheet was generated with RCJ CMS v${process.env.cms_version}`, 8, 'black');

  let x = 440;
  let y = 35;

  // Draw box of the start tile

  // Simulate before render
  const tiles = [];
  let index = 1;
  let base_size_x = 95;
  let base_size_y = 36;

  y += base_size_y; // Start tile
  while (1) {
    const tile = getTileInfo(scoringRun.map.tiles, index);
    if (tile == null) break;
    if (tile.checkPoint) {
      if (y > 330 - base_size_y * 2) {
        x += base_size_x;
        y = 35;
      }
      y += base_size_y * 2;
      if (y > 330 - base_size_y) {
        x += base_size_x;
        y = 35;
      }
      const t = structuredClone(tile);
      t.nowIndex = index;
      tiles.push(t);
    }
    if (
      tile.tileType.gaps ||
      tile.tileType.intersections ||
      tile.tileType.seesaw ||
      tile.items.obstacles ||
      tile.items.speedbumps ||
      tile.items.rampPoints
    ) {
      const t = structuredClone(tile);
      t.nowIndex = index;
      t.isElement = true;
      tiles.push(t);
      y += base_size_y;
      if (y > 330 - base_size_y) {
        x += base_size_x;
        y = 35;
      }
    }

    index++;
  }

  y += base_size_y; // LoP after final checkpoint
  if (y > 330 - base_size_y) {
    x += base_size_x;
    y = 35;
  }

  let text_padding = 10;
  switch (x) {
    case 820:
      if (y > 35) {
        base_size_x = 76;
        base_size_y = 29;
        text_padding = 7;
      }
      break;
    case 915:
      base_size_x = 76;
      base_size_y = 29;
      text_padding = 7;
    default:
      break;
  }

  x = 440;
  y = 35;

  const startColor = '#ff9f43';

  pdf.drawImage(
    doc,
    x,
    y,
    'scoresheet_generation/line/start.png',
    base_size_x,
    50,
    'center'
  );
  pdf.drawTextWithAlign(
    doc,
    x,
    y + text_padding,
    1,
    20,
    startColor,
    base_size_y,
    'center'
  );
  y += base_size_y;

  let checkPointNum = 0;
  for (const tile of tiles) {
    const item = [];
    if (tile.checkPoint && !tile.isElement) {
      if (y > 330 - base_size_y * 2) {
        x += base_size_x;
        y = 35;
      }
      if (scoringRun.map.EvacuationAreaLoPIndex == checkPointNum) {
        pdf.drawImage(
          doc,
          x,
          y,
          'scoresheet_generation/line/checkpointE.png',
          base_size_x,
          100,
          'center'
        );
        pdf.drawTextWithAlign(
          doc,
          x,
          y + text_padding,
          tile.nowIndex + 1,
          20,
          '#ee5253',
          base_size_y,
          'center'
        );
      } else {
        pdf.drawImage(
          doc,
          x,
          y,
          'scoresheet_generation/line/checkpoint.png',
          base_size_x,
          100,
          'center'
        );
        pdf.drawTextWithAlign(
          doc,
          x,
          y + text_padding,
          tile.nowIndex + 1,
          20,
          '#ff9f43',
          base_size_y,
          'center'
        );
      }
      checkPointNum++;

      y += base_size_y * 2;
      if (y > 330 - base_size_y) {
        x += base_size_x;
        y = 35;
      }
    } else {
      if (tile.tileType.gaps) item.push('gap');
      if (tile.tileType.intersections) item.push('intersection');
      if (tile.tileType.seesaw) item.push('seesaw');
      if (tile.items.obstacles) item.push('obstacle');
      if (tile.items.speedbumps) item.push('speedbump');
      if (tile.items.rampPoints) item.push('ramp');

      if (item.length > 0) {
        pdf.drawImage(
          doc,
          x,
          y,
          'scoresheet_generation/line/element.png',
          base_size_x,
          50,
          'center'
        );
        pdf.drawTextWithAlign(
          doc,
          x,
          y + text_padding,
          tile.nowIndex + 1,
          20,
          '#0abde3',
          base_size_y,
          'center'
        );
        const item_x = x + base_size_y + 6;
        const item_y = y + 3;
        pdf.drawImage(
          doc,
          item_x + 3,
          item_y + 3,
          `public/images/tiles/${tile.tileType.image}`,
          base_size_y - 10,
          base_size_y - 10,
          'center',
          tile.rot
        );
        pdf.drawRectangle(
          doc,
          item_x + 3,
          item_y + 3,
          base_size_y - 10,
          base_size_y - 10
        );
        for (const i of item) {
          switch (i) {
            case 'seesaw':
            case 'intersection':
            case 'gap':
              break;
            case 'speedbump':
              pdf.drawImage(
                doc,
                item_x,
                item_y,
                `scoresheet_generation/line/${i}.png`,
                base_size_y - 5,
                base_size_y - 5,
                'center',
                tile.rot
              );
              break;
            default:
              pdf.drawImage(
                doc,
                item_x,
                item_y,
                `scoresheet_generation/line/${i}.png`,
                base_size_y - 5,
                base_size_y - 5,
                'center'
              );
          }
        }
        y += base_size_y;
        if (y > 330 - base_size_y) {
          x += base_size_x;
          y = 35;
        }
      }
    }
    index++;
  }

  const lastTile = getTileInfo(scoringRun.map.tiles, scoringRun.map.indexCount - 1);
  if (scoringRun.map.EvacuationAreaLoPIndex == checkPointNum) {
    pdf.drawImage(
      doc,
      x,
      y,
      'scoresheet_generation/line/after_finalE.png',
      base_size_x,
      50,
      'center'
    );
  } else {
    pdf.drawImage(
      doc,
      x,
      y,
      'scoresheet_generation/line/after_final.png',
      base_size_x,
      50,
      'center'
    );
  }
}

function getTileInfo(tiles, index) {
  for (const t of tiles) {
    for (const i of t.index) {
      if (i == index) return t;
    }
  }
  return null;
}

module.exports.generateScoreSheet = async function (res, rounds) {
  let font = null;
  if (rounds.length > 0) {
    const tmp = await guessLanguagePromise(rounds[0].competition.name);
    font = getFontPath(tmp);
  }

  const doc = new PDFDocument({ autoFirstPage: false });

  doc.pipe(res);

  if (font) doc.font(font);

  for (let i = 0; i < rounds.length; i++) {
    doc.addPage({
      margin: 0,
      size: [globalConfig.paperSize.x, globalConfig.paperSize.y],
    });
    drawRun(doc, globalConfig, rounds[i]);
  }

  doc.end();
};
// ===== FIN VERBATIM helper/scoreSheetPDFLineRules/2026.js:1-461 =====
  })(mRegla, mRegla.exports, C.requireDe({
    'pdfkit': C.PDFDocument,
    '../scoreSheetPDFUtil': 'helper/scoreSheetPDFUtil',
    'qr-image': C.qrImage,
    'fs': C.fs,
    'guesslanguage/lib/guessLanguage': C.guessLanguage,
    'glob': C.glob
  }), 'helper/scoreSheetPDFLineRules', 'helper/scoreSheetPDFLineRules/2026.js', C.process);
  C.publicar(mRegla);

  // ---------------------------------------------------------------- helper/scoreSheetPDFLine2.js
  var mLine2 = C.modulo('helper/scoreSheetPDFLine2');
  (function (module, exports, require, __dirname, __filename) {
// ===== INICIO VERBATIM helper/scoreSheetPDFLine2.js:1-100 =====
const rules = {};
const scoreSheetPath = require('path').join(__dirname, 'scoreSheetPDFLineRules');

let supportedRules = [];
require('fs')
  .readdirSync(scoreSheetPath)
  .forEach((file) => {
    const name = file.replace(/\.js$/, '');
    rules[name] = require(`./scoreSheetPDFLineRules/${file}`);
    supportedRules.push(name);
  });

const lineSSR = require('./lineSSR');
const fs = require('fs');
const path = require('path');

async function ensureMapImages(runs) {
  const tmpDir = path.join(__dirname, '../tmp/course');
  if (!fs.existsSync(tmpDir)) {
    fs.mkdirSync(tmpDir, { recursive: true });
  }

  const mapKeys = new Set();
  for (const run of runs) {
    if (run.map) {
      const mapKey = run.map._id ? run.map._id.toString() : `inline-${runs.indexOf(run)}`;
      if (!mapKeys.has(mapKey)) {
        mapKeys.add(mapKey);
        let rule = '2026';
        if (run.competition && run.competition.leagues && run.team) {
          const league = run.competition.leagues.find((l) => l.league == run.team.league);
          if (league) rule = league.rule;
        }

        run.mapImageBuffer = await lineSSR.generatePNG(run.map, rule);
        if (!run.map._id) continue;

        const buffer = run.mapImageBuffer;
        fs.writeFileSync(path.join(tmpDir, `${run.map._id}.png`), buffer);
      } else if (run.map._id) {
        const existingPath = path.join(tmpDir, `${run.map._id}.png`);
        if (fs.existsSync(existingPath)) run.mapImageBuffer = fs.readFileSync(existingPath);
      }
    }
  }
}

module.exports.generateScoreSheet = async function (res, runs) {
  await ensureMapImages(runs);
  if (runs.length > 0) {
    let run = runs[0];
    const league = run.competition.leagues.find((l) => l.league == run.team.league);
    return rules[league.rule].generateScoreSheet(res, runs)
  }
  return rules[supportedRules[0]].generateScoreSheet(res, runs)
};

module.exports.generateScoreSheetsFromMaps = async function (res, maps, rule, noQR = false) {
  const dummyRuns = maps.map(map => {
    // Normalize tiles if they are in object format from the frontend
    let normalizedTiles = map.tiles;
    if (map.tiles && !Array.isArray(map.tiles)) {
      normalizedTiles = Object.entries(map.tiles).map(([key, tile]) => {
        const [x, y, z] = key.split(',').map(Number);
        return { ...tile, x, y, z };
      });
    }

    return {
      _id: map._id || '000000000000000000000000',
      competition: {
        name: (map.competition && map.competition.name) || 'Competition',
        logo: (map.competition && map.competition.logo) || '',
        leagues: [{
          league: map.league || 'Line',
          rule: rule
        }]
      },
      team: {
        name: '',
        teamCode: '',
        league: map.league || 'Line',
      },
      startTime: null,
      round: { name: '' },
      field: { name: '' },
      map: {
        ...map,
        tiles: normalizedTiles
      },
      noQR: noQR || map.noQR,
    };
  });

  return await module.exports.generateScoreSheet(res, dummyRuns);
};

module.exports.generateScoreSheetFromMap = async function (res, map, rule) {
  return await module.exports.generateScoreSheetsFromMaps(res, [map], rule, map.noQR);
};
// ===== FIN VERBATIM helper/scoreSheetPDFLine2.js:1-100 =====
  })(mLine2, mLine2.exports, C.requireDe({
    'path': C.path,
    'fs': C.fs,
    './scoreSheetPDFLineRules/2026.js': 'helper/scoreSheetPDFLineRules/2026',
    './lineSSR': 'helper/lineSSR'
  }), 'helper', 'helper/scoreSheetPDFLine2.js');
  C.publicar(mLine2);

  S.modulosCargados = S.modulosCargados || {};
  S.modulosCargados['local/render/planilla-pdf.js'] = true;
})(window);

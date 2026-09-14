/*
 * rcj-line-offline — área backend.
 * RCJLocal.ranking: port de routes/api/ranking.js:22-228 (handler de Line) del CMS (commit d805502)
 * sobre IndexedDB. sortRuns, sortRunsNormalized, sortFinalScore y sum (ranking.js:607-666) van
 * VERBATIM. Decimal.js se reemplaza por RCJLocal._Decimal (misma precisión y redondeo).
 *
 * Modos soportados (D9): SUM_OF_BEST_N_GAMES y MEAN_OF_NORMALIZED_BEST_N_GAMES. Los modos con
 * documentos o Technical Challenge quedan fuera de v1 (D8) y responden 400.
 *
 * Extensión nueva (no está en el CMS): query `?desempate=6.1.8` (alias `reglamento`) desempata
 * empates de finalScore por la media de field scores normalizados de las rondas usadas
 * (reglamento 2026 §6.1.8) antes de caer al desempate por tiempo del CMS. Agrega
 * `result.desempate = '6.1.8'` y `ranking[i].desempate6118` (número).
 */
(function () {
  'use strict';

  var R = window.RCJLocal = window.RCJLocal || {};

// ===== INICIO VERBATIM routes/api/ranking.js:607-666 (rcj-rescue-cms d805502) =====
function sortRuns(a, b) {
  if (a.score == b.score) {
      if (a.time.minutes < b.time.minutes) {
          return -1
      } else if (a.time.minutes > b.time.minutes) {
          return 1
      } else if (a.time.seconds < b.time.seconds) {
          return -1
      } else if (a.time.seconds > b.time.seconds) {
          return 1
      } else {
          return 0
      }
  } else {
      return b.score - a.score
  }
}

function sortRunsNormalized(a, b) {
  if (a.normalizedScore == b.normalizedScore) {
      if (a.time.minutes < b.time.minutes) {
          return -1
      } else if (a.time.minutes > b.time.minutes) {
          return 1
      } else if (a.time.seconds < b.time.seconds) {
          return -1
      } else if (a.time.seconds > b.time.seconds) {
          return 1
      } else {
          return 0
      }
  } else {
      return b.normalizedScore - a.normalizedScore
  }
}

function sortFinalScore(a, b) {
  if (a.finalScore == b.finalScore) {
      if (a.gameSum.time.minutes < b.gameSum.time.minutes) {
          return -1
      } else if (a.gameSum.time.minutes > b.gameSum.time.minutes) {
          return 1
      } else if (a.gameSum.time.seconds < b.gameSum.time.seconds) {
          return -1
      } else if (a.gameSum.time.seconds > b.gameSum.time.seconds) {
          return 1
      } else {
          return 0
      }
  } else {
      return b.finalScore - a.finalScore
  }
}

function sum(array) {
  if (array.length == 0) return 0;
  return array.reduce(function(a, b) {
    return Number(a) + Number(b);
  }, 0);
}
// ===== FIN VERBATIM routes/api/ranking.js:607-666 =====


  function idConsulta(v) {
    return R._mongoose ? (function () { try { return R._mongoose.CAST.ObjectId(v); } catch (e) { return undefined; } })() : v;
  }
  function seleccionar(doc, campos) {
    var out = {};
    Object.keys(doc).forEach(function (k) {
      if (k === '_id' || campos.indexOf(k) >= 0) out[k] = JSON.parse(JSON.stringify(doc[k]));
    });
    return out;
  }
  function ordenNatural(a, b) {
    var ca = a.createdAt || '', cb = b.createdAt || '';
    if (ca < cb) return -1;
    if (ca > cb) return 1;
    return a._id < b._id ? -1 : (a._id > b._id ? 1 : 0);
  }

  /**
   * calcular(t, competition, league, query, util) -> respuesta {status, data, headers}
   * t: transacción de RCJLocal.store; util: {json, noEncontrado} de api.js.
   */
  async function calcular(t, competition, league, query, util) {
    var K = R.constantesCMS;
    var json = util.json;
    query = query || {};

    if (!R.esIdValido(competition)) return util.noEncontrado();
    if (!K.LINE_LEAGUES.includes(league)) return util.noEncontrado();

    let competitionDb = await t.get('competitions', idConsulta(competition));
    if (!competitionDb) return json(400, { msg: 'Could not get competition' }); // original: TypeError sin respuesta
    let rankingSettings = competitionDb.leagues.find(r => r.league == league);
    if (!rankingSettings) {
      rankingSettings = {
        mode: K.SUM_OF_BEST_N_GAMES,
        disclose: false,
        num: 20
      }
    }
    // !disclose && !authCompetition(VIEW): el usuario local tiene acceso
    let sumGameNumber = rankingSettings.num;
    let rankingMode = rankingSettings.mode;

    if (K.DOCUMENT_RANKING_MODE.includes(rankingMode)) {
      return json(400, { msg: 'Modo de ranking no disponible en la versión offline (documentos / Technical Challenge)', mode: rankingMode });
    }

    // lineRun.find({competition}).select(...).populate(team: name teamCode league; round: name).lean()
    let crudas = await t.list('lineRuns', r => r.competition === competitionDb._id);
    crudas.sort(ordenNatural);
    let allRunsDb = [];
    for (let run of crudas) {
      let r = seleccionar(run, ['team', 'score', 'normalizationGroup', 'LoPs', 'rescueOrder', 'nl', 'isNL', 'time', 'startTime', 'round', 'adjustment']);
      if ('team' in r) {
        let team = await t.get('teams', r.team);
        r.team = team ? seleccionar(team, ['name', 'teamCode', 'league']) : null;
      }
      if ('round' in r) {
        let round = await t.get('rounds', r.round);
        r.round = round ? seleccionar(round, ['name']) : null;
      }
      allRunsDb.push(r);
    }

    let allRunsLeague = allRunsDb.filter(r => r.team.league == league);
    let allRounds =[...new Set(allRunsLeague.map(r => r.round.name))].sort();
    let allNormGroups =[...new Set(allRunsLeague.map(r => r.normalizationGroup))].sort();

    // Apply score adjustment
    allRunsLeague.map(run => {
      if (run.adjustment != null) {
        run.score = new R._Decimal(run.score).times((run.adjustment + 100) / 100).toNumber();
      }
    });

    if (K.NORMALIZED_RANKING_MODE.includes(rankingMode)) {
      let normGroups = allRunsLeague.map(r => r.normalizationGroup);
      normGroups = [...new Set(normGroups)];
      let maxScore = {};
      for (let n of normGroups) {
        maxScore[n] = Math.max(...allRunsLeague.filter(run => run.normalizationGroup == n).map(run => run.score))
      }
      allRunsLeague.map(run => {
        if (maxScore[run.normalizationGroup] == 0) run.normalizedScore = 0;
        else run.normalizedScore = run.score / maxScore[run.normalizationGroup];
      })
    }

    // [extensión 6.1.8] normalizado por grupo aunque el modo no sea normalizado, fuera del JSON
    let desempate = query.desempate == '6.1.8' || query.desempate == 'reglamento';
    let normalizado6118 = new Map();
    let mejores6118 = new Map();
    if (desempate) {
      let maxPorGrupo = {};
      for (let n of [...new Set(allRunsLeague.map(r => r.normalizationGroup))]) {
        maxPorGrupo[n] = Math.max(...allRunsLeague.filter(run => run.normalizationGroup == n).map(run => run.score));
      }
      allRunsLeague.forEach(run => {
        normalizado6118.set(run, maxPorGrupo[run.normalizationGroup] == 0 ? 0 : run.score / maxPorGrupo[run.normalizationGroup]);
      });
    }

    let teamRuns = {};
    for (let run of allRunsLeague) {
      if (teamRuns[run.team._id] == null) teamRuns[run.team._id] = { games: [] };
      teamRuns[run.team._id].games.push(run);
    }

    Object.keys(teamRuns).map(e => {
      teamRuns[e].gameSum = {};
      let bestRuns;
      if (K.NORMALIZED_RANKING_MODE.includes(rankingMode)) {
        teamRuns[e].games.sort(sortRunsNormalized)
        bestRuns = teamRuns[e].games.slice(0, sumGameNumber);
        teamRuns[e].gameSum.normalizedScore = sum(bestRuns.map(run => run.normalizedScore));
        teamRuns[e].gameSum.normalizedScoreMean = teamRuns[e].gameSum.normalizedScore / bestRuns.length;
      } else {
        teamRuns[e].games.sort(sortRuns)
        bestRuns = teamRuns[e].games.slice(0, sumGameNumber);
        teamRuns[e].gameSum.score = sum(bestRuns.map(run => run.score));
      }
      if (desempate) mejores6118.set(teamRuns[e], bestRuns);

      // Mark used or not
      teamRuns[e].games.map((run, index) => {
        if (index < sumGameNumber) run.used = true;
        else run.used = false;
      })

      // Sum of the time
      teamRuns[e].gameSum.time = {};
      teamRuns[e].gameSum.time.minutes = sum(bestRuns.map(run => run.time.minutes));
      teamRuns[e].gameSum.time.seconds = sum(bestRuns.map(run => run.time.seconds));
      teamRuns[e].gameSum.time.minutes += Math.floor(teamRuns[e].gameSum.time.seconds / 60);
      teamRuns[e].gameSum.time.seconds %= 60;

      // Sum of the victims
      if (teamRuns[e].games[0].isNL) { //NL
        teamRuns[e].gameSum.victims = {
          live: sum(bestRuns.map(run => run.nl.liveVictim.filter(l => l.found && l.identified).length)),
          dead: sum(bestRuns.map(run => run.nl.deadVictim.filter(l => l.found && l.identified).length)),
          unknown: sum(bestRuns.map(run => run.nl.liveVictim.filter(l => l.found && !l.identified).length + run.nl.deadVictim.filter(l => l.found && !l.identified).length))
        };
      } else { // WL
        teamRuns[e].gameSum.victims = bestRuns.flatMap(run => run.rescueOrder).reduce(function (result, current) {
          var element = result.find(p => p.victimType == current.victimType && p.zoneType == current.zoneType);
          if (element) {
            element.count ++;
          } else {
            result.push({
              victimType: current.victimType,
              zoneType: current.zoneType,
              count: 1
            });
          }
          return result;
        }, []);
      }

      // Sum of the LoPs
      teamRuns[e].gameSum.lops = sum(bestRuns.map(run => sum(run.LoPs)));

      // Set default score
      teamRuns[e].technicalChallenge = 0;
    })

    let result = {
      mode: rankingMode,
      modeDetails: {
        nonNormalized: rankingMode === K.SUM_OF_BEST_N_GAMES,
        normalized: K.NORMALIZED_RANKING_MODE.includes(rankingMode),
        document: K.DOCUMENT_RANKING_MODE.includes(rankingMode),
        technicalChallenge: rankingMode === 'GAMES_DOCUMENT_CHALLENGE'
      }
    };

    let ranking = Object.values(teamRuns);
    let medias6118 = new Map();
    if (desempate) {
      ranking.forEach(r => {
        let usados = mejores6118.get(r) || [];
        medias6118.set(r, usados.length ? sum(usados.map(run => normalizado6118.get(run))) / usados.length : 0);
      });
    }
    ranking.map(r => {
      r.team = r.games[0].team;
      r.games.map(g => delete g.team);
      // Convert to object
      if (K.NORMALIZED_RANKING_MODE.includes(rankingMode)) {
        r.games = r.games.reduce((accumulator, value, index) => {
          return {...accumulator, [value.normalizationGroup]: value};
        }, {});
      } else {
        r.games = r.games.reduce((accumulator, value, index) => {
          return {...accumulator, [value.round.name]: value};
        }, {});
      }
    });

    switch(rankingMode) {
      case K.SUM_OF_BEST_N_GAMES:
        ranking.map(r => r.finalScore = r.gameSum.score);
        break;
      case K.MEAN_OF_NORMALIZED_BEST_N_GAMES:
        ranking.map(r => r.finalScore = r.gameSum.normalizedScoreMean);
        break;
    }

    if (desempate) {
      ranking.sort(function (a, b) {
        if (a.finalScore == b.finalScore) {
          let d = medias6118.get(b) - medias6118.get(a);
          if (d !== 0 && !isNaN(d)) return d;
          return sortFinalScore(a, b);
        }
        return b.finalScore - a.finalScore;
      });
      ranking.forEach(r => { r.desempate6118 = medias6118.get(r); });
      result.desempate = '6.1.8';
    } else {
      ranking.sort(sortFinalScore);
    }
    result.ranking = ranking;

    if (K.NORMALIZED_RANKING_MODE.includes(rankingMode)) {
      result.runGroups = allNormGroups;
    } else {
      result.runGroups = allRounds;
    }

    return json(200, result);
  }

  R.ranking = {
    calcular: calcular,
    sortRuns: sortRuns,
    sortRunsNormalized: sortRunsNormalized,
    sortFinalScore: sortFinalScore,
    sum: sum
  };
})();

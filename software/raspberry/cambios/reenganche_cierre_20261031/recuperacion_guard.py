"""Evidencia previa congelada y cierre acotado de recuperaciones laterales."""
from collections import deque
import math
import cv2
import numpy as np


class RecoveryGuard:
    VERSION = 'RECUP-REENGANCHE-3'

    def __init__(self):
        self.reset()

    def reset(self):
        self.history = deque(maxlen=30)
        self.evidence = dict(side=0, left=0, right=0)
        self.finish_side = 0
        self.finish_t = 0.0
        self.missing_t = None
        self.turn_t = None
        self.aligned = 0
        self.stopped = False
        self.fragment = None
        self.search_t = None
        self.search_angle = 0.0
        self.search_trackable = 0
        self.search_aligned = 0
        self.search_used = False

    def observe(self, connected):
        left = np.count_nonzero(connected[60:105, :3]) >= 6
        right = np.count_nonzero(connected[60:105, -3:]) >= 6
        self.history.append((bool(left), bool(right)))

    def freeze(self):
        left = sum(x[0] for x in self.history)
        right = sum(x[1] for x in self.history)
        side = 1 if right >= 12 and left <= 2 else -1 if left >= 12 and right <= 2 else 0
        self.evidence = dict(side=side, left=left, right=right)
        self.history.clear()
        self.fragment = None
        self.search_t = None
        self.search_used = False
        self.finish_side = 0
        self.stopped = False
        return dict(self.evidence)

    def decide(self, decision, terminal, post_age=0.0, ambiguous_limit=1.0):
        d = dict(decision)
        terminal = terminal or {}
        reason = str(d.get('reason') or '')
        if (d.get('kind') == 'CURVA' and reason == 'lateral previa + fragmento pequeno compatible'
                and terminal.get('strong') and terminal.get('strong_piso')
                and terminal.get('side_recent') == 0):
            d.update(kind='RECTA', side=0, heading=None, reason='guard: GAP previo sin rama')
            return d, 'GAP_PREVIO'
        side = self.evidence['side']
        if not side:
            return d, None
        recover_side = (d.get('kind') == 'CURVA' and int(d.get('side') or 0) != side)
        block_palillo = d.get('kind') == 'RECTA' and reason == 'palillo: cinta partida'
        block_ambiguous = d.get('kind') == 'AMBIGUA' and post_age >= ambiguous_limit
        if recover_side or block_palillo or block_ambiguous:
            h = d.get('heading')
            magnitude = abs(float(h)) if h is not None and math.isfinite(float(h)) else 35.0
            magnitude = min(90.0, max(12.0, magnitude))
            d.update(kind='CURVA', side=side, heading=side * magnitude,
                     reason='guard: rama previa persistente (%s)' % reason)
            return d, 'RAMA_PREVIA'
        return d, None

    def begin_finish(self, side, now):
        self.finish_side = 1 if side > 0 else -1
        self.finish_t = float(now)
        self.missing_t = None
        self.turn_t = None
        self.aligned = 0
        self.stopped = False

    def _legacy_finish(self, now, connected, full_mask, current_angle):
        """None conserva el comando; STOP requiere GS19, no speed=0 en linea."""
        if self.stopped:
            return dict(action='STOP', angle=0.0)
        if not self.finish_side:
            return None
        from completar_giro import forma_cinta
        ok = np.count_nonzero(connected) >= 200
        shape = forma_cinta(connected, ok)
        self.aligned = self.aligned + 1 if shape in ('A', 'D') else 0
        if self.aligned >= 2:
            self.finish_side = 0
            return None
        if self.turn_t is not None:
            if now - self.turn_t >= 0.45:
                self.stopped = True
                return dict(action='STOP', angle=0.0)
            return dict(action='PIVOT', angle=-85.0 * self.finish_side)
        if not ok:
            if self.missing_t is None:
                self.missing_t = float(now)
            if now - self.missing_t >= 0.35:
                if np.count_nonzero(full_mask[60:]) >= 200:
                    self.turn_t = float(now)
                    return dict(action='PIVOT', angle=-85.0 * self.finish_side)
                self.stopped = True
                return dict(action='STOP', angle=0.0)
        else:
            self.missing_t = None
        if now - self.finish_t >= 1.50:
            self.stopped = True
            return dict(action='STOP', angle=0.0)
        return None

    @staticmethod
    def geometry(mask):
        """Dos bandas: posicion cercana y orientacion; no confundir A con centrado."""
        centers = []
        for a, b in ((100, 120), (60, 80)):
            ys, xs = np.nonzero(mask[a:b])
            if len(xs) < 20:
                return None
            centers.append((float(np.median(xs)) - 79.5) / 80.0)
        return centers[0], centers[1] - centers[0]

    def remember_fragment(self, mask, now):
        # Solo se invoca durante el giro GS4 y su cierre, nunca en GAP o verdes.
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        candidates = [i for i in range(1, count)
                      if stats[i, cv2.CC_STAT_AREA] >= 60
                      and stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT] >= 66]
        if not candidates:
            return
        i = max(candidates, key=lambda k: (stats[k, cv2.CC_STAT_TOP] + stats[k, cv2.CC_STAT_HEIGHT],
                                           stats[k, cv2.CC_STAT_AREA]))
        ys, xs = np.nonzero(labels == i)
        x = float(np.median(xs[ys >= ys.max() - 5]))
        error = (x - 79.5) / 80.0
        if abs(error) >= 0.35:
            self.fragment = (float(now), error)

    def _start_search(self, now):
        # Excepcion al STOP: rama confirmada y fragmento lateral realmente visto.
        # No deducir el lado del fragmento del lado del codo: pueden ser opuestos.
        if (self.search_used or not self.evidence['side'] or self.fragment is None
                or now - self.fragment[0] > 1.5):
            return False
        self.search_used = True
        self.search_t = float(now)
        self.search_angle = -85.0 if self.fragment[1] > 0 else 85.0
        self.search_trackable = 0
        self.search_aligned = 0
        self.stopped = False
        print('[RECUP-REENGANCHE] busca fragmento %s; limite 1.0 s' %
              ('DER' if self.search_angle < 0 else 'IZQ'))
        return True

    def finish(self, now, connected, full_mask, current_angle):
        active = bool(self.finish_side or self.search_t is not None)
        if active:
            self.remember_fragment(full_mask, now)
        geometry = self.geometry(connected) if active else None
        centered = geometry is not None and abs(geometry[0]) <= 0.45 and abs(geometry[1]) <= 0.50
        if self.search_t is not None:
            # Al vencer el plazo, distinguir cinta perdida de seguimiento ya recuperado.
            trackable = geometry is not None and abs(geometry[0]) <= 0.80 and abs(geometry[1]) <= 0.65
            self.search_trackable = self.search_trackable + 1 if trackable else 0
            self.search_aligned = self.search_aligned + 1 if centered else 0
            if self.search_aligned >= 3 or (now - self.search_t >= 1.0 and self.search_trackable >= 3):
                self.finish_side = 0
                self.search_t = None
                self.stopped = False
                return None
            if now - self.search_t >= 1.0:
                self.stopped = True
                self.search_t = None
                self.finish_side = 0
                return dict(action='STOP', angle=0.0)
            # Con cinta conectada se conserva el seguidor; sin ella se pivota
            # hacia el ultimo fragmento visto, sin avanzar recto ni oscilar de lado.
            if np.count_nonzero(connected) >= 200:
                return None
            return dict(action='SEARCH', angle=self.search_angle)
        result = self._legacy_finish(now, connected, full_mask, current_angle)
        if result and result['action'] == 'STOP' and self._start_search(now):
            return dict(action='SEARCH', angle=self.search_angle)
        return result

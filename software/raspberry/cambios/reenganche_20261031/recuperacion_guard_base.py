"""Evidencia previa congelada y cierre acotado de recuperaciones laterales."""
from collections import deque
import math
import cv2
import numpy as np


class RecoveryGuard:
    VERSION = 'RECUP-GEOMETRIA-1'

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

    def finish(self, now, connected, full_mask, current_angle):
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

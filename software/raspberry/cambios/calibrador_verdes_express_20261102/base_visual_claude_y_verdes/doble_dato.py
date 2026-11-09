"""Clasificacion coherente de un doble ya visible; no gobierna motores."""
import cv2
import numpy as np

VERSION = 'DOBLE-DATO-1'


class DoubleData:
    def __init__(self):
        self.reset()

    def reset(self):
        self.started = None
        self.last_seen = None
        self.previous_time = None

    @staticmethod
    def visible_pair(lab, black):
        ref = cv2.moments(black[90:])
        if not ref['m00']:
            return False
        cx = ref['m10'] / ref['m00']
        mask = np.zeros(black.shape, np.uint8)
        mask[70:] = cv2.inRange(lab[70:], np.array([60, 90, 110]), np.array([198, 111, 137]))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        _, _, stats, centers = cv2.connectedComponentsWithStats(mask)
        sides = {-1: [], 1: []}
        for stat, center in zip(stats[1:], centers[1:]):
            x, y, width, height, area = map(int, stat)
            if area < 120 or width < 6 or height < 5:
                continue
            above = max(60, y - 15)
            occupancy = np.count_nonzero(black[above:y, x:x+width]) / ((y - above) * width)
            if occupancy <= 0.32:
                continue
            side = -1 if center[0] < cx - 5 else 1 if center[0] > cx + 5 else 0
            if side:
                sides[side].append((y, y + height))
        return any(min(a[1], b[1]) - max(a[0], b[0]) >= 5
                   for a in sides[-1] for b in sides[1])

    def step(self, raw_state, lab, black, now):
        if self.previous_time is not None and now - self.previous_time > 0.5:
            self.reset()
        self.previous_time = now
        # Nunca crear una marca nueva: el detector previo debe aceptarla.
        if raw_state not in (1, 2, 3):
            if (raw_state == 0 and self.started is not None and self.last_seen is not None
                    and now - self.started <= 1.0 and now - self.last_seen <= 0.18):
                return 3
            self.started = None
            return raw_state
        self.last_seen = now
        if self.started is not None:
            if now - self.started <= 1.0:
                return 3
            self.started = None
        if self.visible_pair(lab, black):
            self.started = now
            return 3
        return raw_state


# El clasificador anterior queda intacto; el refuerzo sólo envuelve su salida.
_OriginalDoubleData = DoubleData
from doble_transversal import EarlyDouble
import os
VERSION = 'DOBLE-DATO-TRANSVERSAL-2'
_PAIR_LOWER = np.array([60, 90, 110])
_PAIR_UPPER = np.array([198, 111, 137])


class DoubleData:
    def __init__(self):
        self._legacy = _OriginalDoubleData()
        self._early = EarlyDouble(self._legacy, _PAIR_LOWER, _PAIR_UPPER)
        self.enabled = os.environ.get('DOBLE_TRANSVERSAL', '1') == '1'

    @property
    def visible_pair(self):
        return self._legacy.visible_pair

    @visible_pair.setter
    def visible_pair(self, function):
        self._legacy.visible_pair = function

    @property
    def last_pair(self):
        return self._early.last_pair

    @property
    def hits(self):
        return self._early.hits

    def configure_colors(self, lower, upper):
        self._early.lower = np.array(lower, np.uint8)
        self._early.upper = np.array(upper, np.uint8)

    def reset(self):
        self._legacy.reset()
        self._early.reset()

    def step(self, raw_state, lab, black, now):
        if not self.enabled:
            return self._legacy.step(raw_state, lab, black, now)
        return self._early.step(raw_state, lab, black, now)

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
            occupancy = np.count_nonzero(black[y-15:y, x:x+width]) / (15.0 * width)
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

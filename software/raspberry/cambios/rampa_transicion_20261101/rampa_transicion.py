"""Entrega suave de una recta de subida ya confirmada hacia la cresta."""
import math
import numpy as np

VERSION = 'RAMPA-TRANSICION-1'


class RampTransition:
    def __init__(self):
        self.reset()

    def reset(self):
        self.streak = 0
        self.armed = False
        self.last_valid = None
        self.last_time = None

    @staticmethod
    def near_geometry(mask):
        ys, centers = [], []
        for y in range(94, 119, 2):
            xs = np.flatnonzero(mask[y])
            if 5 <= len(xs) <= 90 and xs[-1] - xs[0] <= 95:
                ys.append(y)
                centers.append(float(np.median(xs)))
        if len(ys) < 8 or ys[-1] - ys[0] < 14:
            return None
        slope, intercept = np.polyfit(ys, centers, 1)
        residual = np.sqrt(np.mean((np.asarray(centers) - (slope * np.asarray(ys) + intercept)) ** 2))
        if residual > 3.0:
            return None
        y_near = float(np.mean(ys[-4:]))
        x_near = float(np.mean(centers[-4:]))
        offset = (x_near - 79.0) / 80.0
        corrected_slope = slope - offset * 80.0 / (y_near - 10.0)
        return float(offset), float(corrected_slope)

    def step(self, rising, who, mask, now):
        if not rising or (self.last_time is not None and now - self.last_time > 0.5):
            self.reset()
        self.last_time = now
        if not rising:
            return None
        if who == 'rampa-recta':
            self.streak += 1
            if self.streak >= 20:
                self.armed = True
                self.last_valid = now
            return None
        self.streak = 0
        if not self.armed:
            return None
        # Conservar los controladores existentes de cresta y de cinta corta.
        if who != 'rampa-linea':
            return None
        geometry = self.near_geometry(mask)
        if geometry is not None:
            offset, slope = geometry
            self.last_valid = now
            angle = math.degrees(math.atan(slope)) - 30.0 * offset
            return dict(angle=float(np.clip(angle, -15.0, 15.0)), who='rampa-transicion-cerca')
        # Misma cota temporal que la proteccion de cresta ya usada por main.
        if self.last_valid is not None and now - self.last_valid <= 1.5:
            return dict(angle=0.0, who='rampa-transicion-sin-geometria')
        self.armed = False
        return None

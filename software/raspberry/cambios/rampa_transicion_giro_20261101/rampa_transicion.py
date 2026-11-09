"""Entrega suave de una recta de subida ya confirmada hacia la cresta."""
import math
import numpy as np

VERSION = 'RAMPA-TRANSICION-2'

# GIRO EN LA CRESTA (1-nov, pista_doble_dato 18:30 y 18:45). Con la recta armada, una cinta que
# dobla arriba de la rampa entra como rama por UN costado de la imagen y baja hacia el robot cuadro
# a cuadro (fondo de la rama 67 -> 70 -> 74 -> 79 ...). La transicion la tapaba con 0 / +-15 y el
# robot seguia derecho. Si la rama crece GIRO_CUADROS cuadros seguidos, se suelta: vuelve el angulo
# de siempre. El borde de la cresta (8:59) toca los DOS costados o se aleja: ese no suelta.
GIRO_FILAS_MIN = 10   # filas de la mascara que tocan el costado
GIRO_COLS = 3         # ancho de la franja del costado
GIRO_CUADROS = 4
# Despues de soltar por un giro, el robot ya esta arriba y la cinta cruza la imagen: el recorte de la
# cresta la tomaba como paisaje y mandaba 0 con la cinta a la vista (pista_giro_cresta 4:26,75 y 4:46).
# Durante GIRO_SIN_CRESTA_S main no recorta la cresta.
GIRO_SIN_CRESTA_S = 4.0


class RampTransition:
    def __init__(self):
        self.giro_ts = None
        self.reset()

    def tras_giro(self, now):
        return self.giro_ts is not None and now - self.giro_ts <= GIRO_SIN_CRESTA_S

    def reset(self):
        self.streak = 0
        self.armed = False
        self.last_valid = None
        self.last_time = None
        self.side = None
        self.side_bottoms = []

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

    @staticmethod
    def side_branch(mask):
        # (lado, fila mas baja) si la cinta toca UN solo costado con GIRO_FILAS_MIN filas.
        left = np.flatnonzero(mask[:, :GIRO_COLS].any(axis=1))
        right = np.flatnonzero(mask[:, -GIRO_COLS:].any(axis=1))
        if len(left) >= GIRO_FILAS_MIN and len(right) == 0:
            return -1, int(left[-1])
        if len(right) >= GIRO_FILAS_MIN and len(left) == 0:
            return 1, int(right[-1])
        return None

    def turn_ahead(self, mask):
        branch = self.side_branch(mask)
        if branch is None or branch[0] != self.side:
            self.side = None if branch is None else branch[0]
            self.side_bottoms = [] if branch is None else [branch[1]]
            return False
        if branch[1] > self.side_bottoms[-1]:
            self.side_bottoms.append(branch[1])
        elif branch[1] < self.side_bottoms[-1]:
            self.side_bottoms = [branch[1]]
        return len(self.side_bottoms) >= GIRO_CUADROS

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
        if self.turn_ahead(mask):
            self.armed = False
            self.giro_ts = now
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

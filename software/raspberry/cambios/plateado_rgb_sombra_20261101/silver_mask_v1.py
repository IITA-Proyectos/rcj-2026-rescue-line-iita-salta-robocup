"""Prototipo offline: color RGB + dos bordes de una posible banda.

No importa main, no abre puertos y no produce ordenes de motor/GS.
La salida es una hipotesis visual, NO una identificacion de material.
Las pendientes son medidas de imagen: requieren referencia de camara para
usarlas como error de orientacion; no son grados de yaw.
"""
import cv2
import numpy as np

VERSION = 'SILVER-MASK-SHADOW-1'


def rgb_mask(bgr):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.int16)
    maximum, minimum = rgb.max(axis=2), rgb.min(axis=2)
    neutral = maximum - minimum <= np.maximum(20, maximum * 0.22)
    mask = ((maximum >= 45) & (maximum <= 210) & neutral).astype(np.uint8) * 255
    mask[:30] = 0
    return mask


def detect_band(bgr):
    """Devuelve mascara RGB, mascara acotada y geometria candidata, o None.

    Dos bordes paralelos en el piso pueden converger en perspectiva: se permite
    ese estrechamiento y se descartan pares que se cruzan dentro de la banda.
    El contraste es local y relativo al piso, sin cambiar su segmentacion actual.
    """
    height, width = bgr.shape[:2]
    if (height, width) != (120, 160):
        raise ValueError('Se esperan cuadros BGR de 160x120')
    color = rgb_mask(bgr)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 35, 85)
    edges[:30] = 0
    edges[112:] = 0
    found = cv2.HoughLinesP(edges, 1, np.pi / 180, 25,
                            minLineLength=65, maxLineGap=10)
    empty = np.zeros_like(gray)
    if found is None:
        return color, empty, None
    lines = []
    for x1, y1, x2, y2 in np.asarray(found).reshape(-1, 4):
        if abs(x2 - x1) < 60:
            continue
        slope = float((y2 - y1) / (x2 - x1))
        if abs(slope) > 0.85:
            continue
        lines.append((slope, float(y1 - slope * x1),
                      int(min(x1, x2)), int(max(x1, x2))))
    xx, yy = np.meshgrid(np.arange(width), np.arange(height))
    best = None
    value = bgr.max(axis=2)
    for i, first in enumerate(lines):
        for second in lines[i + 1:]:
            if abs(first[0] - second[0]) > 0.40:
                continue
            x0, x1 = max(first[2], second[2]), min(first[3], second[3])
            if x1 - x0 < 65:
                continue
            a = first[0] * xx + first[1]
            b = second[0] * xx + second[1]
            top, bottom = np.minimum(a, b), np.maximum(a, b)
            thickness = bottom[0] - top[0]
            # No extender a traves de la interseccion de las rectas.
            same_order = (a[0] < b[0]) == (a[0, (x0 + x1) // 2] < b[0, (x0 + x1) // 2])
            columns = (thickness >= 6) & (thickness <= 50) & same_order
            inside = ((yy >= top + 1) & (yy <= bottom - 1) & columns[None, :]
                      & (yy >= 30) & (yy < 112))
            area = int(inside.sum())
            if not 400 <= area <= 4200 or np.count_nonzero(inside.any(axis=0)) < 95:
                continue
            occupancy = float(np.mean(color[inside] > 0))
            if occupancy < 0.60:
                continue
            above = ((yy >= top - 9) & (yy <= top - 4) & columns[None, :]
                     & (yy >= 30) & (yy < 112))
            below = ((yy >= bottom + 4) & (yy <= bottom + 9) & columns[None, :]
                     & (yy >= 30) & (yy < 112))
            if min(above.sum(), below.sum()) < 100:
                continue
            middle_v = float(np.median(value[inside]))
            above_v, below_v = float(np.median(value[above])), float(np.median(value[below]))
            if min(above_v, below_v) - middle_v < 8:
                continue
            if max(above_v, below_v) - middle_v < 22:
                continue
            score = occupancy + min(above_v - middle_v, below_v - middle_v) / 100
            if best is None or score > best['score']:
                polygon = inside.astype(np.uint8) * 255
                best = dict(score=score, occupancy=occupancy, area=area,
                            slope=(first[0] + second[0]) / 2,
                            upper=first if first[1] < second[1] else second,
                            lower=second if first[1] < second[1] else first,
                            contrast_above=above_v - middle_v,
                            contrast_below=below_v - middle_v,
                            polygon=polygon)
    if best is None:
        return color, empty, None
    return color, cv2.bitwise_and(color, best['polygon']), best


class SilverShadow:
    """Persistencia visual sin autoridad sobre el robot.

    `stable` no significa APDS confirmado ni entrada centrada. Un cuadro perdido
    invalida la medicion de orientacion: nunca se conserva como alineado.
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.previous = None
        self.previous_time = None
        self.count = 0

    def step(self, bgr, now):
        color, mask, candidate = detect_band(bgr)
        if self.previous_time is not None and (now <= self.previous_time or now - self.previous_time > .5):
            self.reset()
        if candidate is None:
            self.previous = None
            self.count = 0
        else:
            compatible = False
            if self.previous is not None:
                old, new = self.previous['polygon'] > 0, candidate['polygon'] > 0
                union = np.count_nonzero(old | new)
                iou = np.count_nonzero(old & new) / max(union, 1)
                compatible = iou >= .35 and abs(self.previous['slope'] - candidate['slope']) <= .18
            self.count = self.count + 1 if compatible else 1
            self.previous = candidate
        self.previous_time = now
        return dict(rgb_mask=color, silver_mask=mask, candidate=candidate,
                    stable=self.count >= 3, frames=self.count,
                    # No se fabrica una pose ni un centrado desde el centroide de la banda.
                    slope=candidate['slope'] if candidate is not None else None,
                    centered=None, motor_command=None)

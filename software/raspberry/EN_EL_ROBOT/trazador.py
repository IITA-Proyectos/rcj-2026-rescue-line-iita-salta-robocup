# -*- coding: utf-8 -*-
"""Trazador direccional: sigue la linea a lo largo de SU PROPIO EJE.

POR QUE, y cual es el defecto que arregla:
El metodo de franjas horizontales corta la imagen en tiras y toma el centroide
de cada tira. Eso funciona mientras la linea SUBA. Pero cuando la linea tiene un
tramo HORIZONTAL -que en esta pista pasa todo el tiempo, son las curvitas en
zigzag- la franja la corta a lo largo y el centroide cae en el medio de ese
tramo, que no es por donde va la linea. Medido en video_4 frame 183: en tres
franjas seguidas la linea ocupa de x=62 a x=159 y la cadena sale saltando
92 -> 100 -> 123 -> 111 -> 112 -> 116 -> 149.

Este trazador avanza EN PASOS a lo largo de la linea: desde donde esta parado
mira en abanico hacia adelante, elige por donde sigue habiendo cinta, avanza un
paso, y repite. La orientacion de la linea deja de importar.
"""
import cv2, numpy as np, math

W, H = 160, 120
PASO      = 6          # px que avanza en cada paso
ABANICO   = 75         # grados a cada lado que explora
N_RAYOS   = 15         # cuantas direcciones prueba por paso
N_PASOS   = 26         # largo maximo del trazo
RADIO     = 3          # radio del disco con que mide "hay cinta aca"
PESO_GIRO = 0.55       # cuanto penaliza doblar (0 = dobla libre, 1 = va derecho)
MIN_TINTA = 0.35       # fraccion minima del disco que tiene que ser cinta

# Tabla de direcciones precalculada: sin/cos de cada rayo del abanico. Se arma
# una sola vez al importar, no en cada paso.
_D = np.linspace(-math.radians(ABANICO), math.radians(ABANICO), N_RAYOS)
_SIN = np.sin(_D); _COS = np.cos(_D)
_PEN = PESO_GIRO * np.abs(_D)          # penalizacion por doblar, ya calculada


def _disco_int(integral, cx, cy, r=RADIO):
    """Cuanta cinta hay en el cuadrado (cx,cy)+-r, en O(1) con imagen integral.

    Antes esto hacia sub.mean() sobre un recorte: una copia por rayo y por paso,
    o sea ~400 recortes por frame. Con la integral son 4 lecturas y una resta.
    """
    x0, x1 = max(0, cx-r), min(W, cx+r+1)
    y0, y1 = max(0, cy-r), min(H, cy+r+1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    area = (x1-x0) * (y1-y0)
    s = (integral[y1, x1] - integral[y0, x1] - integral[y1, x0] + integral[y0, x0])
    return float(s) / (area * 255.0)


def trazar(mask, x0, y0, ang0=0.0):
    """ang0 en radianes; 0 = hacia arriba de la imagen (alejandose del robot)."""
    integral = cv2.integral(mask)                # una sola vez por frame
    pts = [(float(x0), float(y0))]
    x, y, ang = float(x0), float(y0), float(ang0)
    for _ in range(N_PASOS):
        # las N_RAYOS direcciones de una, con la tabla precalculada
        sa, ca = math.sin(ang), math.cos(ang)
        nxs = x + PASO * (sa*_COS + ca*_SIN)     # sin(ang+d)
        nys = y - PASO * (ca*_COS - sa*_SIN)     # cos(ang+d)
        mejor_sc, mejor_i = -1e9, -1
        for i in range(N_RAYOS):
            nx, ny = nxs[i], nys[i]
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            tinta = _disco_int(integral, int(nx), int(ny))
            if tinta < MIN_TINTA:
                continue
            sc = tinta - _PEN[i]
            if sc > mejor_sc:
                mejor_sc, mejor_i = sc, i
        if mejor_i < 0:
            break
        x, y = nxs[mejor_i], nys[mejor_i]
        ang = 0.6 * ang + 0.4 * (ang + _D[mejor_i])
        pts.append((float(x), float(y)))
    return pts


def punto_de_partida(mask):
    """El punto de la cinta mas cercano al robot: fila mas baja con cinta,
    y dentro de esa fila el tramo mas cercano al centro."""
    for y in range(H-1, H//2, -1):
        col = np.where(mask[y] > 0)[0]
        if len(col) == 0:
            continue
        tramos, ini = [], None
        for x in range(W):
            if mask[y][x] and ini is None:
                ini = x
            elif not mask[y][x] and ini is not None:
                tramos.append((ini, x-1)); ini = None
        if ini is not None:
            tramos.append((ini, W-1))
        tramos = [t for t in tramos if t[1]-t[0] >= 2]
        if not tramos:
            continue
        t = min(tramos, key=lambda t: abs((t[0]+t[1])/2.0 - (W-1)/2.0))
        return (t[0]+t[1])/2.0, float(y)
    return None


def punto_a_distancia(pts, dist):
    """Punto que esta a 'dist' pixeles A LO LARGO del trazo (no en linea recta).

    Es el punto de mira de pure pursuit bien hecho: la distancia se mide
    siguiendo la cinta, no en altura de imagen. Con la linea horizontal, medir
    por altura daba cualquier cosa.
    """
    if len(pts) < 2:
        return pts[-1] if pts else None
    acum = 0.0
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        d = math.hypot(xb-xa, yb-ya)
        if acum + d >= dist:
            t = 0.0 if d == 0 else (dist - acum) / d
            return (xa + t*(xb-xa), ya + t*(yb-ya))
        acum += d
    return pts[-1]


class SeguidorTrazo(object):
    """Seguidor completo basado en el trazador direccional."""

    def __init__(self, mirada=52, ganancia=1.0, memoria_ms=600):
        self.mirada = mirada          # px a lo largo de la cinta
        self.ganancia = ganancia
        self.hist = []
        self.ultimo = 0.0
        self.edad = 999
        self.max_edad = int(memoria_ms / 50)

    def paso(self, frame, mascara_fn, ya_procesado=False):
        if not ya_procesado:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
            frame = cv2.resize(frame, (W, H), interpolation=cv2.INTER_NEAREST)
        m = mascara_fn(frame)
        p0 = punto_de_partida(m)
        if p0 is None:
            self.edad += 1; self.hist = []
            return {"ok": False, "motivo": "sin linea", "puntos": [],
                    "angle_filtrado": self.ultimo if self.edad <= self.max_edad else 0.0,
                    "vigente": self.edad <= self.max_edad, "confianza": 0.0}
        pts = trazar(m, p0[0], p0[1])
        if len(pts) < 3:
            self.edad += 1; self.hist = []
            return {"ok": False, "motivo": "trazo corto", "puntos": pts,
                    "angle_filtrado": self.ultimo if self.edad <= self.max_edad else 0.0,
                    "vigente": self.edad <= self.max_edad, "confianza": 0.0}
        largo = sum(math.hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(pts, pts[1:]))
        pm = punto_a_distancia(pts, min(self.mirada, largo))
        ox, oy = (W-1)/2.0, float(H)
        ang = math.degrees(math.atan2(ox - pm[0], oy - pm[1]))
        ang = max(-90.0, min(90.0, ang * self.ganancia))
        self.hist.append(ang)
        if len(self.hist) > 3:
            self.hist.pop(0)
        ang = float(np.median(self.hist))
        self.ultimo = ang; self.edad = 0
        return {"ok": True, "motivo": "", "puntos": pts, "angle": ang,
                "angle_filtrado": ang, "vigente": True,
                "confianza": min(1.0, largo / self.mirada),
                "largo": largo, "mira": pm}

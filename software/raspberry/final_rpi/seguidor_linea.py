# -*- coding: utf-8 -*-
"""
seguidor_linea.py - Seguidor de linea del robot del IITA (Roboliga 2026).

COMO FUNCIONA, en tres frases
-----------------------------
1. Se busca donde esta la cinta justo delante del robot.
2. Desde ahi se la va SIGUIENDO en pasos cortos: en cada paso se mira en abanico
   hacia adelante y se avanza por donde sigue habiendo cinta. Eso dibuja la ruta.
3. Se apunta a un punto de esa ruta que esta a una distancia fija MEDIDA A LO
   LARGO DE LA CINTA. (Es "pure pursuit", el metodo clasico de seguimiento.)

POR QUE NO SE USA EL METODO DE ANTES
------------------------------------
El codigo viejo sacaba UN centroide de todos los pixeles negros del ROI. Eso
responde "donde esta el promedio de negro", que no es "hacia donde va la linea".
Medido sobre los videos del 16-ago-2026:
  * en el 11 % de los frames de video_4 el angulo salia con el SIGNO INVERTIDO;
  * su ganancia cerca del centro era ~2,0 grados por pixel y lejos 0,4, o sea
    que sobrecorregia cerca de la linea y por eso oscilaba en vez de centrarse;
  * con la linea perfectamente centrada daba -2 grados (cam_x = W/2 - 1 deja el
    centro medio pixel corrido).

Y tampoco se usa el metodo de FRANJAS HORIZONTALES que probamos antes: falla
justo en las curvitas en zigzag de esta pista. Cuando la cinta tiene un tramo
horizontal, la franja la corta a lo largo y el centroide cae en el medio de ese
tramo, que no es por donde va la linea. Medido: el trazo se salia de la cinta en
81 frames de video_4 y 217 de video_5. Con este metodo, 0 y 2.

RESULTADOS MEDIDOS (video_4 y video_5, 1456 frames, en PC)
----------------------------------------------------------
  la ruta cae SOBRE la cinta   96,6 % / 97,1 %   (franjas: 88,4 % / 82,7 %)
  encuentra ruta               95,0 % / 96,2 %
  costo                        0,54 / 0,52 ms por frame

OJO: esto corrio en PC sobre video grabado con la camara en la mano. NO corrio
en el robot. Que la ruta este bien dibujada no prueba que el robot tome la
curva: si la rueda interna no arranca en reversa, ningun angulo lo arregla.

USO EN vision/main.py
---------------------
    from seguidor_linea import Seguidor, velocidad_sugerida
    seguidor = Seguidor()                 # una sola vez, antes del lazo
    ...
    r = seguidor.paso(frame_resized, ya_procesado=True)
    angle = r["angle_filtrado"]           # reemplaza al calculo con atan2
    speed = velocidad_sugerida(r)         # opcional
El signo es el mismo que el del codigo viejo (derecha = negativo), asi que
send_frame() y el firmware NO se tocan.
"""
import cv2, numpy as np, math

W, H = 160, 120
LO = np.array([0, 0, 0]); HI = np.array([90, 90, 90])
_K = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
DENS_SALON  = 0.55
RECORTE_MINIMO = 60    # las filas que el Main.py de la Raspberry ya borraba
MARGEN_SALON = 4

UMBRAL_ADAPTATIVO = True   # False vuelve al umbral fijo de siempre
FACTOR_OSCURO     = 0.62   # la linea es lo que esta por debajo de este factor
                           # del brillo del piso EN SU MISMA FILA


def _mascara(f):
    """Saca la linea negra.

    El umbral FIJO ([0,0,0]-[90,90,90]) falla cuando el piso esta muy iluminado:
    el reflejo aclara la cinta, deja de pasar el umbral, y la linea se corta en
    dos. Medido en video_4 frame 260: la franja con brillo medio 200 pierde la
    linea mientras las de brillo 90-155 la ven bien.

    El umbral ADAPTATIVO compara cada pixel contra el brillo del piso EN SU
    MISMA FILA, asi que se banca que la iluminacion cambie de arriba a abajo.
    Medido: la cobertura sube de 95,5% a 99,5% en video_4 y de 95,9% a 97,5%
    en video_5.

    OJO: no hace milagros. Si el reflejo es tan fuerte que la cinta y el piso
    quedan al mismo brillo, la informacion no esta y ningun umbral la recupera.
    Eso se arregla FIJANDO LA EXPOSICION de la camara (v4l2-ctl), que ademas
    esta pendiente en camara.py: hoy corre con auto-exposure.
    """
    if UMBRAL_ADAPTATIVO:
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.int16)
        ref = np.percentile(g, 70, axis=1).reshape(-1, 1)      # el piso de cada fila
        m = ((g < ref * FACTOR_OSCURO) * 255).astype(np.uint8)
    else:
        m = cv2.inRange(f, LO, HI)
    # los reflejos del LED perforan la cinta: cerrar tapa esos agujeros
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, _K, iterations=1)
    # RECORTE DE LO QUE NO ES PISO. Esto FALTABA: _fila_salon() estaba definida y
    # no se llamaba desde ningun lado, asi que la mascara incluia el horizonte y el
    # trazador se podia ir caminando por una pared o una silla -que es justo el modo
    # de falla que probar_planner.py te dice que mires-. El Main.py que corre en la
    # Raspberry hace `black_mask[:60, :] = 0`, un recorte fijo; aca se usa el
    # adaptativo, y ademas se garantiza ese recorte fijo como piso minimo para no
    # quedar nunca viendo mas arriba de lo que ya recortaba el metodo viejo.
    corte = max(_fila_salon(m), RECORTE_MINIMO)
    if corte > 0:
        m[:corte, :] = 0
    return m


def _fila_salon(mask):
    """Primera fila (de arriba hacia abajo) donde TERMINA la masa del salon.

    El salon entra por el borde superior como filas casi enteras de negro. Se
    baja mientras la fila siga siendo mayormente negra; donde deja de serlo,
    empieza el piso. Si no hay salon, devuelve 0."""
    dens = mask.mean(axis=1) / 255.0
    y = 0
    while y < H and dens[y] >= DENS_SALON:
        y += 1
    return min(y + MARGEN_SALON, H - 1) if y > 0 else 0


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


class Seguidor(object):
    """Seguidor completo basado en el trazador direccional."""

    def __init__(self, mirada=52, ganancia=1.0, memoria_ms=600):
        self.mirada = mirada          # px a lo largo de la cinta
        self.ganancia = ganancia
        self.hist = []
        self.ultimo = 0.0
        self.edad = 999
        self.max_edad = int(memoria_ms / 50)

    def paso(self, frame, ya_procesado=False):
        if not ya_procesado:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
            frame = cv2.resize(frame, (W, H), interpolation=cv2.INTER_NEAREST)
        m = _mascara(frame)
        p0 = punto_de_partida(m)
        if p0 is None:
            self.edad += 1; self.hist = []
            return {"ok": False, "motivo": "sin linea", "puntos": [], "mascara": m,
                    "angle_filtrado": self.ultimo if self.edad <= self.max_edad else 0.0,
                    "vigente": self.edad <= self.max_edad, "confianza": 0.0}
        pts = trazar(m, p0[0], p0[1])
        if len(pts) < 3:
            self.edad += 1; self.hist = []
            return {"ok": False, "motivo": "trazo corto", "puntos": pts, "mascara": m,
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
        return {"ok": True, "motivo": "", "puntos": pts, "angle": ang, "mascara": m,
                "angle_filtrado": ang, "vigente": True,
                "confianza": min(1.0, largo / self.mirada),
                "largo": largo, "mira": pm}


def velocidad_sugerida(r, v_recta=40, v_curva=45, v_dudoso=20):
    """Velocidad segun cuan cerrada esta la curva Y cuanta confianza hay.

    Dos reglas distintas, y es importante no confundirlas:

    1. CURVA CERRADA CON BUENA VISTA -> mas rapido. Va al reves de la intuicion:
       el radio lo fija 'rotation' y no depende de la velocidad, pero la
       velocidad de giro SI es proporcional a 'speed'. Frenar en la curva no la
       cierra, solo hace que el robot tarde mas en girar y se le escape la linea
       del campo de la camara.

    2. POCA CONFIANZA -> mas despacio. Cuando la cadena se corta (un reflejo
       parte la cinta, o la linea sale del cuadro) el planner extrapola y avisa
       bajando 'confianza'. Ahi conviene ir lento: no es momento de comprometerse
       con un giro fuerte basado en un dato que el propio algoritmo marca como
       flojo.

    Verificado con el reparto real de DriveBase::steer(); NO corrio en el robot.
    """
    if not r.get("ok") and not r.get("vigente"):
        return 0
    conf = r.get("confianza", 1.0) if r.get("ok") else 0.0
    a = abs(r.get("angle_filtrado", 0.0))
    if a < 12:
        v = v_recta
    elif a > 45:
        v = v_curva
    else:
        v = v_recta + (v_curva - v_recta) * (a - 12) / 33.0
    if conf < 0.5:                       # el planner dice que no esta seguro
        v = v_dudoso + (v - v_dudoso) * (conf / 0.5)
    return int(round(v))

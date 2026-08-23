# -*- coding: utf-8 -*-
"""
shadow.py - Banco SHADOW: corre la maquina de estados candidata EN PARALELO al
            control que realmente corrio, sobre los mismos frames grabados.

============================================================================
 ESTO NO ES UNA SIMULACION FISICA
============================================================================

Las imagenes estan grabadas con la trayectoria que el robot REALMENTE hizo. Si
el candidato hubiera decidido otra cosa, los frames siguientes habrian sido
OTROS. Es lazo abierto.

LO QUE SI CONTESTA:
  - que estado de confianza (HIGH/MEDIUM/LOW/LOST) ve la vision en cada frame
  - que habria mandado el control de hoy, y que mandaria el candidato
  - cuando el candidato RECHAZA una inversion de signo, y por que
  - si el candidato interviene ANTES de las fallas reales
  - si deja tranquilos los giros que ya funcionan
LO QUE NO CONTESTA:
  - si el robot completa la curva. Eso solo lo dice la pista.

============================================================================
 DOS FORMATOS DE ENTRADA, Y CONFUNDIRLOS DA TODO AL REVES
============================================================================

  640x240  panel de GRABAR: el lado IZQUIERDO ya es el frame de 160x120 que la
           Pi proceso -ya rotado 180 y reescalado-. Se recupera con
           f[:, :320][::2, ::2]. NO se vuelve a rotar.

  cualquier otra  video CRUDO de camara. Hay que hacerle lo mismo que la Pi:
           cv2.rotate(f, ROTATE_180)  ->  resize (160,120) INTER_NEAREST
           (main_rpi_2026-08-22.py, lineas 798-799 del original)

El umbral y el ROI son los del codigo del 22-ago: inRange(0,0,0)-(90,90,90) y
black_mask[:60,:] = 0.

USO
---
    python3 shadow.py video_4.avi
    python3 shadow.py hist.avi --desde 580 --hasta 679 --tag exito
    python3 shadow.py hist.avi --desde 1354 --hasta 1490 --tag falla
    python3 shadow.py --todos
"""
import argparse
import math
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from replay import ModeloCase7, FW_STEER_GAIN, FW_PIVOTE_ENTRA  # noqa: E402

LO = np.array([0, 0, 0])
HI = np.array([90, 90, 90])
W, H = 160, 120
CENTRO = (W - 1) / 2.0
FPS = 33.3

# --- bandas. NEAR es lo que el robot tiene debajo; FAR es lo mas lejos que ve
NEAR = (110, 119)
MID = (95, 105)
FAR = (75, 85)
PIX_MIN = 8                 # px de la componente en una banda para contarla
AREA_LOST = 30              # debajo de esto no hay ni referencia cercana
VEL_LOW = 15                # rpm en LOW: "avance reducido" deja de ser una palabra
VEL_SIN_CERCA = 12          # rpm cuando no la tiene debajo pero hay pista adelante
VEL_PERDIDA = 25            # el case 4 del firmware: BACKWARD 25 rpm, 200 ms
AREA_JUNCTION = 1500        # una T/cruz tiene componente GRANDE
ANCHO_JUNCTION = 60         # y ancha

NEGRO = (18, 18, 18)
BLANCO = (235, 235, 235)
GRIS = (120, 120, 120)
ROJO = (80, 80, 240)
VERDE = (110, 220, 110)
AMARILLO = (60, 210, 235)
NARANJA = (60, 150, 250)
COLOR_EST = {"HIGH": VERDE, "MEDIUM": (170, 220, 120), "LOW": NARANJA,
             "SIN_CERCA": (80, 180, 255), "PERDIDA": ROJO}


def frame_de_la_pi(f):
    """Devuelve el 160x120 tal como lo vio la Pi, segun el formato de entrada.

    EL SUBMUESTREO IMPAR NO ES UN CAPRICHO. El panel es el 160x120 duplicado
    pixel a pixel, pero el MJPEG con perdida hace que las dos copias de cada
    pixel no queden identicas. Validado contra el rxsteer real de las 960 tramas
    enganchadas de hist.avi:

        [::2, ::2]     (par)     65,2 % exacto al grado
        [1::2, 1::2]   (impar)   84,0 %   <-- esta
        [1::2, ::2]              82,6 %
        [::2, 1::2]              63,0 %

    Tomar los pares -que es lo intuitivo- pierde 19 puntos. Con `impar` el
    99,997 de la varianza queda explicada (r = 0,9957) y el 96,2 % cae dentro de
    un grado, que es lo que hace falta para comparar leyes de control.
    """
    if f.shape[0] == 240 and f.shape[1] >= 640:
        return f[:, :320][1::2, 1::2]        # panel de GRABAR: ya procesado
    g = cv2.rotate(f, cv2.ROTATE_180)        # video crudo: como hace main.py
    return cv2.resize(g, (W, H), interpolation=cv2.INTER_NEAREST)


def percibir(g):
    """Todo lo que se puede saber de UN frame, sin memoria."""
    m = cv2.inRange(g, LO, HI)
    m[:60, :] = 0
    n, et, est, _ = cv2.connectedComponentsWithStats((m > 0).astype(np.uint8), 8)
    mejor, k0 = 0, 0
    for k in range(1, n):
        if np.any(et[119, :] == k) and est[k, cv2.CC_STAT_AREA] > mejor:
            mejor, k0 = est[k, cv2.CC_STAT_AREA], k
    d = {"area": 0.0, "wmax": 0, "trav": 0, "near": False, "mid": False,
         "far": False, "comp": None, "cx": None, "area_arriba": 0.0,
         "cx_arriba": None}
    # lo mas grande que NO toca la fila 119: es "pista adelante" aunque no la
    # tenga debajo. Distinguirlo importa: de todos los frames sin linea debajo,
    # el 61 % tiene pista adelante (medido sobre 14.542 frames de 11 videos).
    for k in range(1, n):
        if not np.any(et[119, :] == k):
            a = float(est[k, cv2.CC_STAT_AREA])
            if a > d["area_arriba"]:
                d["area_arriba"] = a
                ys, xs = np.nonzero(et == k)
                d["cx_arriba"] = float(xs.mean()) - CENTRO
    if not k0 or mejor < AREA_LOST:
        return d
    mm = (et == k0)
    anchos = [len(np.nonzero(mm[y, :])[0]) for y in range(60, 120)]
    d["comp"] = mm
    d["area"] = float(mejor)
    d["wmax"] = max(anchos)
    d["trav"] = max(anchos[:40])                 # travesano: filas 60..99
    for nom, (a, b) in (("near", NEAR), ("mid", MID), ("far", FAR)):
        d[nom] = mm[a:b + 1, :].sum() >= PIX_MIN
    xs = np.nonzero(mm[119, :])[0]
    d["cx"] = (float(xs.mean()) - CENTRO) if len(xs) else None
    return d


def confianza(p):
    """HIGH / MEDIUM / LOW / LOST a partir de la percepcion.

    JUNCTION NO ES UN ESTADO DE ESTE NIVEL, y la primera version se equivoco en
    eso: usaba `area >= 1500 y travesano >= 60`, y con ese criterio daba entre
    34 % y 52 % de los frames. Una pista no tiene intersecciones la mitad del
    tiempo. El problema es que los frames NORMALES ya cumplen ese criterio: los
    HIGH tienen area mediana 3216 y travesano 63.

    La T se protege sola, y por eso no hace falta un estado aparte: una T tiene
    el travesano a distancia media y conectado al tronco, asi que da `mid` -y
    normalmente tambien `far`- verdaderos. Cae en HIGH o MEDIUM, y ahi el
    candidato NO INTERVIENE. El comportamiento reglamentario de la T queda
    intacto por construccion del candidato, no por una regla extra.

    Medido sobre los 10 videos: de 672 frames LOW, NINGUNO tenia area de
    interseccion (mediana 79 px contra 3216 de los HIGH). Es evidencia fuerte
    sobre el material disponible, NO una imposibilidad geometrica: una T
    parcialmente fuera del ROI podria dar otra cosa.
    """
    if not p["near"] or p["area"] < AREA_LOST:
        # NO ES LO MISMO "no la tengo debajo" que "no hay nada".
        # La traza manual de Benjamin lo expuso: en video_4, entre los frames
        # 550 y 560 la cinta vuelve a entrar POR ARRIBA -area creciendo de 36 a
        # 270 px en la fila 60- mientras el, moviendolo a mano, completaba la
        # maniobra bien. Retroceder ahi seria alejarse de la linea que vuelve.
        # Medido sobre 14.542 frames de 11 videos: de los que no tienen linea
        # debajo, el 61 % TIENE pista adelante.
        return "SIN_CERCA" if p["area_arriba"] >= AREA_LOST else "PERDIDA"
    if p["mid"] and p["far"]:
        return "HIGH"
    if p["mid"]:
        return "MEDIUM"
    return "LOW"


def es_interseccion(p):
    """Bandera SOLO informativa, para el overlay y el CSV. No decide nada."""
    return p["area"] >= AREA_JUNCTION and p["trav"] >= ANCHO_JUNCTION


def angulo_atan2(g):
    """El atan2 del codigo del 22-ago, sobre el ROI."""
    m = cv2.inRange(g, LO, HI)
    m[:60, :] = 0
    if m.sum() < 1:
        return 0.0, True                      # la guarda de min_line_size
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return 0.0, True
    xc = (xs - (W / 2 - 1)) / (W / 2)
    yc = ((H - 1) - ys) / H
    xb = np.mean(xc * (1 - yc))
    yb = np.mean(yc)
    return (math.atan2(yb, xb) / math.pi * 180) - 90, False


class Candidato(object):
    """La maquina de estados a evaluar. NO se da por buena.

    LA IDEA, en una frase: mientras la evidencia sea pobre, una medida pobre NO
    tiene permiso para contradecir la ultima medida buena.

    Es distinto del dwell viejo. El dwell decia "durante X ms no cambies de
    signo", sin mirar por que. Esto dice "no cambies de signo MIENTRAS la
    evidencia este degradada", y suelta apenas la evidencia vuelve.
    """

    def __init__(self, ventana_ms=600):
        self.ventana_ms = ventana_ms
        self.signo_confiable = 0        # el ultimo signo decidido con HIGH/MEDIUM
        self.t_low = None               # cuando empezo el tramo LOW
        self.t = 0.0

    def paso(self, estado, signo_pedido, rot_actual, vel_actual, dt_s,
             cx_arriba=None):
        """Devuelve el COMANDO FISICO COMPLETO, no solo `rot`.

        La primera version solo devolvia `rot`, y eso era enganoso: con
        accion="recuperar" la barra mostraba el rot viejo mientras el texto decia
        "retrocede". Ahora salen `vel`, `direccion`, `rot` y las consignas de
        rueda, calculadas con la misma cuenta de DriveBase::steer.
        """
        ms = self.t * 1000.0
        self.t += dt_s
        r = {"rot": rot_actual, "vel": vel_actual, "dir": "FORWARD",
             "accion": "normal", "rechazo": False, "motivo": ""}

        if estado in ("HIGH", "MEDIUM"):
            if signo_pedido:
                self.signo_confiable = signo_pedido
            self.t_low = None
            r["motivo"] = "evidencia %s: el angulo manda" % estado
            return r

        if estado == "PERDIDA":
            self.t_low = None
            r.update(accion="retroceder", vel=VEL_PERDIDA, dir="BACKWARD", rot=0.0,
                     motivo="ni linea debajo ni pista adelante: case 4, 25 rpm atras")
            return r

        if estado == "SIN_CERCA":
            # NO retroceder: la cinta esta adelante, volviendo. Retroceder seria
            # alejarse de ella. Se sostiene el sentido confiable y se afloja.
            if self.t_low is None:
                self.t_low = ms
            if ms - self.t_low > self.ventana_ms:
                r.update(accion="timeout",
                         motivo="sin cerca sostenido > %d ms: se abandona" % self.ventana_ms)
                return r
            # HACIA DONDE. La primera version sostenia el ultimo signo
            # confiable, y la traza manual de Benjamin la delato: en video_4
            # 550-560 la cinta reaparece por un lado y el ultimo signo apuntaba
            # al otro, asi que el candidato habria girado ALEJANDOSE de ella.
            # La mancha visible dice de que lado esta; eso manda sobre la
            # memoria. Convenio: cx > 0 es a la derecha en la imagen, y girar
            # hacia la derecha es rot NEGATIVO (igual que el atan2 del codigo).
            if cx_arriba is not None:
                signo = -1 if cx_arriba > 0 else 1
                por = "hacia la mancha visible (cx %+.0f px)" % cx_arriba
            else:
                signo = self.signo_confiable or (signo_pedido or 1)
                por = "sin cx: se sostiene el ultimo sentido confiable"
            r.update(accion="ir_a_buscarla", vel=VEL_SIN_CERCA, rot=signo * 1.0,
                     motivo="no la tengo debajo pero HAY pista adelante: voy %s" % por)
            return r

        # LOW: hay referencia cercana, pero pobre
        if self.t_low is None:
            self.t_low = ms
        if ms - self.t_low > self.ventana_ms:
            r.update(accion="timeout",
                     motivo="LOW sostenido > %d ms: se abandona el sostenimiento" % self.ventana_ms)
            return r
        r.update(accion="sostener", vel=VEL_LOW)
        if self.signo_confiable and signo_pedido and signo_pedido != self.signo_confiable:
            r["rot"] = abs(rot_actual) * self.signo_confiable
            r["rechazo"] = True
            r["motivo"] = "LOW: evidencia pobre NO invierte el sentido confiable"
        else:
            r["motivo"] = "LOW: se sostiene el sentido, avance reducido"
        return r


def ruedas(vel, rot):
    """DriveBase::steer(drivebase.cpp:205): el lado interno se invierte si la
    consigna sale negativa; lo que se registra es la MAGNITUD."""
    otro = abs(vel - 2.0 * abs(rot) * vel)
    return (otro, vel) if rot > 0 else (vel, otro)


def panel_texto(img, x, y, filas, ancho):
    for i, (txt, col, esc) in enumerate(filas):
        cv2.putText(img, txt, (x, y + i * 22), cv2.FONT_HERSHEY_SIMPLEX, esc,
                    col, 1, cv2.LINE_AA)


def barra(img, x, y, w, h, valor, color, etiqueta):
    cx = x + w // 2
    cv2.rectangle(img, (x, y), (x + w, y + h), (55, 55, 55), 1)
    cv2.line(img, (cx, y), (cx, y + h), GRIS, 1)
    n = int(min(abs(valor), 1.0) * (w // 2))
    if n > 1:
        a, b = (cx, cx + n) if valor > 0 else (cx - n, cx)
        cv2.rectangle(img, (a, y + 2), (b, y + h - 2), color, -1)
    cv2.putText(img, etiqueta, (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)


def correr(ruta, desde=0, hasta=10 ** 9, tag="", ventana_ms=600, salida_dir=None,
           con_video=True):
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        print("*** no se pudo abrir %s" % ruta)
        return None
    base = os.path.splitext(os.path.basename(ruta))[0] + (("_" + tag) if tag else "")
    sd = salida_dir or AQUI
    sal_avi = os.path.join(sd, "shadow_%s.avi" % base)
    sal_csv = os.path.join(sd, "shadow_%s.csv" % base)

    E = 3
    PW, PH = W * E, H * E                      # 480x360
    ANCHO, ALTO = PW * 2 + 420, PH + 150
    vw = cv2.VideoWriter(sal_avi, cv2.VideoWriter_fourcc(*"MJPG"), 12.0,
                         (ANCHO, ALTO)) if con_video else None
    fcsv = open(sal_csv, "w")
    # `source_frame` es el indice en el VIDEO ORIGINAL, no en el recorte: si el
    # CSV dice 1354 es el frame 1354 de hist.avi. La primera version escribia el
    # video ENTERO aunque el AVI saliera recortado, y eso es exactamente la clase
    # de discrepancia de procedencia que ya costo cara en este proyecto.
    fcsv.write("source_frame,angle,near,mid,far,area,area_arriba,wmax,trav,interseccion,"
               "estado,vel_actual,dir_actual,rot_actual,ls_actual,rs_actual,"
               "vel_candidato,dir_candidato,rot_candidato,ls_candidato,rs_candidato,"
               "rechazo,accion,motivo\n")

    fw = ModeloCase7(confirma_ms=0)
    cand = Candidato(ventana_ms=ventana_ms)
    dt = 1.0 / FPS
    i = escritos = 0
    cnt = {}
    rechazos = interv = 0

    while True:
        ok, f = cap.read()
        if not ok:
            break
        idx = i
        i += 1
        g = frame_de_la_pi(f)
        p = percibir(g)
        est = confianza(p)
        en_tramo = desde <= idx <= hasta
        if en_tramo:
            cnt[est] = cnt.get(est, 0) + 1
        ang, guarda = angulo_atan2(g)
        r = fw.paso(ang, dt)
        signo = 1 if r["rot"] > 0 else (-1 if r["rot"] < 0 else 0)
        c = cand.paso(est, signo, r["rot"], r["vel"], dt, p["cx_arriba"])
        lsa, rsa = ruedas(r["vel"], r["rot"])
        lsc, rsc = ruedas(c["vel"], c["rot"])
        if en_tramo and c["rechazo"]:
            rechazos += 1
        if en_tramo and c["accion"] != "normal":
            interv += 1

        if en_tramo:
            fcsv.write("%d,%.1f,%d,%d,%d,%.0f,%.0f,%d,%d,%d,%s,"
                       "%d,%s,%.3f,%.0f,%.0f,%d,%s,%.3f,%.0f,%.0f,%d,%s,%s\n" %
                       (idx, ang, p["near"], p["mid"], p["far"], p["area"],
                        p["area_arriba"], p["wmax"], p["trav"],
                        1 if es_interseccion(p) else 0, est,
                        r["vel"], "FORWARD", r["rot"], lsa, rsa,
                        c["vel"], c["dir"], c["rot"], lsc, rsc,
                        1 if c["rechazo"] else 0, c["accion"], c["motivo"]))

        if not (con_video and en_tramo):
            continue

        img = np.full((ALTO, ANCHO, 3), NEGRO, np.uint8)
        cam = cv2.resize(g, (PW, PH), interpolation=cv2.INTER_NEAREST)
        img[40:40 + PH, 0:PW] = cam
        vis = np.zeros((H, W, 3), np.uint8)
        m = cv2.inRange(g, LO, HI)
        m[:60, :] = 0
        vis[m > 0] = (70, 70, 70)
        if p["comp"] is not None:
            vis[p["comp"]] = COLOR_EST.get(est, BLANCO)
        vis = cv2.resize(vis, (PW, PH), interpolation=cv2.INTER_NEAREST)
        for nom, (a, b), col in (("NEAR", NEAR, (255, 200, 80)), ("MID", MID, (255, 150, 200)),
                                 ("FAR", FAR, (200, 255, 150))):
            cv2.line(vis, (0, a * E), (PW, a * E), col, 1)
            cv2.putText(vis, nom, (4, a * E - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1, cv2.LINE_AA)
        img[40:40 + PH, PW:PW * 2] = vis

        cv2.putText(img, "SHADOW REPLAY - NO ES SIMULACION FISICA", (8, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, AMARILLO, 1, cv2.LINE_AA)
        cv2.putText(img, "%s  frame %d" % (os.path.basename(ruta), idx), (PW + 8, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, BLANCO, 1, cv2.LINE_AA)

        px = PW * 2 + 14
        cv2.putText(img, est, (px, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    COLOR_EST.get(est, BLANCO), 2, cv2.LINE_AA)
        panel_texto(img, px, 108, [
            ("near %s   mid %s   far %s" % ("SI" if p["near"] else "no",
                                            "SI" if p["mid"] else "no",
                                            "SI" if p["far"] else "no"), GRIS, 0.5),
            ("area %5.0f   ancho %3d" % (p["area"], p["wmax"]), GRIS, 0.5),
            ("travesano %3d" % p["trav"], GRIS, 0.5),
            ("angle %+6.1f gr%s" % (ang, "  (guarda)" if guarda else ""), BLANCO, 0.5),
        ], 400)
        barra(img, px, 220, 380, 26, r["rot"], ROJO, "CONTROL ACTUAL   rot %+.2f" % r["rot"])
        barra(img, px, 290, 380, 26, c["rot"], VERDE, "CANDIDATO        rot %+.2f" % c["rot"])
        if c["rechazo"]:
            cv2.rectangle(img, (px - 6, 280), (px + 386, 326), AMARILLO, 2)
            cv2.putText(img, "INVERSION RECHAZADA", (px, 348),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, AMARILLO, 1, cv2.LINE_AA)

        y0 = 40 + PH + 26
        cv2.putText(img, "accion: %s" % c["accion"], (8, y0),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    VERDE if c["accion"] == "normal" else NARANJA, 1, cv2.LINE_AA)
        cv2.putText(img, c["motivo"], (8, y0 + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    GRIS, 1, cv2.LINE_AA)
        cv2.putText(img, "rechazos %d   intervenciones %d" % (rechazos, interv),
                    (8, y0 + 52), cv2.FONT_HERSHEY_SIMPLEX, 0.5, BLANCO, 1, cv2.LINE_AA)
        vw.write(img)
        escritos += 1

    cap.release()
    if vw is not None:
        vw.release()
    fcsv.close()
    tot = max(sum(cnt.values()), 1)
    print("  %-34s %5d frames | %s" % (base, tot,
          "  ".join("%s %.0f%%" % (k, 100.0 * cnt.get(k, 0) / tot)
                    for k in ("HIGH", "MEDIUM", "LOW", "SIN_CERCA", "PERDIDA"))))
    print("  %-34s inversiones rechazadas %d   intervenciones %d   avi %d frames"
          % ("", rechazos, interv, escritos))
    return dict(estados=cnt, rechazos=rechazos, interv=interv, n=tot,
                avi=sal_avi, csv=sal_csv)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="?", default="")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=10 ** 9)
    ap.add_argument("--tag", default="")
    ap.add_argument("--ventana", type=int, default=600, help="ms de sostenimiento en LOW")
    ap.add_argument("--todos", action="store_true")
    a = ap.parse_args()

    if a.todos:
        import glob
        print("  ESTADOS DE CONFIANZA POR VIDEO")
        print("  " + "-" * 90)
        for v in sorted(glob.glob(os.path.join(AQUI, "*.avi"))):
            b = os.path.basename(v)
            if b.startswith(("shadow_", "comparacion", "centrado", "CONTROL", "CASO")):
                continue
            correr(v, 0, 10 ** 9, "", a.ventana, con_video=False)
        return 0

    if not a.video:
        print(__doc__)
        return 2
    ruta = a.video if os.path.isabs(a.video) else os.path.join(AQUI, a.video)
    if not os.path.exists(ruta):
        print("*** no existe %s" % ruta)
        return 2
    correr(ruta, a.desde, a.hasta, a.tag, a.ventana)
    return 0


if __name__ == "__main__":
    sys.exit(main())

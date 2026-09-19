# -*- coding: utf-8 -*-
"""CUAL DE LOS ESTIMADORES REACCIONA MEJOR EN UN CODO, Y QUE HARIA EL ROBOT.

Benjamin, 26-ago: "el video de registro completo tiene todos los que se usan,
puedes ver cual es mejor para usar y como tendria que reaccionar el robot".

Corre el pipeline sobre el video y saca, frame a frame:
  ang_atan2   la ley de HOY (centroide de la mancha, Main.py:887)
  ang_camino  el planner (VISION_LINEA=camino), o sea la aguja gris del video
y para cada uno calcula QUE HARIA EL ROBOT: rot, radio y avance, con el algebra
del drivebase y las constantes medidas.

    python comparar_estimadores.py hist.avi 1354 1490
"""
import os, sys, math
os.environ.setdefault("VISION_LINEA", "camino")
import numpy as np, cv2

AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
import vision_linea                                            # noqa: E402

GAIN, EXP, PIVOT = 1.35, 0.50, 0.92
B_EFF, APERTURA = 20.9, 1.15

def robot(steer):
    """steer [-1,1] -> (rot, R trazado en cm, avance como fraccion de vel)"""
    ab = min(abs(steer) * GAIN, 1.0)
    rot = 1.0 if ab >= PIVOT else ab ** EXP
    R = (B_EFF * (1 - rot) / (2 * rot) * APERTURA) if rot > 1e-9 else 0.0
    return rot, R, 1.0 - rot

# ============================================================================
#  RETRACTACION 26-ago: la v1 de este script media MAL y hay que dejarlo escrito.
#
#  `hist.avi` NO es el frame de la camara: es un video de DEBUG de 640x240 con
#  DOS PANELES -izquierda la camara, derecha la mascara-. La v1 redimensionaba
#  los 640x240 ENTEROS a 160x120 y contaba pixeles negros, o sea que contaba
#  sobre todo el PANEL DE LA MASCARA, que es casi todo negro. Daba 5200 px
#  constantes y "la linea nunca se pierde", que es falso: en el frame 1420 la
#  mascara esta practicamente vacia y el cartel del propio video dice
#  "viejo -88 / manda -88", o sea saturado.
#
#  Es exactamente el error que el proyecto ya tiene anotado como regla:
#  ANTES DE INSTRUMENTAR, PREGUNTA QUE MIDE REALMENTE EL CAMPO.
#
#  Ahora se usa SOLO el panel izquierdo (320x240 -> 160x120), que es la imagen
#  de la camara al doble de resolucion.
# ============================================================================
def panel_camara(frame):
    """Del video de debug de 640x240 saca la imagen de la camara, 160x120."""
    h, w = frame.shape[:2]
    if w == 640 and h == 240:
        frame = frame[:, :320]
    return cv2.resize(frame, (160, 120))


def atan2_hoy(frame):
    """Reproduce Main.py:863-887: ROI, mascara, centroide pesado, atan2."""
    f = panel_camara(frame)
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    m = (g < 90).astype(np.uint8) * 255
    m[:55, :] = 0
    ys, xs = np.nonzero(m)
    if len(xs) < 50:
        return None, len(xs)
    x = (xs / 160.0) - 0.5
    y = 1.0 - (ys / 120.0)
    xr = float(np.sum(x * (1 - y)))
    yr = float(np.sum(y))
    if xr == 0 and yr == 0:
        return None, len(xs)
    ang = math.degrees(math.atan2(yr, xr)) - 90.0
    return max(-90.0, min(90.0, ang)), len(xs)

def main():
    vid = sys.argv[1] if len(sys.argv) > 1 else "hist.avi"
    f0 = int(sys.argv[2]) if len(sys.argv) > 2 else 1354
    f1 = int(sys.argv[3]) if len(sys.argv) > 3 else 1490
    cap = cv2.VideoCapture(os.path.join(AQUI, vid))
    if not cap.isOpened():
        print("no se pudo abrir", vid); return 1
    print("")
    print("=" * 100)
    print("  %s  frames %d-%d   |   vision_linea ACTIVA=%s modo=%s"
          % (vid, f0, f1, vision_linea.ACTIVA, vision_linea.estado().get("modo")))
    print("=" * 100)
    print("")
    print("  %6s %7s %9s %9s | %6s %8s %8s | %6s %8s %8s"
          % ("frame", "px_neg", "atan2", "camino", "rot_a", "R_a", "avan_a",
             "rot_c", "R_c", "avan_c"))
    print("  " + "-" * 92)
    A, C, NP, i = [], [], [], 0
    while True:
        ok, fr = cap.read()
        if not ok or i > f1:
            break
        if i >= f0:
            aa, npx = atan2_hoy(fr)
            f = panel_camara(fr)
            try:
                ac = vision_linea.angulo(f)
            except Exception:
                ac = None
            A.append(aa); C.append(ac); NP.append(npx)
            if (i - f0) % 8 == 0:
                ra, Ra, va = robot(aa / 90.0) if aa is not None else (0, 0, 0)
                rc, Rc, vc = robot(ac / 90.0) if ac is not None else (0, 0, 0)
                print("  %6d %7d %9s %9s | %6.3f %8s %7.0f%% | %6.3f %8s %7.0f%%"
                      % (i, npx,
                         ("%.1f" % aa) if aa is not None else "  --",
                         ("%.1f" % ac) if ac is not None else "  --",
                         ra, ("%.1f" % Ra) if ra < 1 else "PIVOTE", 100 * va,
                         rc, ("%.1f" % Rc) if rc < 1 else "PIVOTE", 100 * vc))
        i += 1
    cap.release()

    def resumen(nom, V):
        v = [x for x in V if x is not None]
        if not v:
            print("  %-10s SIN OPINION en los %d frames" % (nom, len(V))); return
        s = np.array(v) / 90.0
        rot = np.array([robot(x)[0] for x in s])
        avan = 1 - rot
        flips = int(np.sum(np.diff(np.sign(np.array(v))) != 0))
        d = np.abs(np.diff(np.array(v)))
        print("  %-10s n=%3d/%3d  |ang| p50=%5.1f  saltos p50=%4.1f p90=%5.1f  "
              "flips=%2d  %%pivote=%3.0f%%  avance=%.2f"
              % (nom, len(v), len(V), np.median(np.abs(v)),
                 np.median(d) if len(d) else 0,
                 np.percentile(d, 90) if len(d) else 0,
                 flips, 100 * np.mean(rot >= 0.999), avan.mean()))
    print("")
    print("=" * 100)
    print("  RESUMEN DEL TRAMO")
    print("=" * 100)
    print("")
    resumen("atan2 HOY", A)
    resumen("camino", C)
    if NP:
        import numpy as _np
        n=_np.array(NP); print("")
        print("  pixeles negros en el ROI: p50=%d  min=%d  |  frames con <50 px: %d de %d"
              % (_np.median(n), n.min(), int((n<50).sum()), len(n)))
        print("  (Main.py exige black_sum >= min_line_size para creerle a la vision)")
    print("")
    print("  flips = cuantas veces el comando CAMBIA DE LADO. En un codo el robot")
    print("  tiene que girar para UN lado: cada flip es medio giro tirado.")
    return 0

if __name__ == "__main__":
    sys.exit(main())

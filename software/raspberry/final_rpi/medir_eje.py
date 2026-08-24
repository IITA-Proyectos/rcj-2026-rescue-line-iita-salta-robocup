# -*- coding: utf-8 -*-
"""
MEDIR_EJE - el dato fisico que tiene suspendido a T4 desde hace semanas.

QUE FALTA Y POR QUE IMPORTA
---------------------------
`bearing_suelo.py` dejo T4 NI SOSTENIDO NI REFUTADO, suspendido por un unico
dato que no esta en ningun video ni en ningun CSV: **donde cae el EJE DE
ROTACION del robot dentro del campo visual**.

  * `bearing_px` es un bearing desde el centro optico de la camara.
  * el bird-eye mide desde el borde inferior de la imagen.
  * al robot le importa el bearing desde SU EJE DE ROTACION, que no es ninguno
    de los dos.

Y NO se puede sacar de la telemetria: el robot giro OBEDECIENDO a `steer`, asi
que `steer` correlaciona con `gz` por construccion. Es circular.

Con `d_eje` medido, `bearing_desde_el_eje = atan2(X, Z + d_eje)` queda
determinado y las tres leyes se pueden comparar de verdad.

EL TRUCO QUE HACE QUE ESTO SEA UNA REGRESION LINEAL
---------------------------------------------------
De `birdeye.py` (validado, R2 0,982-0,999 en 9 de 11 videos): para una camara
pinhole mirando un plano,

    ancho aparente de una cinta      w(v) = a * (v - v_h)
    distancia de la fila v           Z(v) = k / (v - v_h)

Si medimos con regla la distancia D DESDE EL EJE hasta el punto del piso que
cae en la fila v, entonces

    D(v) = k / (v - v_h)  +  d_eje

que es una RECTA en x = 1/(v - v_h):

    D = k * x + d_eje

**La ordenada al origen ES d_eje.** Con 3-4 mediciones sale por minimos
cuadrados, con residuos y R2 para saber si creerle. No hace falta calibrar la
camara ni desarmar nada.

PROCEDIMIENTO EN LA PISTA  (~20 minutos, robot quieto)
------------------------------------------------------
PASO 0 - encontrar el eje de rotacion REAL. Con 4 ruedas fijas el centro de
  rotacion NO es el centro geometrico: se corre hacia el eje delantero y depende
  de la superficie. Se encuentra asi, y es exacto para un cuerpo rigido:

    a. hoja de papel grande abajo del robot, fija con cinta al piso;
    b. marcar en el papel DOS puntos del chasis (p.ej. proyectando con una
       plomada o un lapiz a plomo el centro del paragolpes y el centro trasero);
    c. hacer que el robot pivotee en el lugar ~90 grados;
    d. marcar en el papel LOS MISMOS DOS puntos del chasis en la nueva pose;
    e. unir cada punto con su nueva posicion: son dos segmentos. Trazar la
       MEDIATRIZ de cada uno. Se cruzan en el centro de rotacion.
    f. marcar ese cruce. Ese es el origen de todas las distancias.

  Repetir con el robot apuntando al otro lado y promediar. Si los dos cruces
  difieren mas de ~1 cm, anotarlo: el centro de rotacion no es estable y eso
  es en si mismo un hallazgo.

PASO 1 - foto LONGITUDINAL. Cinta negra apoyada en el piso A LO LARGO del eje
  de avance, como si fuera la pista. Da `a` y `v_h` de una sola foto:

    python3 medir_eje.py --capturar --tipo longitudinal --ancho-cinta-cm 1.9

PASO 2 - fotos TRAVESAÑO. Cinta negra PERPENDICULAR al eje de avance, a 3 o 4
  distancias distintas. Cada vez se mide con regla del centro de rotacion al
  BORDE MAS CERCANO de la cinta y se pasa ese numero:

    python3 medir_eje.py --capturar --tipo travesano --dist-cm 25
    python3 medir_eje.py --capturar --tipo travesano --dist-cm 35
    python3 medir_eje.py --capturar --tipo travesano --dist-cm 50
    python3 medir_eje.py --capturar --tipo travesano --dist-cm 70

  Elegir distancias que caigan REPARTIDAS entre la fila 119 y la fila 40; si las
  cuatro caen abajo el ajuste no tiene palanca.

PASO 3 - ajustar:

    python3 medir_eje.py --ajustar

VALIDACION OFFLINE
------------------
    python3 medir_eje.py --simular

Genera datos sinteticos con k/d_eje/v_h conocidos y verifica que el ajuste los
recupera. Sirve para probar la matematica sin la Pi.

NO TOCA la candidata, NO TOCA el firmware, NO mueve el robot.
"""

import argparse
import importlib.util
import json
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(AQUI, "medicion_eje.json")

# Horizonte medido en birdeye.py el 2026-08-23 (mediana de 11 videos).
VH_BIRDEYE = 9.0


def cargar_v2():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v2", os.path.join(AQUI, "nuevo_code_v2.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


# --------------------------------------------------------------------------
# AJUSTES
# --------------------------------------------------------------------------
def recta(x, y):
    """Minimos cuadrados y = m*x + b. Devuelve m, b, R2, residuos."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    n = len(x)
    if n < 2:
        return None
    m, b = np.polyfit(x, y, 1)
    pred = m * x + b
    res = y - pred
    ss_res = float((res ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return dict(m=float(m), b=float(b), r2=float(r2),
                residuos=[float(r) for r in res],
                rms=float(math.sqrt(ss_res / n)), n=n)


def ajustar_horizonte(filas, anchos):
    """w(v) = a*(v - v_h). Devuelve a, v_h."""
    f = recta(filas, anchos)
    if f is None or abs(f["m"]) < 1e-12:
        return None
    f["a"] = f["m"]
    f["v_h"] = -f["b"] / f["m"]
    return f


def ajustar_eje(filas, dists_cm, v_h):
    """D(v) = k/(v - v_h) + d_eje. Recta en x = 1/(v - v_h)."""
    filas = np.asarray(filas, float)
    if np.any(filas <= v_h + 1e-6):
        return {"error": "hay filas por encima del horizonte v_h=%.2f" % v_h}
    x = 1.0 / (filas - v_h)
    f = recta(x, dists_cm)
    if f is None:
        return {"error": "hacen falta al menos 2 travesanos"}
    f["k"] = f["m"]
    f["d_eje_cm"] = f["b"]
    f["v_h_usado"] = float(v_h)
    return f


def sensibilidad_vh(filas, dists_cm, v_h, delta=3.0):
    """Cuanto se mueve d_eje si v_h estuviera mal por +-delta filas."""
    out = {}
    for d in (-delta, 0.0, +delta):
        r = ajustar_eje(filas, dists_cm, v_h + d)
        out["v_h%+.0f" % d] = (None if "error" in r
                               else round(r["d_eje_cm"], 2))
    return out


# --------------------------------------------------------------------------
# DETECCION EN LA IMAGEN
# --------------------------------------------------------------------------
def mascara_negra(v2, g):
    return cv2.inRange(g, v2.LO, v2.HI)


def anchos_por_fila(v2, m, fila_min=None, fila_max=None):
    """Para una cinta LONGITUDINAL: ancho de la corrida mas larga por fila."""
    H, W = m.shape
    fila_min = v2.FLOOR_TOP if fila_min is None else fila_min
    fila_max = H - 1 if fila_max is None else fila_max
    filas, anchos = [], []
    for v in range(fila_min, fila_max + 1):
        xs = np.where(m[v] > 0)[0]
        if len(xs) < 2:
            continue
        rr = v2.runs_1d(xs)
        if not rr:
            continue
        r = max(rr, key=lambda q: q[1] - q[0])
        w = r[1] - r[0] + 1
        if w < 2 or w > 0.8 * W:
            continue
        filas.append(v)
        anchos.append(w)
    return filas, anchos


def fila_travesano(v2, m):
    """Para una cinta PERPENDICULAR: fila del borde MAS CERCANO (mayor v)
    de la componente negra mas grande."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(
        (m > 0).astype(np.uint8), 8)
    if n < 2:
        return None
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    ys, xs = np.nonzero(lab == k)
    return dict(fila_cerca=int(ys.max()), fila_lejos=int(ys.min()),
                area=int(stats[k, cv2.CC_STAT_AREA]),
                ancho_px=int(xs.max() - xs.min() + 1))


def anotar(v2, g, m, fila_marcada=None):
    """PNG ampliado con regla de filas, para leer a ojo si hace falta."""
    E = 6
    vis = cv2.resize(g, (v2.W * E, v2.H * E),
                     interpolation=cv2.INTER_NEAREST)
    sombra = cv2.resize((m > 0).astype(np.uint8) * 255,
                        (v2.W * E, v2.H * E),
                        interpolation=cv2.INTER_NEAREST)
    vis[sombra > 0] = (0.5 * vis[sombra > 0]
                       + 0.5 * np.array([0, 0, 255])).astype(np.uint8)
    for v in range(0, v2.H, 10):
        y = v * E
        cv2.line(vis, (0, y), (vis.shape[1] - 1, y), (80, 80, 80), 1)
        cv2.putText(vis, str(v), (3, y - 3), cv2.FONT_HERSHEY_SIMPLEX,
                    0.35, (160, 160, 160), 1, cv2.LINE_AA)
    cv2.line(vis, (0, v2.FLOOR_TOP * E), (vis.shape[1] - 1, v2.FLOOR_TOP * E),
             (255, 160, 60), 1)
    cv2.putText(vis, "FLOOR_TOP %d" % v2.FLOOR_TOP,
                (60, v2.FLOOR_TOP * E - 4), cv2.FONT_HERSHEY_SIMPLEX,
                0.4, (255, 160, 60), 1, cv2.LINE_AA)
    if fila_marcada is not None:
        y = int(fila_marcada) * E
        cv2.line(vis, (0, y), (vis.shape[1] - 1, y), (60, 255, 60), 2)
        cv2.putText(vis, "fila %d" % fila_marcada, (60, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 255, 60), 1,
                    cv2.LINE_AA)
    return vis


# --------------------------------------------------------------------------
# ESTADO PERSISTENTE
# --------------------------------------------------------------------------
def leer_datos():
    if os.path.exists(DATOS):
        with open(DATOS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"longitudinal": None, "travesanos": []}


def escribir_datos(d):
    with open(DATOS, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)


# --------------------------------------------------------------------------
# CAPTURA
# --------------------------------------------------------------------------
def capturar(a, v2):
    cap = cv2.VideoCapture(a.camara)
    if not cap.isOpened():
        print("*** no abre el dispositivo %d" % a.camara)
        print("    si el servicio tiene la camara: sudo systemctl stop "
              "iita-robot")
        return 2
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, a.ancho)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, a.alto)
    for _ in range(10):                       # descartar frames de arranque
        cap.read()
    acum = None
    n = 0
    for _ in range(a.promediar):
        ok, fr = cap.read()
        if not ok:
            continue
        g = v2.frame_pi(fr).astype(np.float32)
        acum = g if acum is None else acum + g
        n += 1
    cap.release()
    if not n:
        print("*** no se pudo leer ningun frame")
        return 2
    g = (acum / n).astype(np.uint8)           # promedio: baja el ruido
    m = mascara_negra(v2, g)

    d = leer_datos()
    base = a.etiqueta or ("%s_%s" % (a.tipo, a.dist_cm if a.dist_cm else "0"))
    png_raw = os.path.join(AQUI, "eje_%s.png" % base)
    png_ann = os.path.join(AQUI, "eje_%s_anotada.png" % base)

    if a.tipo == "longitudinal":
        filas, anchos = anchos_por_fila(v2, m)
        if len(filas) < 10:
            print("*** solo %d filas con cinta. Revisa luz/encuadre: mira %s"
                  % (len(filas), png_ann))
            cv2.imwrite(png_ann, anotar(v2, g, m))
            return 3
        f = ajustar_horizonte(filas, anchos)
        d["longitudinal"] = dict(
            filas=filas, anchos=anchos, ancho_cinta_cm=a.ancho_cinta_cm,
            a=f["a"], v_h=f["v_h"], r2=f["r2"], png=png_raw)
        print("  filas con cinta   %d  (de %d a %d)"
              % (len(filas), min(filas), max(filas)))
        print("  ajuste w(v)=a*(v-v_h)   a=%.4f px/fila   v_h=%.2f   R2=%.4f"
              % (f["a"], f["v_h"], f["r2"]))
        print("  v_h de birdeye (2026-08-23): %.1f    diferencia %+.2f filas"
              % (VH_BIRDEYE, f["v_h"] - VH_BIRDEYE))
        if f["r2"] < 0.95:
            print("  *** R2 bajo. La cinta no esta recta, o hay reflejos, o el")
            print("      plano no es plano. Repetir antes de seguir.")
        cv2.imwrite(png_ann, anotar(v2, g, m))
    else:
        if a.dist_cm is None:
            print("*** falta --dist-cm (regla: centro de rotacion -> borde "
                  "MAS CERCANO de la cinta)")
            return 2
        r = fila_travesano(v2, m)
        if r is None:
            print("*** no se detecto la cinta. Mira %s" % png_ann)
            cv2.imwrite(png_ann, anotar(v2, g, m))
            return 3
        fila = a.fila if a.fila is not None else r["fila_cerca"]
        d["travesanos"] = [t for t in d["travesanos"]
                           if abs(t["dist_cm"] - a.dist_cm) > 1e-6]
        d["travesanos"].append(dict(
            dist_cm=a.dist_cm, fila=int(fila),
            fila_cerca=r["fila_cerca"], fila_lejos=r["fila_lejos"],
            area=r["area"], ancho_px=r["ancho_px"], png=png_raw))
        d["travesanos"].sort(key=lambda t: t["dist_cm"])
        print("  travesano a %.1f cm  ->  fila cercana %d  (lejana %d, "
              "area %d px)" % (a.dist_cm, r["fila_cerca"], r["fila_lejos"],
                               r["area"]))
        if a.fila is not None:
            print("  fila FORZADA a mano: %d" % fila)
        if r["area"] < 30:
            print("  *** area chica: puede ser ruido y no la cinta. Mira %s"
                  % png_ann)
        cv2.imwrite(png_ann, anotar(v2, g, fila_marcada=fila, m=m))

    cv2.imwrite(png_raw, g)
    escribir_datos(d)
    print("  guardado en %s" % DATOS)
    print("  imagenes: %s  %s" % (png_raw, png_ann))
    return 0


# --------------------------------------------------------------------------
# AJUSTE FINAL
# --------------------------------------------------------------------------
def ajustar(a):
    d = leer_datos()
    tr = d.get("travesanos") or []
    if len(tr) < 2:
        print("*** hacen falta al menos 2 travesanos (hay %d). "
              "Idealmente 3 o 4." % len(tr))
        return 2

    lon = d.get("longitudinal")
    if a.vh is not None:
        v_h, origen = a.vh, "forzado por --vh"
    elif lon:
        v_h, origen = lon["v_h"], "medido en la foto longitudinal"
    else:
        v_h, origen = VH_BIRDEYE, "birdeye 2026-08-23 (NO se midio hoy)"

    filas = [t["fila"] for t in tr]
    dists = [t["dist_cm"] for t in tr]
    r = ajustar_eje(filas, dists, v_h)
    if "error" in r:
        print("*** %s" % r["error"])
        return 3

    print("")
    print("=" * 70)
    print("  MEDICION DEL EJE DE ROTACION")
    print("=" * 70)
    print("")
    print("  v_h = %.2f   (%s)" % (v_h, origen))
    if lon:
        print("  a   = %.4f px/fila   R2 %.4f   cinta de %.2f cm"
              % (lon["a"], lon["r2"], lon.get("ancho_cinta_cm") or 0.0))
    print("")
    print("  travesanos medidos")
    print("    %8s %6s %10s %10s %9s"
          % ("dist cm", "fila", "1/(v-v_h)", "predicho", "residuo"))
    for t, res in zip(tr, r["residuos"]):
        x = 1.0 / (t["fila"] - v_h)
        print("    %8.1f %6d %10.5f %10.2f %+9.2f"
              % (t["dist_cm"], t["fila"], x, t["dist_cm"] - res, res))
    print("")
    print("  AJUSTE  D(v) = k/(v - v_h) + d_eje")
    print("    k        %10.2f cm*fila" % r["k"])
    print("    d_eje    %10.2f cm     <-- EL DATO QUE FALTABA" % r["d_eje_cm"])
    print("    R2       %10.4f" % r["r2"])
    print("    RMS      %10.2f cm" % r["rms"])
    print("    n        %10d" % r["n"])
    print("")
    s = sensibilidad_vh(filas, dists, v_h)
    print("  SENSIBILIDAD a v_h (si el horizonte estuviera mal por +-3 filas)")
    print("    %s" % "   ".join("%s -> %s cm" % (k, v) for k, v in s.items()))
    print("")

    ok = True
    if r["r2"] < 0.98:
        print("  *** R2 %.4f < 0,98. El modelo Z ~ 1/(v-v_h) NO esta")
        print("      describiendo bien estas mediciones. Antes de usar d_eje:")
        print("      revisar que el piso sea plano, que la regla midiera desde")
        print("      el centro de rotacion, y que las filas sean del MISMO")
        print("      borde de la cinta en las cuatro fotos.")
        ok = False
    if r["d_eje_cm"] < 0:
        print("  *** d_eje NEGATIVO. Eso pondria el eje de rotacion ADELANTE")
        print("      del campo visual cercano. Casi seguro hay un signo o un")
        print("      origen equivocado en la medicion con regla.")
        ok = False
    if r["n"] < 3:
        print("  *** con 2 puntos la recta pasa exacta y R2 no dice nada.")
        print("      Medir un tercer travesano.")
        ok = False
    if ok:
        print("  RESULTADO ACEPTABLE. Con este d_eje ya se puede calcular")
        print("    bearing_desde_el_eje = atan2(X, k/(v-v_h) + d_eje)")
        print("  y comparar de verdad las tres leyes contra `steer`.")

    d["ajuste"] = dict(v_h=v_h, origen_v_h=origen, k=r["k"],
                       d_eje_cm=r["d_eje_cm"], r2=r["r2"], rms=r["rms"],
                       n=r["n"], sensibilidad_vh=s, aceptable=ok)
    escribir_datos(d)
    print("")
    print("  guardado en %s" % DATOS)
    print("=" * 70)
    return 0 if ok else 4


# --------------------------------------------------------------------------
# AUTOTEST
# --------------------------------------------------------------------------
def simular():
    print("")
    print("  AUTOTEST del ajuste con datos sinteticos")
    print("")
    rng = np.random.RandomState(7)
    fallas = 0
    for k_v, d_v, vh_v in ((900.0, 12.0, 9.0), (1400.0, 6.5, 4.0),
                           (700.0, 20.0, 12.0)):
        filas = np.array([45.0, 60.0, 85.0, 115.0])
        dist = k_v / (filas - vh_v) + d_v
        ruido = rng.normal(0, 0.25, size=len(filas))     # 2,5 mm de regla
        r = ajustar_eje(filas, dist + ruido, vh_v)
        ek = abs(r["k"] - k_v)
        ed = abs(r["d_eje_cm"] - d_v)
        ok = ed < 1.0 and r["r2"] > 0.99
        fallas += 0 if ok else 1
        print("    k=%7.1f d_eje=%5.1f v_h=%4.1f  ->  k=%7.1f d_eje=%5.2f "
              "R2=%.5f   err_d %.3f cm   %s"
              % (k_v, d_v, vh_v, r["k"], r["d_eje_cm"], r["r2"], ed,
                 "OK" if ok else "*** FALLA"))
        del ek
    # sensibilidad: v_h mal por 3 filas
    filas = np.array([45.0, 60.0, 85.0, 115.0])
    dist = 900.0 / (filas - 9.0) + 12.0
    r_mal = ajustar_eje(filas, dist, 12.0)
    print("")
    print("    con v_h equivocado en +3 filas: d_eje %5.2f cm en vez de 12,00 "
          "(error %+.2f)" % (r_mal["d_eje_cm"], r_mal["d_eje_cm"] - 12.0))
    print("    -> por eso conviene medir v_h con la foto longitudinal y no")
    print("       heredarlo de birdeye.")
    # horizonte
    v = np.arange(35, 120, 1.0)
    w = 0.085 * (v - 9.0)
    f = ajustar_horizonte(v, w + rng.normal(0, 0.05, size=len(v)))
    okh = abs(f["v_h"] - 9.0) < 1.5 and abs(f["a"] - 0.085) < 0.005
    fallas += 0 if okh else 1
    print("")
    print("    horizonte  a=0,0850 v_h=9,00  ->  a=%.4f v_h=%.2f R2=%.4f   %s"
          % (f["a"], f["v_h"], f["r2"], "OK" if okh else "*** FALLA"))
    print("")
    print("  RESULTADO:", "TODO OK" if fallas == 0 else "*** %d FALLAS"
          % fallas)
    return 0 if fallas == 0 else 1


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Medicion de d_eje. Desbloquea T4.")
    ap.add_argument("--capturar", action="store_true")
    ap.add_argument("--ajustar", action="store_true")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--tipo", choices=["longitudinal", "travesano"],
                    default="travesano")
    ap.add_argument("--dist-cm", type=float, default=None, dest="dist_cm",
                    help="regla: centro de rotacion -> borde MAS CERCANO")
    ap.add_argument("--fila", type=int, default=None,
                    help="forzar la fila a mano si la deteccion se equivoca")
    ap.add_argument("--ancho-cinta-cm", type=float, default=1.9,
                    dest="ancho_cinta_cm")
    ap.add_argument("--etiqueta", default=None)
    ap.add_argument("--camara", type=int, default=0)
    ap.add_argument("--ancho", type=int, default=160)
    ap.add_argument("--alto", type=int, default=120)
    ap.add_argument("--promediar", type=int, default=15,
                    help="frames promediados para bajar el ruido")
    ap.add_argument("--vh", type=float, default=None,
                    help="forzar v_h en el ajuste")
    a = ap.parse_args()

    if a.simular:
        return simular()
    if a.ajustar:
        return ajustar(a)
    if a.capturar:
        return capturar(a, cargar_v2())
    ap.print_help()
    print("")
    print("Empeza por:  python3 medir_eje.py --simular")
    return 1


if __name__ == "__main__":
    sys.exit(main())

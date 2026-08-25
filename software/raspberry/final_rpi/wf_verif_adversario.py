# -*- coding: utf-8 -*-
"""
VERIFICACION ADVERSARIA de wf_v1_vs_mejor.py.

No intenta confirmar: intenta ROMPER. Seis ataques:

  A) CONTAMINACION DEL BASELINE. wf_v1_vs_mejor parchea v2.path_target,
     v2.graph_from_skeleton y v2.dijkstra GLOBALMENTE y despues afirma que
     con las banderas apagadas el BASELINE es el de siempre. Su chequeo
     interno solo compara el target DENTRO del parche. Aca se corre una
     copia LIMPIA del modulo (nunca parcheada, instancia propia) en el mismo
     loop y se comparan los dos targets frame a frame. Si difieren en un
     solo frame, la comparacion es contra otra cosa.

  B) BANDA DE UMBRAL. La conclusion "V1 empeora saltos" se mide con
     UMBRAL = 24 px, que es EXACTAMENTE el clamp del guard espacial de V4
     (nuevo_code_v4.py:68 max_step = 24.0 a 33 fps). Con `>` estricto, el
     baseline tiene CERO saltos contiguos POR DEFINICION. Se barre la banda
     entera 8..48 px para ver si la conclusion depende del punto elegido.

  C) EL CLAMP COMO CEGUERA. Se cuenta cuantas veces el guard interviene
     (SPATIAL_LIMIT) y cuantas veces apaga el target (REACQ_PENDING /
     NO_SKELETON). Si el "cero saltos" del baseline se paga con apagones,
     la metrica de saltos no es comparable entre arquitecturas.

  D) DISPONIBILIDAD DEGENERADA DE V1. V1 gana disponibilidad. Se desglosa
     por motivo_target y se mide que fraccion de esa disponibilidad son
     reglas que devuelven una esquina literal de la imagen (multi_bottom,
     multi_bottom_hold) o el margen (sale_izquierda/derecha).

  E) CONTROLES. Valor exacto del steer maximo y de que regla sale en V1.

  F) DETERMINISMO. Se corre todo dos veces.

    python wf_verif_adversario.py
"""

import math
import os
import sys
from collections import Counter

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import ab_v2_v3_v4 as AB
import wf_v1_vs_mejor as WF

FPS = 100.0 / 3.0
BANDA = [8.0, 12.0, 16.0, 20.0, 22.0, 23.0, 24.0, 25.0, 26.0, 28.0, 32.0,
         40.0, 48.0]


# --------------------------------------------------------------------------
def steer(t, v2):
    if t is None:
        return None
    return float(np.clip(-90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90))


def pasada4(SB_lim, v2_lim, SB_par, v2_par, V1mod, ruta, fps,
            desde=0, hasta=10 ** 9):
    """Un solo decode, cuatro trackers.

    trA  copia LIMPIA del modulo, jamas parcheada     -> control de contaminacion
    trB  modulo parcheado, banderas APAGADAS          -> BASELINE de wf
    trC  modulo parcheado, banderas ENCENDIDAS        -> CAMINO+MONO
    trV  AirborneV1
    """
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise IOError(ruta)
    trA, trB, trC = SB_lim(fps), SB_par(fps), SB_par(fps)
    trV = V1mod.AirborneV1(fps)
    out = {"LIMPIO": [], "BASELINE": [], "CAMINO+MONO": [], "V1": []}
    extra = {"BASELINE": [], "CAMINO+MONO": [], "V1": []}
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        g = v2_par.frame_pi(fr)

        ra = trA.step(g)                       # modulo limpio, sin parche

        WF.CFG["camino"] = False
        WF.CFG["mono"] = False
        rb = trB.step(g)

        WF.CFG["camino"] = True
        WF.CFG["mono"] = True
        rc = trC.step(g)

        WF.CFG["camino"] = False
        WF.CFG["mono"] = False
        rv = trV.paso(g)

        if i >= desde:
            for nom, r, vv in (("LIMPIO", ra, v2_lim), ("BASELINE", rb, v2_par),
                               ("CAMINO+MONO", rc, v2_par)):
                t = r.get("target")
                out[nom].append((t, steer(t, vv), r.get("state")))
            for nom, r in (("BASELINE", rb), ("CAMINO+MONO", rc)):
                extra[nom].append(r.get("spatial_guard"))
            t = rv.get("target")
            a = rv.get("angle_target")
            out["V1"].append(
                (t, None if (t is None or a is None or not np.isfinite(a))
                 else float(a), rv.get("estado")))
            extra["V1"].append(rv.get("motivo_target"))
        i += 1
    cap.release()
    return out, extra


# --------------------------------------------------------------------------
def saltos_euclideos(serie):
    """Mismo recorrido que AB.metricas: contra el ultimo target que hubo."""
    s, ult = [], None
    for x in serie:
        t = x[0]
        if t is None:
            continue
        if ult is not None:
            s.append(math.hypot(t[0] - ult[0], t[1] - ult[1]))
        ult = t
    return s


def saltos_columna(serie):
    dxc, dxg = [], []
    ult, ulti = None, -1
    for i, x in enumerate(serie):
        t = x[0]
        if t is None:
            continue
        if ult is not None:
            d = abs(t[0] - ult[0])
            (dxc if i == ulti + 1 else dxg).append(d)
        ult, ulti = t, i
    return dxc, dxg


# --------------------------------------------------------------------------
def correr_todo(etiqueta):
    v4p, v2p, v1mod = WF.cargar()
    SBp = WF.hacer_sinbranch(v4p)
    v4l, v2l, _ = WF.cargar()                  # copia LIMPIA, nunca parcheada
    SBl = WF.hacer_sinbranch(v4l)

    WF.CHK["n"] = 0
    WF.CHK["mal"] = 0
    for k in WF.USO:
        WF.USO[k] = 0
    rest = WF.instalar(v2p)

    NOM = ("BASELINE", "CAMINO+MONO", "V1")
    ser = {n: [] for n in ("LIMPIO",) + NOM}
    ext = {n: [] for n in NOM}
    guard = {n: Counter() for n in ("BASELINE", "CAMINO+MONO")}
    mot = Counter()
    difA = 0
    nA = 0
    porvid = {}

    for vid in AB.AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        o, e = pasada4(SBl, v2l, SBp, v2p, v1mod, ruta, FPS)
        # --- ATAQUE A: el parche cambia el baseline? ----------------------
        for a, b in zip(o["LIMPIO"], o["BASELINE"]):
            nA += 1
            ta, tb = a[0], b[0]
            if (ta is None) != (tb is None):
                difA += 1
            elif ta is not None and (abs(ta[0] - tb[0]) > 1e-9
                                     or abs(ta[1] - tb[1]) > 1e-9):
                difA += 1
        for n in NOM:
            ser[n].extend(o[n])
            ext[n].extend(e[n])
        ser["LIMPIO"].extend(o["LIMPIO"])
        for n in ("BASELINE", "CAMINO+MONO"):
            guard[n].update([x for x in e[n] if x])
        mot.update([x for x in e["V1"] if x])
        porvid[vid] = {n: AB.metricas(o[n]) for n in NOM}

    rest()
    return ser, ext, guard, mot, difA, nA, porvid


# --------------------------------------------------------------------------
def main():
    print("")
    print("=" * 104)
    print("  VERIFICACION ADVERSARIA DE wf_v1_vs_mejor.py")
    print("=" * 104)

    ser, ext, guard, mot, difA, nA, porvid = correr_todo("corrida 1")

    NOM = ("BASELINE", "CAMINO+MONO", "V1")
    M = {n: AB.metricas(ser[n]) for n in NOM}
    ML = AB.metricas(ser["LIMPIO"])

    # ----------------------------------------------------------------------
    print("")
    print("  ATAQUE A - CONTAMINACION DEL BASELINE POR EL MONKEY-PATCH")
    print("    Copia limpia del modulo (jamas parcheada) contra el BASELINE de wf,")
    print("    frame a frame, target a target, sobre los 10 videos.")
    print("      frames comparados : %d" % nA)
    print("      discrepancias     : %d   %s"
          % (difA, "OK, el parche NO toca el baseline" if difA == 0
             else "*** EL PARCHE CONTAMINA EL BASELINE"))
    print("      chequeo interno de wf: %d frames, %d discrepancias"
          % (WF.CHK["n"], WF.CHK["mal"]))
    print("      (el interno solo cubre %d de %d frames: no mira los AHEAD ni "
          "los PERDIDA)" % (WF.CHK["n"], nA))
    print("      metricas del modulo LIMPIO : disp %.2f  sin_aut %d  huecos %d  "
          "s_gt %d  inv %d  suav %.2f"
          % (ML["disp"], ML["sin_aut"], ML["huecos"], ML["s_gt"], ML["inv"],
             ML["suav"]))
    print("      metricas del BASELINE de wf: disp %.2f  sin_aut %d  huecos %d  "
          "s_gt %d  inv %d  suav %.2f"
          % (M["BASELINE"]["disp"], M["BASELINE"]["sin_aut"],
             M["BASELINE"]["huecos"], M["BASELINE"]["s_gt"],
             M["BASELINE"]["inv"], M["BASELINE"]["suav"]))
    print("      publicado en la tarea      : disp 93.78  sin_aut 864  huecos 276"
          "  s_gt 247  inv 392  suav 1.91")

    # ----------------------------------------------------------------------
    eu = {n: saltos_euclideos(ser[n]) for n in NOM}
    col = {n: saltos_columna(ser[n]) for n in NOM}

    print("")
    print("  ATAQUE B - BANDA DE UMBRAL   (el 24 px es el clamp del guard, "
          "nuevo_code_v4.py:68)")
    print("    Si la conclusion 'V1 empeora saltos' solo vive en 24 px, es un "
          "artefacto del punto elegido.")
    print("")
    print("    SALTOS EUCLIDEOS > u          |  SALTOS DE COLUMNA > u        |"
          "  COLUMNA CONTIGUOS > u")
    print("    %5s %8s %8s %6s | %8s %8s %6s | %8s %8s %6s"
          % ("u px", "BASE", "C+MONO", "V1", "BASE", "C+MONO", "V1",
             "BASE", "C+MONO", "V1"))
    for u in BANDA:
        f = []
        for n in NOM:
            f.append(int((np.asarray(eu[n]) > u).sum()))
        for n in NOM:
            a = np.asarray(col[n][0] + col[n][1])
            f.append(int((a > u).sum()))
        for n in NOM:
            a = np.asarray(col[n][0]) if col[n][0] else np.array([0.0])
            f.append(int((a > u).sum()))
        print("    %5.0f %8d %8d %6d | %8d %8d %6d | %8d %8d %6d"
              % (u, f[0], f[1], f[2], f[3], f[4], f[5], f[6], f[7], f[8]))
    print("")
    print("    VEREDICTO DE LA BANDA: V1 pierde en saltos euclideos en %d de %d "
          "umbrales" % (sum(1 for u in BANDA
                            if (np.asarray(eu["V1"]) > u).sum()
                            > (np.asarray(eu["CAMINO+MONO"]) > u).sum()),
                        len(BANDA)))
    print("                           y en saltos de columna en %d de %d."
          % (sum(1 for u in BANDA
                 if (np.asarray(col["V1"][0] + col["V1"][1]) > u).sum()
                 > (np.asarray(col["CAMINO+MONO"][0]
                               + col["CAMINO+MONO"][1]) > u).sum()),
             len(BANDA)))

    print("")
    print("  ATAQUE B2 - LA COLA DE dxc DEL BASELINE PEGADA AL CLAMP")
    for n in ("BASELINE", "CAMINO+MONO"):
        a = np.asarray(col[n][0])
        print("    %-13s dxc contiguos: n=%d  max=%.4f  >23.0: %d  >23.9: %d  "
              ">24.0: %d" % (n, a.size, a.max(), int((a > 23.0).sum()),
                             int((a > 23.9).sum()), int((a > 24.0).sum())))
    a = np.asarray(col["V1"][0])
    print("    %-13s dxc contiguos: n=%d  max=%.4f  >23.0: %d  >23.9: %d  "
          ">24.0: %d" % ("V1", a.size, a.max(), int((a > 23.0).sum()),
                         int((a > 23.9).sum()), int((a > 24.0).sum())))

    # ----------------------------------------------------------------------
    print("")
    print("  ATAQUE C - EL 'CERO SALTOS' SE PAGA CON APAGONES?")
    print("    Acciones del guard espacial de V4 sobre los 10 videos.")
    for n in ("BASELINE", "CAMINO+MONO"):
        tot = sum(guard[n].values())
        print("    %-13s  %s" % (n, "  ".join(
            "%s %d (%.1f%%)" % (k, v, 100.0 * v / max(tot, 1))
            for k, v in sorted(guard[n].items(), key=lambda z: -z[1]))))

    # ----------------------------------------------------------------------
    print("")
    print("  ATAQUE D - DE QUE ESTA HECHA LA DISPONIBILIDAD DE V1")
    tot = sum(mot.values())
    DEGEN = ("multi_bottom", "multi_bottom_hold", "sale_izquierda",
             "sale_derecha", "doble_borde_left", "doble_borde_right",
             "lateral_persistente_left", "lateral_persistente_right")
    for k, v in sorted(mot.items(), key=lambda z: -z[1]):
        print("    %-28s %6d  %6.2f %%  %s"
              % (k, v, 100.0 * v / max(tot, 1),
                 "<- borde/esquina" if k in DEGEN else ""))
    deg = sum(v for k, v in mot.items() if k in DEGEN)
    con = M["V1"]["con"]
    n_tot = M["V1"]["n"]
    print("    frames con target de V1            : %d de %d  (disp %.2f %%)"
          % (con, n_tot, M["V1"]["disp"]))
    print("    de esos, por una regla de borde    : %d  (%.2f %% de los con "
          "target)" % (deg, 100.0 * deg / max(con, 1)))
    print("    disponibilidad NO degenerada de V1 : %.2f %%"
          % (100.0 * (con - deg) / max(n_tot, 1)))
    print("    disponibilidad de CAMINO+MONO      : %.2f %%"
          % M["CAMINO+MONO"]["disp"])

    # ----------------------------------------------------------------------
    print("")
    print("  ATAQUE E - CONTROLES POSITIVOS, VALOR EXACTO Y PROCEDENCIA")
    v4p, v2p, v1mod = WF.cargar()
    SBp = WF.hacer_sinbranch(v4p)
    v4l, v2l, _ = WF.cargar()
    SBl = WF.hacer_sinbranch(v4l)
    rest = WF.instalar(v2p)
    for cn, vid, fps, d0, h0, ex in AB.CONTROLES:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta) or not ex:
            continue
        o, e = pasada4(SBl, v2l, SBp, v2p, v1mod, ruta, fps, d0, h0)
        print("    --- %s   exige %d/%d" % (cn, ex, ex))
        for n in NOM:
            m = AB.metricas(o[n])
            st = [x[1] for x in o[n] if x[1] is not None]
            smax = max(st) if st else float("nan")
            smin = min(st) if st else float("nan")
            j = int(np.argmax([x[1] if x[1] is not None else -1e9
                               for x in o[n]]))
            proc = ("  regla=%s" % e["V1"][j]) if n == "V1" else ""
            print("        %-13s %3d/%-3d  %-6s  smax %+7.3f  smin %+7.3f%s"
                  % (n, m["con"], ex, "PASA" if m["con"] >= ex else "FALLA",
                     smax, smin, proc))
    rest()

    # ----------------------------------------------------------------------
    print("")
    print("  ATAQUE F - DETERMINISMO: segunda corrida completa")
    ser2, _e2, _g2, _m2, difA2, nA2, _pv2 = correr_todo("corrida 2")
    igual = True
    for n in NOM:
        m1, m2 = AB.metricas(ser[n]), AB.metricas(ser2[n])
        ok = all(abs(m1[k] - m2[k]) < 1e-9
                 for k in ("disp", "sin_aut", "huecos", "s_gt", "inv"))
        igual &= ok
        print("    %-13s corrida1 disp %.4f s_gt %d inv %d | corrida2 disp %.4f "
              "s_gt %d inv %d   %s"
              % (n, m1["disp"], m1["s_gt"], m1["inv"], m2["disp"], m2["s_gt"],
                 m2["inv"], "IGUAL" if ok else "*** DISTINTO"))
    print("    contaminacion corrida 2: %d/%d" % (difA2, nA2))

    print("")
    print("=" * 104)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
H10 - SELECCION RETROGRADA: la candidata puede elegir un target DETRAS del robot.

DE DONDE SALE
-------------
Auditando `seguir` f1186 con Benjamin. Yo habia dicho que ir a la izquierda ahi
era correcto porque era una horquilla. ERA FALSO. Se midio la rotacion real del
robot con correlacion de fase sobre el fondo del propio video: **+59 grados
monotonos a la DERECHA** entre f1140 y f1230, sin ninguna U. Para que ese
corrimiento fuera 180 grados la camara necesitaria 183 grados de campo.

O sea que la rama izquierda que la candidata siguio 20 frames era **el pedazo de
cinta que el robot ya habia pasado**.

EL MECANISMO
------------
El esqueleto es una curva conectada. Desde `start`, Dijkstra camina LOOKAHEAD px
en CUALQUIERA DE LOS DOS SENTIDOS, y en el score no hay nada que distinga
adelante de atras:

    s = 0,35|d-70| + 0,55 angdiff(rumbo, prev_heading) + 0,10 cont + 0,30 max(0,8-dy)

  * el gate `y <= sy+3` solo descarta lo que esta POR DEBAJO del start;
  * el termino 0,30*max(0,8-dy) muere a 8 filas y no discrimina nada a 18 o 39;
  * queda `prev_heading`, que sale de la eleccion del frame anterior.

Una vez enganchado para atras, volver a lo correcto cuesta ~38 puntos contra
~3 de seguir equivocado. Es un enganche que se sostiene solo.

QUE MIDE ESTE BANCO
-------------------
Para cada frame construye el arbol de caminos mas cortos que YA calculo la
candidata (se espian `graph_from_skeleton` y `dijkstra`: no se recalcula nada) y
para cada nodo computa el ALCANCE de su subarbol: la fila mas lejana (y minima)
a la que se puede llegar pasando por el.

    alcance(target elegido)  contra  el mejor alcance disponible en la shell

Si la candidata eligio una rama que se queda MUCHO mas cerca que otra que tenia
a mano, es candidata a seleccion retrograda. Se llama `delta_alcance` y se
reporta LA DISTRIBUCION COMPLETA, no un umbral elegido a mano: H6 ya cayo por
elegir un threshold a ojo.

CONTROLES QUE TIENEN QUE DAR CASI CERO
--------------------------------------
  lineal_positivo  f800-872   la curva cerrada que el robot SI completo
  hist_exito       f580-679

Si RETRO dispara fuerte ahi, la metrica es basura y H10 no se sostiene.

NO TOCA LA CANDIDATA. Espias reversibles.
"""

import argparse
import importlib.util
import math
import os
import sys

import numpy as np
import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

FPS = 100.0 / 3.0
AUTONOMOS = ["hist.avi", "lineal.avi", "lineal70.avi", "como_esta.avi",
             "seguir.avi", "rumbo.avi", "a.avi", "roi_auto.avi",
             "con_planner.avi", "con_planner2.avi"]
CONTROLES = [
    ("lineal_positivo", "lineal.avi", 800, 872),
    ("hist_exito", "hist.avi", 580, 679),
    ("hist_falla", "hist.avi", 1354, 1490),
    ("seguir_evento", "seguir.avi", 1160, 1200),
]
UMBRALES = (10, 15, 20, 30, 40)


def cargar():
    sp = importlib.util.spec_from_file_location(
        "nuevo_code_v4", os.path.join(AQUI, "nuevo_code_v4.py"))
    v4 = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(v4)
    return v4, v4.v3, v4.v3.v2


def hacer_sinbranch(v4):
    class _N(object):
        def step(self, p, s):
            return p, "PASA"

    class SinBranch(v4.NuevoCodeV4):
        def __init__(self, fps):
            v4.NuevoCodeV4.__init__(self, fps)
            self.branch_guard = _N()
    return SinBranch


CAP = {}


def espiar(v2):
    """Captura pts/adj de graph_from_skeleton, dist/prev/start de dijkstra y
    el res de path_target. Todo lo que ya calculo la candidata."""
    o_g = v2.graph_from_skeleton
    o_d = v2.dijkstra
    o_p = v2.NuevoCodeV2.path_target

    def g(sk):
        r = o_g(sk)
        CAP["pts"] = r[0]
        return r

    def d(adj, start):
        r = o_d(adj, start)
        CAP["dist"], CAP["prev"], CAP["start_i"] = r[0], r[1], start
        return r

    def p(self, comp, mode):
        CAP.clear()
        CAP["mode"] = mode
        sk, res = o_p(self, comp, mode)
        CAP["res"] = res
        return sk, res

    v2.graph_from_skeleton = g
    v2.dijkstra = d
    v2.NuevoCodeV2.path_target = p

    def restaurar():
        v2.graph_from_skeleton = o_g
        v2.dijkstra = o_d
        v2.NuevoCodeV2.path_target = o_p
    return restaurar


def alcance_subarbol(pts, dist, prev):
    """Para cada nodo, la fila MINIMA (mas lejana) alcanzable pasando por el.

    Se recorre el arbol de Dijkstra de hojas a raiz: orden decreciente de
    distancia garantiza que un hijo se procesa antes que su padre.
    """
    n = len(pts)
    alc = np.array([p[0] for p in pts], np.int32)      # y de cada nodo
    fin = np.where(np.isfinite(dist))[0]
    orden = fin[np.argsort(-dist[fin])]
    for i in orden:
        pa = prev[i]
        if pa != -1 and alc[i] < alc[pa]:
            alc[pa] = alc[i]
    return alc


def analizar_frame(v2, r):
    """Devuelve dict con delta_alcance, o None si el frame no aplica."""
    res = CAP.get("res")
    if res is None or "dist" not in CAP:
        return None
    modo = CAP.get("mode", "")
    if modo.startswith("AHEAD"):
        return {"ahead": True}
    pts, dist, prev = CAP["pts"], CAP["dist"], CAP["prev"]
    si = CAP["start_i"]
    sy, sx = pts[si]

    idx = {}
    for i, p in enumerate(pts):
        idx.setdefault(p, i)
    ty, tx = int(round(res["target"][1])), int(round(res["target"][0]))
    ti = idx.get((ty, tx))
    if ti is None:
        return {"sin_indice": True}

    lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
    fin = np.where(np.isfinite(dist))[0]
    shell = [i for i in fin if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
    fallback = False
    if not shell:
        shell = sorted(fin, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[
            :min(30, len(fin))]
        fallback = True
    if ti not in shell:
        return {"fuera_de_shell": True, "fallback": fallback}

    alc = alcance_subarbol(pts, dist, prev)
    alc_t = int(alc[ti])
    mejor = min(shell, key=lambda i: alc[i])
    alc_b = int(alc[mejor])
    return dict(
        delta=alc_t - alc_b, alc_t=alc_t, alc_b=alc_b,
        sy=int(sy), sx=int(sx), tx=tx, ty=ty,
        bx=int(pts[mejor][1]), by=int(pts[mejor][0]),
        lado_t=int(np.sign(tx - sx)), lado_b=int(np.sign(pts[mejor][1] - sx)),
        n_shell=len(shell), fallback=fallback,
    )


def corrida(SinBranch, v2, ruta, desde=0, hasta=10 ** 9):
    cap = cv2.VideoCapture(ruta)
    tr = SinBranch(FPS)
    out = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok or i > hasta:
            break
        g = v2.frame_pi(fr)
        r = tr.step(g)
        if i >= desde:
            a = analizar_frame(v2, r)
            t = r.get("target")
            s = None if t is None else float(np.clip(
                -90.0 * (t[0] - v2.CENTER) / (v2.W / 2.0), -90, 90))
            out.append(dict(i=i, an=a, target=t, steer=s,
                            state=r.get("state")))
        i += 1
    cap.release()
    return out


def saltos_con_huecos(reg, umbral=24.0):
    """Saltos > umbral medidos A TRAVES de los huecos, como el banco."""
    ult = None
    sal = []
    for k, x in enumerate(reg):
        t = x["target"]
        if t is None:
            continue
        if ult is not None:
            d = math.hypot(t[0] - ult[0], t[1] - ult[1])
            if d > umbral:
                sal.append(k)
        ult = t
    return sal


def inversiones(reg, dead=10.0):
    """Cambios de signo del steer con banda muerta, como el banco."""
    ult = None
    inv = []
    for k, x in enumerate(reg):
        s = x["steer"]
        if s is None or abs(s) < dead:
            continue
        if ult is not None and s * ult < 0:
            inv.append(k)
        ult = s
    return inv


def resumen(nombre, reg, det=False):
    ap = [x for x in reg if x["an"] and "delta" in x["an"]]
    n = len(ap)
    if not n:
        print("  %-18s (0 frames aplicables)" % nombre)
        return None
    d = np.array([x["an"]["delta"] for x in ap], float)
    fila = {"nombre": nombre, "n": n, "frames": len(reg)}
    for u in UMBRALES:
        fila["u%d" % u] = int((d >= u).sum())
    fila["pct15"] = 100.0 * (d >= 15).sum() / n
    fila["p50"] = float(np.percentile(d, 50))
    fila["p90"] = float(np.percentile(d, 90))
    fila["max"] = float(d.max())
    fila["cambia_lado"] = int(sum(
        1 for x in ap if x["an"]["delta"] >= 15
        and x["an"]["lado_t"] != x["an"]["lado_b"]))
    print("  %-18s %6d %6d %6d %6d %6d %6d   %6.2f %%   p50 %5.1f p90 %5.1f "
          "max %5.0f   lado dist. %d"
          % (nombre, n, fila["u10"], fila["u15"], fila["u20"], fila["u30"],
             fila["u40"], fila["pct15"], fila["p50"], fila["p90"],
             fila["max"], fila["cambia_lado"]))
    if det:
        for x in ap:
            a = x["an"]
            if a["delta"] >= 15:
                print("      f%-5d start(%3d,%3d)  elegido(%3d,%3d) alc %3d  "
                      "|  mejor(%3d,%3d) alc %3d   delta %3d  %s"
                      % (x["i"], a["sx"], a["sy"], a["tx"], a["ty"], a["alc_t"],
                         a["bx"], a["by"], a["alc_b"], a["delta"],
                         "LADO OPUESTO" if a["lado_t"] != a["lado_b"] else ""))
    return fila


def main():
    ap = argparse.ArgumentParser(description="H10 seleccion retrograda")
    ap.add_argument("--solo-controles", action="store_true",
                    dest="solo_controles")
    ap.add_argument("--detalle", action="store_true")
    a = ap.parse_args()

    v4, v3, v2 = cargar()
    SinBranch = hacer_sinbranch(v4)
    restaurar = espiar(v2)

    CAB = ("  %-18s %6s %6s %6s %6s %6s %6s   %8s   %-24s %s"
           % ("", "aplic", ">=10", ">=15", ">=20", ">=30", ">=40", "%>=15",
              "distribucion delta", "lado opuesto"))

    print("")
    print("=" * 108)
    print("  H10 - SELECCION RETROGRADA")
    print("  delta_alcance = (fila mas lejana alcanzable por la rama ELEGIDA)")
    print("                - (fila mas lejana alcanzable por la MEJOR de la shell)")
    print("  delta grande = la candidata eligio una rama que se queda cerca")
    print("                 teniendo otra que llegaba mucho mas lejos")
    print("=" * 108)

    print("")
    print("  CONTROLES  (los dos primeros TIENEN que dar casi cero)")
    print(CAB)
    ctrl = []
    for nom, vid, d, h in CONTROLES:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        reg = corrida(SinBranch, v2, ruta, d, h)
        ctrl.append(resumen(nom, reg, det=a.detalle or nom == "seguir_evento"))

    if a.solo_controles:
        restaurar()
        return 0

    print("")
    print("  DIEZ AUTONOMOS")
    print(CAB)
    tot = dict(n=0, u10=0, u15=0, u20=0, u30=0, u40=0, cambia_lado=0)
    todas = []
    asoc = [0, 0, 0, 0]        # salto&retro, salto&no, no-salto&retro, no&no
    global RACHAS, BASE
    RACHAS = []
    BASE = [0, 0, 0]
    for vid in AUTONOMOS:
        ruta = os.path.join(AQUI, vid)
        if not os.path.exists(ruta):
            continue
        reg = corrida(SinBranch, v2, ruta, 0, 10 ** 9)
        f = resumen(vid.replace(".avi", ""), reg)
        if f is None:
            continue
        for k in ("n", "u10", "u15", "u20", "u30", "u40", "cambia_lado"):
            tot[k] += f[k]
        todas.extend([x["an"]["delta"] for x in reg
                      if x["an"] and "delta" in x["an"]])
        # --- asociacion, con DOS correcciones de metodo -------------------
        # 1) solo frames APLICABLES en los dos grupos. Meter los no aplicables
        #    (PERDIDA / modo AHEAD) en el grupo "no RETRO" mete justo los
        #    frames donde viven los saltos y da una comparacion tramposa.
        # 2) la unidad correcta es la RACHA, no el frame: mientras el target
        #    va montado en la rama de atras se mueve suave. El salto llega
        #    cuando la racha SE AGOTA.
        sal = set(saltos_con_huecos(reg))
        inv = set(inversiones(reg))
        idx_ap = [k for k, x in enumerate(reg)
                  if x["an"] and "delta" in x["an"]]
        ap_set = set(idx_ap)
        retro_en = set(k for k in idx_ap if reg[k]["an"]["delta"] >= 15)
        for k in idx_ap:
            hay_salto = any((k < s <= k + 10) for s in sal)
            hay_retro = k in retro_en
            if hay_retro and hay_salto:
                asoc[0] += 1
            elif hay_retro:
                asoc[2] += 1
            elif hay_salto:
                asoc[1] += 1
            else:
                asoc[3] += 1
        # rachas: corridas de RETRO con tolerancia de 2 frames de hueco
        rr = sorted(retro_en)
        j = 0
        while j < len(rr):
            k = j
            while k + 1 < len(rr) and rr[k + 1] - rr[k] <= 2:
                k += 1
            ini, fin_r = rr[j], rr[k]
            RACHAS.append(dict(
                video=vid, ini=ini, fin=fin_r, largo=fin_r - ini + 1,
                opuesto=any(reg[m]["an"].get("lado_t") !=
                            reg[m]["an"].get("lado_b")
                            for m in range(ini, fin_r + 1)
                            if reg[m]["an"] and "delta" in reg[m]["an"]),
                inv_despues=any(fin_r < s <= fin_r + 10 for s in inv),
                # PLACEBO: misma ventana de 10 frames pero 2 s ANTES de que
                # empiece la racha. Si la zona es curva y ya tiene inversiones
                # por si sola, esto tiene que dar parecido y el efecto cae.
                inv_placebo=any(ini - 70 < s <= ini - 60 for s in inv),
                inv_antes=any(ini - 10 <= s < ini for s in inv),
                salto_despues=any(fin_r < s <= fin_r + 10 for s in sal),
                hueco_despues=any(reg[m]["target"] is None
                                  for m in range(fin_r + 1,
                                                 min(fin_r + 11, len(reg)))
                                  if m < len(reg)),
            ))
            j = k + 1
        # base: P(salto en los 10 frames siguientes) desde un frame aplicable
        BASE[0] += sum(1 for k in idx_ap
                       if any(k < s <= k + 10 for s in sal))
        BASE[1] += len(idx_ap)
        BASE[2] += sum(1 for k in idx_ap
                       if any(k < s <= k + 10 for s in inv))
        del ap_set

    d = np.array(todas, float)
    print("")
    print("  TOTAL")
    print("    frames aplicables        %d" % tot["n"])
    for u in UMBRALES:
        print("    delta >= %-3d             %6d   %5.2f %%"
              % (u, tot["u%d" % u], 100.0 * tot["u%d" % u] / max(tot["n"], 1)))
    print("    de los >=15, con la mejor rama del LADO OPUESTO   %d  (%.1f %%)"
          % (tot["cambia_lado"],
             100.0 * tot["cambia_lado"] / max(tot["u15"], 1)))
    print("")
    print("    distribucion de delta_alcance (filas)")
    for q in (50, 75, 90, 95, 99):
        print("      p%-3d %6.1f" % (q, np.percentile(d, q)))
    print("      max  %6.1f" % d.max())
    print("      delta == 0 en %.2f %% de los frames"
          % (100.0 * (d == 0).sum() / len(d)))

    print("")
    print("  ASOCIACION POR FRAME  (solo frames APLICABLES en los dos grupos)")
    a11, a01, a10, a00 = asoc
    pr_r = 100.0 * a11 / max(a11 + a10, 1)
    pr_nr = 100.0 * a01 / max(a01 + a00, 1)
    print("    P(salto en <=10 f | RETRO)     %6.2f %%   (%d de %d)"
          % (pr_r, a11, a11 + a10))
    print("    P(salto en <=10 f | no RETRO)  %6.2f %%   (%d de %d)"
          % (pr_nr, a01, a01 + a00))
    if pr_nr > 0:
        print("    razon de riesgo                %6.2f x" % (pr_r / pr_nr))

    print("")
    print("  ASOCIACION POR RACHA  (la unidad correcta: el salto llega cuando")
    print("  la racha SE AGOTA, no mientras dura)")
    if RACHAS:
        L = np.array([r["largo"] for r in RACHAS], float)
        con_s = sum(1 for r in RACHAS if r["salto_despues"])
        con_h = sum(1 for r in RACHAS if r["hueco_despues"])
        base = 100.0 * BASE[0] / max(BASE[1], 1)
        print("    rachas RETRO                   %d" % len(RACHAS))
        print("    largo  p50 %.0f  p90 %.0f  max %.0f frames"
              % (np.percentile(L, 50), np.percentile(L, 90), L.max()))
        print("    terminan en salto >24 px       %d  (%.1f %%)"
              % (con_s, 100.0 * con_s / len(RACHAS)))
        print("    terminan en hueco              %d  (%.1f %%)"
              % (con_h, 100.0 * con_h / len(RACHAS)))
        print("    base: P(salto en <=10 f) desde un frame aplicable  %.1f %%"
              % base)
        if base > 0:
            print("    razon de riesgo de la racha    %6.2f x"
                  % ((100.0 * con_s / len(RACHAS)) / base))
        base_i = 100.0 * BASE[2] / max(BASE[1], 1)
        con_i = sum(1 for r in RACHAS if r["inv_despues"])
        print("")
        print("    --- MISMO TEST CONTRA INVERSIONES DE STEER (banda 10 gr) ---")
        print("    el cap de continuidad convierte el flip en un barrido suave,")
        print("    asi que el salto >24 px NO aparece: la variable correcta es")
        print("    la inversion.")
        print("    rachas que terminan en inversion  %d  (%.1f %%)"
              % (con_i, 100.0 * con_i / len(RACHAS)))
        print("    base: P(inversion en <=10 f)      %.1f %%" % base_i)
        if base_i > 0:
            print("    razon de riesgo                   %6.2f x"
                  % ((100.0 * con_i / len(RACHAS)) / base_i))
        op = [r for r in RACHAS if r["opuesto"]]
        if op:
            ci = sum(1 for r in op if r["inv_despues"])
            cs = sum(1 for r in op if r["salto_despues"])
            print("")
            print("    --- SUBCONJUNTO LADO OPUESTO (la firma de seguir) ---")
            print("    rachas con la mejor rama del lado contrario  %d" % len(op))
            print("    terminan en inversion  %d (%.1f %%)  ->  %.2f x"
                  % (ci, 100.0 * ci / len(op),
                     (100.0 * ci / len(op)) / max(base_i, 1e-9)))
            print("    terminan en salto      %d (%.1f %%)  ->  %.2f x"
                  % (cs, 100.0 * cs / len(op),
                     (100.0 * cs / len(op)) / max(base, 1e-9)))
            cp = sum(1 for r in op if r["inv_placebo"])
            ca = sum(1 for r in op if r["inv_antes"])
            print("")
            print("    CONTROLES DE CONFUSION sobre las mismas %d rachas"
                  % len(op))
            print("      inversion en los 10 f DESPUES del final   %5.1f %%"
                  % (100.0 * ci / len(op)))
            print("      inversion en los 10 f ANTES del inicio    %5.1f %%"
                  % (100.0 * ca / len(op)))
            print("      PLACEBO: misma ventana 2 s antes          %5.1f %%"
                  % (100.0 * cp / len(op)))
            print("      base global                               %5.1f %%"
                  % base_i)
            print("      si el placebo se parece al 'despues', el efecto es")
            print("      de la ZONA curva y no de la racha: H10 cae igual.")
        largas = [r for r in RACHAS if r["largo"] >= 5]
        if largas:
            cs = sum(1 for r in largas if r["salto_despues"])
            print("    rachas de >=5 frames           %d, terminan en salto "
                  "%d (%.1f %%)  ->  %.2f x"
                  % (len(largas), cs, 100.0 * cs / len(largas),
                     (100.0 * cs / len(largas)) / max(base, 1e-9)))

    print("")
    print("  LECTURA")
    print("    H10 se sostiene si: los controles positivos dan casi cero, la")
    print("    distribucion NO es continua alrededor de 0, y la razon de riesgo")
    print("    contra los saltos es claramente > 1. Si la distribucion es")
    print("    continua, cualquier umbral es arbitrario y H10 cae igual que H6.")
    print("=" * 108)
    restaurar()
    return 0


if __name__ == "__main__":
    sys.exit(main())

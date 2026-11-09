# -*- coding: utf-8 -*-
"""CAMINO+MONO minimo para uso EN ROBOT.

Extraido de camino_principal.py, pero sin los bancos offline (AB, videos, main()).
Solo conserva instalar(), que parchea NuevoCodeV2.path_target para:
  - CAMINO: restringir candidatos a una cadena start->hoja lejana.
  - MONO: continuidad temporal ancestro->descendiente sobre el arbol Dijkstra.

No controla motores y no convierte target->steer.
"""
import math
import numpy as np

CAP = {}
USO = {"camino_vacio": 0, "camino_ok": 0, "mono_vacio": 0}


def es_ancestro(prev, ancla, cand):
    x = cand
    g = 0
    while x != -1 and g < 5000:
        if x == ancla:
            return True
        x = prev[x]
        g += 1
    return False


def instalar(v2, cfg):
    o_g, o_d = v2.graph_from_skeleton, v2.dijkstra
    o_p = v2.NuevoCodeV2.path_target
    o_r = v2.reconstruct

    def g(sk):
        r = o_g(sk)
        CAP["pts"] = r[0]
        return r

    def d(adj, start):
        r = o_d(adj, start)
        CAP["dist"], CAP["prev"], CAP["si"] = r[0], r[1], start
        return r

    def p(self, comp, mode):
        CAP.clear()
        sk, res = o_p(self, comp, mode)
        if res is None or "dist" not in CAP or mode.startswith("AHEAD"):
            return sk, res

        pts, dist, prev, si = CAP["pts"], CAP["dist"], CAP["prev"], CAP["si"]
        sy, sx = pts[si]
        lo, hi = max(18, v2.LOOKAHEAD - 16), v2.LOOKAHEAD + 18
        fin = np.where(np.isfinite(dist))[0]
        cands = [i for i in fin if lo <= dist[i] <= hi and pts[i][0] <= sy + 3]
        if not cands:
            cands = sorted(fin, key=lambda i: abs(dist[i] - v2.LOOKAHEAD))[:min(30, len(fin))]

        # CAMINO: una cadena start -> nodo alcanzable mas lejano.
        if cfg.get("camino") and len(fin):
            F = int(fin[int(np.argmax(dist[fin]))])
            lista = o_r(prev, si, F) or []
            cadena = set(lista)
            CAP["cadena"] = list(lista)
            CAP["cadena_pts"] = [tuple(pts[i]) for i in lista]
            sub = [i for i in cands if i in cadena]
            if sub:
                cands = sub
                USO["camino_ok"] += 1
            else:
                USO["camino_vacio"] += 1

        # MONO: proyectar target anterior al arbol actual y exigir descendencia.
        if cfg.get("mono") and self.prev_target is not None and len(fin):
            ys = np.array([q[0] for q in pts])
            xs = np.array([q[1] for q in pts])
            dd = ((xs[fin] - self.prev_target[0]) ** 2
                  + (ys[fin] - self.prev_target[1]) ** 2)
            ancla = int(fin[int(np.argmin(dd))])
            adm = [i for i in cands if es_ancestro(prev, ancla, i)]
            if adm:
                cands = adm
            else:
                USO["mono_vacio"] += 1

        # Misma funcion de score del planner original.
        def score(i):
            y, x = pts[i]
            dy = sy - y
            h = math.degrees(math.atan2(x - sx, max(dy, 1e-6)))
            s = 0.35 * abs(dist[i] - v2.LOOKAHEAD)
            s += 0.55 * v2.angdiff(h, self.prev_heading)
            if self.prev_target is not None:
                s += 0.10 * math.hypot(x - self.prev_target[0],
                                       y - self.prev_target[1])
            s += 0.30 * max(0, 8 - dy)
            return s

        if not cands:
            return sk, res

        ti = min(cands, key=score)
        ty, tx = pts[ti]
        camino = o_r(prev, si, ti) or [si, ti]
        return sk, dict(
            start=res["start"],
            target=(float(tx), float(ty)),
            # OJO: este heading es DER+ (derecha positiva), no el signo del
            # protocolo historico de steer, que usa derecha negativa.
            heading=math.degrees(math.atan2(tx - sx, max(sy - ty, 1e-6))),
            path=[(float(pts[i][1]), float(pts[i][0])) for i in camino],
        )

    v2.graph_from_skeleton, v2.dijkstra = g, d
    v2.NuevoCodeV2.path_target = p

    def restaurar():
        v2.graph_from_skeleton, v2.dijkstra = o_g, o_d
        v2.NuevoCodeV2.path_target = o_p

    return restaurar

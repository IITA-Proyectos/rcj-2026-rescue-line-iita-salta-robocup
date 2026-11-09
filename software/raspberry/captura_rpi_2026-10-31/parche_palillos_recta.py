# PALILLOS_RECTA para main.py (sobre d41ffec6). Despues del retroceso, si la cinta se ve partida por
# una franja angosta -el pedazo de abajo del robot y otro pedazo de cinta mas adelante, a PALILLOS_CORTE
# px o menos- en PALILLOS_RECTA cuadros, la decision pasa a RECTA (derecho, como un gap). La logica del
# gap vuelve a la cinta sola cuando la ve conectada otra vez. Una curva es una sola mancha y un gap de
# verdad deja un blanco ancho: no se tocan. 0 = como antes.
# Uso: python3 parche_palillos_recta.py main.py
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def rep(a, b):
    global s
    a = a.replace("\n", nl)
    b = b.replace("\n", nl)
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('''OBST_MAX_S       = 10.0
''', '''OBST_MAX_S       = 10.0
# PALILLOS EN LA RECUPERACION (17-oct, pista_.avi: 6:18, 6:47, 7:39, 9:00, 12:23, 14:21, 14:32). El
# reglamento deja escombros sueltos (palillos, varillas de hasta 3 mm) tambien sobre la linea. Una brocheta
# atravesada abajo del robot le corta la cinta y dispara la recuperacion; despues del retroceso la cinta
# se ve en pedazos y el arbitro elige CURVA (en 7:39, una recta, giro y salio de la pista). Con
# PALILLOS_RECTA=N, si en N cuadros despues del retroceso el pedazo de cinta de abajo esta a
# PALILLOS_CORTE px o menos de otro pedazo mas adelante, se decide RECTA: derecho, como en un gap.
# 0 = como antes.
PALILLOS_RECTA   = int(os.environ.get("PALILLOS_RECTA", "0"))
PALILLOS_CORTE   = float(os.environ.get("PALILLOS_CORTE", "14"))
''')

rep('''_obst = {"ini": 0.0, "fin": 0.0, "reset": False}''',
    '''_obst = {"ini": 0.0, "fin": 0.0, "reset": False}
_palillo = {"ts": None, "n": 0}   # PALILLOS_RECTA: cuadros con la cinta partida en este episodio''')

rep('''def _solo_mi_linea(mask):''', '''def _cinta_partida(frame_bgr):
    """PALILLOS_RECTA: True si el pedazo de cinta de abajo esta a PALILLOS_CORTE px o menos de otro
    pedazo de cinta mas adelante (lo que deja un palillo atravesado)."""
    try:
        b = cv2.inRange(frame_bgr, lower_black, upper_black)
        b[:50, :] = 0
        n, et, st, cen = cv2.connectedComponentsWithStats(b, 8)
        abajo = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 60 and
                 st[i, cv2.CC_STAT_TOP] + st[i, cv2.CC_STAT_HEIGHT] - 1 >= 105]
        if not abajo:
            return False
        i = max(abajo, key=lambda k: st[k, cv2.CC_STAT_AREA])
        dist = cv2.distanceTransform((et != i).astype(np.uint8), cv2.DIST_L2, 3)
        for j in range(1, n):
            if j == i or st[j, cv2.CC_STAT_AREA] < 40 or cen[j][1] >= cen[i][1] - 5:
                continue
            if float(dist[et == j].min()) <= PALILLOS_CORTE:
                return True
        return False
    except Exception:
        return False


def _solo_mi_linea(mask):''')

rep('''                                    except Exception as _ea:
                                        print("[PERDIDA] observe_post fallo: %s" % _ea)
                                _dec = _loss_arb.decide(now=_now_rec)''', '''                                    except Exception as _ea:
                                        print("[PERDIDA] observe_post fallo: %s" % _ea)
                                if PALILLOS_RECTA > 0:
                                    if _palillo["ts"] != _loss_retro_ts:
                                        _palillo["ts"] = _loss_retro_ts
                                        _palillo["n"] = 0
                                    if _cinta_partida(frame_resized):
                                        _palillo["n"] += 1
                                _dec = _loss_arb.decide(now=_now_rec)''')

rep('''                            # REV3: despues de TERM_HARD + SIDE_CHECK, congelar la primera
                            # decision final de CURVA hasta que termine el recovery.''', '''                            # PALILLOS_RECTA: la cinta partida por un palillo -> derecho, como un gap.
                            if (PALILLOS_RECTA > 0 and _curve_latched_decision is None and
                                    _dec.get("kind") != "RECTA" and _palillo["ts"] == _loss_retro_ts and
                                    _palillo["n"] >= PALILLOS_RECTA):
                                print("[PALILLO] cinta partida en %d cuadros: %s -> RECTA" % (
                                    _palillo["n"], _dec.get("kind")))
                                _dec = dict(kind="RECTA", side=0, heading=0.0, reason="palillo: cinta partida")
                                _loss_decision = _dec

                            # REV3: despues de TERM_HARD + SIDE_CHECK, congelar la primera
                            # decision final de CURVA hasta que termine el recovery.''')

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok palillos recta")

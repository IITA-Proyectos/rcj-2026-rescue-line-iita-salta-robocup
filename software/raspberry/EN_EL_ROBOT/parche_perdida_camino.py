#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PARCHE: LINEA PERDIDA — distinguir GAP de CURVA y girar hacia donde se fue.
2026-08-28. Idea de Benjamin.

EL PROBLEMA
  Cuando la linea desaparece del ROI, main.py manda angle = 0, o sea DERECHO.
  Pero la linea no desaparece por casualidad: o es un GAP -y derecho esta bien-
  o SE FUE POR UN COSTADO -y derecho la pierde-.

EL DISCRIMINADOR (de Benjamin)
  Un gap deja BLANCO a los costados. Una curva deja NEGRO en el borde por el
  que se fue. Medido sobre 52 eventos de perdida en las 5 corridas de atan2
  del 22-ago, mirando los 6 frames PREVIOS a la perdida y exigiendo que el
  negro del borde pertenezca a la COMPONENTE CONEXA MAS GRANDE (o sea que sea
  la linea, no el piso de madera ni otra cinta):

      0 de 6 frames con borde tocado ....  20 eventos   -> GAP
      1 a 5  (zona ambigua) ............   19 eventos
      6 de 6 ...........................   13 eventos   -> se fue de costado

  Y el lado es ambiguo -los dos bordes tocados- en solo el 10%.

POR QUE NO DA FALSOS POSITIVOS: TRES ZONAS CON ABSTENCION
  Los intentos anteriores de detectar el codo daban 87,5% de falsos positivos
  porque OBLIGABAN a decidir en cada frame. Este no.

      CURVA    >=5 de 6 frames con borde, un solo lado  -> gira hacia ese lado
      GAP      <=1 de 6                                 -> derecho (lo de hoy)
      ABSTIENE todo lo demas                            -> lo de hoy, sin cambio

  Abstenerse cuesta CERO: es exactamente el comportamiento actual.

EL PLANNER
  Si PLANNER esta encendido y opina (r["ok"]), la direccion sale del TRAZO:
  el signo de x_final - x_inicial de r["puntos"]. Eso es mas informativo que
  el borde -dice hacia donde VA el camino, no solo por donde salio-. Si el
  planner no opina, se usa el borde. El parche funciona con y sin planner.

OJO CON green_state = 4
  El `case 4` del firmware (main.cpp:4092) es "retroceder un paso corto" y
  NO USA EL ANGULO -lo dice el comentario de main.py:1067-. Asi que mandar
  green_state=4 DESCARTA la direccion, que es justo lo que se quiere avisar.
  Por eso:
      PERDIDA=1  manda el ANGULO hacia el lado. NO toca green_state.
                 Cero cambios en el firmware.
      PERDIDA=2  ademas manda green_state=4. Hoy eso anula el angulo: para que
                 sirva hay que tocar el case 4 del firmware primero.

COMO SE USA
  python3 parche_perdida_camino.py                # parchea /home/iita/Desktop/main.py
  python3 parche_perdida_camino.py --revertir

      PERDIDA=0                     python3 main.py   # apagado, igual que hoy
      PERDIDA=1 GRABAR=~/p1.avi     python3 main.py   # solo Pi
      PERDIDA=1 PLANNER=1 GRABAR=~/p1p.avi python3 main.py   # con el planner

  Variables: PERDIDA_ANG (defecto 75, igual que RECUP_ANG)
             PERDIDA_N   (defecto 6, cuantos frames de historial)
             PERDIDA_MIN (defecto 5, cuantos de N para decidir CURVA)
"""
import io, os, sys, glob, shutil

DEFECTO = "/home/iita/Desktop/main.py"
MARCA = "PARCHE PERDIDA"

ANCLA_INIT = (
    "_ult_lado = 0.0        # +1 la linea estaba a la derecha, -1 a la izquierda\n"
    "_frames_sin = 0        # cuantos frames seguidos sin verla\n"
)

INIT = '''
# ---- PARCHE PERDIDA (2026-08-28) -----------------------------------------
# 0 = apagado (comportamiento identico al de hoy)
# 1 = manda el angulo hacia el lado por el que se fue la linea
# 2 = ademas manda green_state = GS_LINEA_PERDIDA (ver el aviso del docstring)
PERDIDA       = int(os.environ.get("PERDIDA", "0"))
PERDIDA_ANG   = float(os.environ.get("PERDIDA_ANG", "75"))
PERDIDA_N     = int(os.environ.get("PERDIDA_N", "6"))
PERDIDA_MIN   = int(os.environ.get("PERDIDA_MIN", "5"))
PERDIDA_BORDE = int(os.environ.get("PERDIDA_BORDE", "4"))
_pd_hist = []          # signo del lado en los ultimos PERDIDA_N frames CON linea
_pd_sin = 0            # frames seguidos sin linea
# ---- fin PARCHE PERDIDA ---------------------------------------------------
'''

ANCLA_LOGICA = (
    "                    _r = None\n"
    "            # ==============================================\n"
)

LOGICA = '''
            # ---- PARCHE PERDIDA (2026-08-28) -------------------------
            # GAP vs CURVA por el borde del ROI, con zona de abstencion.
            # Ver el docstring de parche_perdida_camino.py.
            if PERDIDA:
                if black_mask.any():
                    _pd_sin = 0
                    _pd_lado = 0
                    _nn, _lb, _stt, _cc = cv2.connectedComponentsWithStats(black_mask, 8)
                    if _nn > 1:
                        _big = 1 + int(np.argmax(_stt[1:, 4]))
                        _g = (_lb == _big)
                        _iz = bool(_g[:, :PERDIDA_BORDE].any())
                        _de = bool(_g[:, -PERDIDA_BORDE:].any())
                        if _iz != _de:                 # un solo borde tocado
                            _pd_lado = -1 if _iz else 1
                    # si el planner opina, la direccion sale del TRAZO
                    if _r is not None and _r.get("ok"):
                        _pts = _r.get("puntos") or []
                        if len(_pts) >= 4:
                            _dx = _pts[-1][0] - _pts[0][0]
                            if abs(_dx) > 6:
                                _pd_lado = 1 if _dx > 0 else -1
                    _pd_hist.append(_pd_lado)
                    if len(_pd_hist) > PERDIDA_N:
                        del _pd_hist[0]
                else:
                    _pd_sin += 1
                    _iz = sum(1 for _s in _pd_hist if _s < 0)
                    _de = sum(1 for _s in _pd_hist if _s > 0)
                    if (len(_pd_hist) >= PERDIDA_N
                            and max(_iz, _de) >= PERDIDA_MIN
                            and min(_iz, _de) <= PERDIDA_N - PERDIDA_MIN):
                        _s = 1 if _de > _iz else -1    # +1 = se fue por la derecha
                        _k = min(1.0, 0.4 + 0.1 * _pd_sin)
                        angle = -_s * PERDIDA_ANG * _k
                        _quien = "perdida%+d" % _s
                        if PERDIDA == 2:
                            green_state = GS_LINEA_PERDIDA
                    # si no llega al umbral: ABSTENERSE. No se toca nada.
            # ---- fin PARCHE PERDIDA ----------------------------------
'''

# El lazo vive dentro de `def main():`, asi que `_pd_sin += 1` sin declararlo
# global explota con UnboundLocalError en el PRIMER frame sin linea.
ANCLA_GLOBAL = "    global estado, silver_line, _ult_lado, _frames_sin\n"
GLOBAL = "    global _pd_hist, _pd_sin                      # PARCHE PERDIDA\n"


def salir(msg, codigo=1):
    print(msg); sys.exit(codigo)


def main():
    args = [a for a in sys.argv[1:]]
    rev = "--revertir" in args
    args = [a for a in args if not a.startswith("--")]
    ruta = args[0] if args else DEFECTO
    if not os.path.isfile(ruta):
        salir("No encuentro %s\nPasa la ruta como argumento." % ruta)
    if rev:
        baks = sorted(glob.glob(ruta + ".bak-perdida-*"))
        if not baks:
            salir("No hay backup de este parche al lado de %s" % ruta)
        shutil.copyfile(baks[-1], ruta)
        print("Restaurado desde %s" % baks[-1]); sys.exit(0)

    src = io.open(ruta, encoding="utf-8").read()
    if MARCA in src:
        salir("Ya esta parcheado (%s). Nada que hacer." % ruta, 0)
    for nom, anc in (("init", ANCLA_INIT), ("logica", ANCLA_LOGICA),
                     ("global", ANCLA_GLOBAL)):
        n = src.count(anc)
        if n != 1:
            salir("El ancla '%s' aparece %d veces (esperaba 1). NO toco el archivo.\n"
                  "El main.py del robot no es el que espera este parche." % (nom, n))

    nuevo = src.replace(ANCLA_INIT, ANCLA_INIT + INIT, 1)
    nuevo = nuevo.replace(ANCLA_LOGICA, ANCLA_LOGICA + LOGICA, 1)
    # el lazo vive dentro de def main(): sin esto, _pd_sin += 1 explota
    # con UnboundLocalError en el primer frame sin linea.
    nuevo = nuevo.replace(ANCLA_GLOBAL, ANCLA_GLOBAL + GLOBAL, 1)

    try:
        compile(nuevo, ruta, "exec")
    except SyntaxError as e:
        salir("El resultado NO compila (%s, linea %s). No escribo nada." % (e.msg, e.lineno))

    i = 1
    while os.path.exists("%s.bak-perdida-%d" % (ruta, i)):
        i += 1
    bak = "%s.bak-perdida-%d" % (ruta, i)
    shutil.copyfile(ruta, bak)
    io.open(ruta, "w", encoding="utf-8").write(nuevo)
    try:
        compile(io.open(ruta, encoding="utf-8").read(), ruta, "exec")
    except SyntaxError as e:
        shutil.copyfile(bak, ruta)
        salir("El archivo escrito no compila. RESTAURADO desde %s" % bak)

    print("OK  %s parcheado" % ruta)
    print("    backup en %s" % bak)
    print()
    print("Control primero (tiene que andar EXACTAMENTE igual que hoy):")
    print("    PERDIDA=0 GRABAR=~/p0.avi python3 main.py")
    print()
    print("Y despues:")
    print("    PERDIDA=1 GRABAR=~/p1.avi python3 main.py")
    print("    PERDIDA=1 PLANNER=1 GRABAR=~/p1p.avi python3 main.py")
    print()
    print("En el overlay, cuando actua vas a ver  perdida+1  (se fue por la")
    print("derecha) o  perdida-1  (por la izquierda). Si no aparece nunca, el")
    print("discriminador nunca llego al umbral: subi PERDIDA_MIN o bajalo.")


if __name__ == "__main__":
    main()

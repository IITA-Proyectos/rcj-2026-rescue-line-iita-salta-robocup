# -*- coding: utf-8 -*-
"""
parche_planner.py - Enchufa el planner al Main.py que corre en la Raspberry,
                    y le agrega grabacion de video con lo que el robot ve.

POR QUE UN PARCHE Y NO UN Main.py NUEVO
---------------------------------------
El Main.py que corre en la Pi vive fuera de git y tiene cosas que el del repo no
tiene. Reescribirlo entero es la forma mas facil de perder algo sin darse cuenta.
Esto toca TRES lugares, hace backup antes, y se puede revertir con un comando.

USO
---
    python3 parche_planner.py            aplica el parche (deja main.py.bak)
    python3 parche_planner.py /ruta/main.py   si esta en otro lado
    python3 parche_planner.py --revertir  vuelve atras
    python3 parche_planner.py --ver       muestra que cambiaria, sin tocar nada

DESPUES, PARA CORRER
--------------------
    sudo systemctl stop iita-robot           el servicio tiene la camara tomada

    PLANNER=0 GRABAR=~/Desktop/a.avi python3 main.py    centroide, como estaba
    PLANNER=1 GRABAR=~/Desktop/b.avi python3 main.py    el planner maneja siempre
    PLANNER=2 GRABAR=~/Desktop/c.avi python3 main.py    HIBRIDO (el recomendado)

El hibrido usa el centroide siempre, y le pasa el volante al trazo SOLO cuando
el centroide se satura (|angulo| >= 70 por defecto, se cambia con SATURA_DESDE).

Las dos variables son independientes: se puede grabar sin planner y viceversa.
Sin GRABAR no graba nada y no cuesta nada. Sin PLANNER=1 usa el metodo de
siempre, asi que el parche aplicado NO cambia el comportamiento por si solo.

QUE GRABA
---------
El frame de 160x120 que el robot realmente proceso, escalado x2, con encima:
  - el angulo del metodo VIEJO (amarillo) y el del PLANNER (verde)
  - la ruta que armo el planner, punto por punto
  - la linea del recorte del ROI
  - un aviso cuando el planner esta extrapolando de memoria
O sea que en el video se ve lo que el robot vio Y lo que decidio, juntos.
"""
import io
import os
import re
import sys

def _buscar_main():
    """Encuentra el main del robot al lado de este script.

    En Linux las mayusculas importan: el archivo de la Raspberry se llama
    `main.py` y el del repo `Main.py`. Buscar un nombre fijo hacia fallar el
    parche por una letra. Se acepta tambien una ruta explicita como argumento.
    """
    for a in sys.argv[1:]:
        if not a.startswith("--"):
            return os.path.abspath(a)
    aca = os.path.dirname(os.path.abspath(__file__))
    for n in os.listdir(aca):
        if n.lower() == "main.py":
            return os.path.join(aca, n)
    return os.path.join(aca, "main.py")


RUTA = _buscar_main()

# ---------------------------------------------------------------- bloque 1 ---
# Va despues de los imports. Todo protegido: si el planner no esta, el robot
# sigue andando con el metodo de siempre y lo dice por consola. Un experimento
# no puede dejar al robot sin arrancar.
BLOQUE_IMPORT = '''
# ===================== PLANNER DE LINEA (parche IITA) =====================
# Se enciende con la variable de entorno PLANNER=1. Apagado, el robot se
# comporta EXACTAMENTE como antes: el parche no cambia nada por si solo.
# PLANNER=0  el metodo de siempre (centroide)
# PLANNER=1  el planner maneja siempre
# PLANNER=2  HIBRIDO: manda el centroide, y el planner entra SOLO donde el
#            centroide se satura. Ver el comentario de MODO_HIBRIDO abajo.
_MODO = os.environ.get("PLANNER", "0")
USAR_PLANNER = _MODO in ("1", "2")
MODO_HIBRIDO = _MODO == "2"
# Un seguidor de linea necesita DOS errores y el atan2 los mezcla en uno:
#   error LATERAL  (cuan corrido estoy)      -> lo mide bien el centroide, que
#       promedia toda la mascara: es estable y nunca se equivoca de rama.
#   error de RUMBO (para donde sigue la cinta) -> lo mide bien el trazo, que
#       camina la linea y conserva su orientacion.
# Cuando la cinta queda HORIZONTAL en el ROI -o sea, en la curva cerrada-
# y_resultant tiende a 0 y el centroide salta a +-90 sin gradacion: sabe que el
# robot esta mal parado pero no para donde ir. Medido en pista el 2026-08-22:
# eso pasa en el 9-11% de los frames, en episodios de hasta 325 ms.
# El hibrido deja el centroide manejando -que es lo que hoy funciona en recta y
# en curva suave- y le pasa el volante al trazo SOLO en esos frames.
SATURA_DESDE = float(os.environ.get("SATURA_DESDE", "70"))   # grados

# ROI ADAPTATIVO. main.py recorta con black_mask[:60, :] = 0, un numero fijo.
# Medido sobre el video del 2026-08-22: el horizonte real esta en la fila 52
# (mediana, p10 en 39), asi que el recorte fijo tira 8 filas de piso (mediana,
# 15 en el p75), y en el 73% de esos casos HAY CINTA ahi. Son las filas MAS
# LEJANAS, o sea justo donde vive la anticipacion que al robot le falta.
# Con la camara a altura fija -no se puede subir- esta es la unica forma de
# ganar vista hacia adelante, y es gratis.
#   ROI=60    (por defecto) el recorte de siempre, no cambia nada
#   ROI=auto  busca el horizonte en cada frame
ROI_MODO = os.environ.get("ROI", "60")

def _fila_horizonte(frame_bgr, minimo=30, maximo=60):
    """Primera fila desde arriba a partir de la cual empieza el piso.

    El salon entra por el borde superior y es oscuro y texturado; el piso es
    brillante y parejo. Se baja hasta encontrar una fila clara que SIGA clara
    hacia abajo -pedir solo "clara" se lo come un reflejo del salon-.
    Acotado entre `minimo` y `maximo` a proposito: si la deteccion falla, el
    peor caso es el recorte de siempre, nunca uno que meta el salon adentro.
    """
    try:
        g = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        brillo = g.mean(axis=1)
        for y in range(maximo):
            if brillo[y] > 150 and brillo[y:y + 15].min() > 130:
                return max(minimo, y + 2)      # +2 de margen sobre el borde
    except Exception:
        pass
    return maximo
RUTA_VIDEO   = os.environ.get("GRABAR", "")

_seguidor = None
if USAR_PLANNER:
    try:
        from seguidor_linea import Seguidor
        _seguidor = Seguidor()
        print("[PLANNER] encendido")
    except Exception as _e:
        # Que falte el archivo no puede impedir que el robot arranque.
        print("[PLANNER] no se pudo cargar (%s): sigo con el metodo de siempre" % _e)
        USAR_PLANNER = False

_video = None
_video_n = 0

def _cerrar_video():
    """Cerrar el archivo al salir. SIN ESTO el .avi queda sin indice y puede no
    abrir: cv2.VideoWriter escribe la cabecera recien en release(). Con Ctrl-C
    -que es como se corta siempre- el proceso muere y el video se pierde.
    atexit corre igual con KeyboardInterrupt, que es el caso real."""
    global _video
    if _video is not None:
        try:
            _video.release()
            print("[GRABAR] cerrado: %d frames en %s" % (_video_n, RUTA_VIDEO))
        except Exception:
            pass
        _video = None

import atexit
atexit.register(_cerrar_video)
def _grabar(frame_bgr, ang_viejo, ang_planner, r, quien="centroide"):
    """Una imagen por frame con lo que el robot vio y lo que decidio.

    Nunca levanta una excepcion hacia el lazo de vision: si la grabacion falla,
    se apaga sola y el robot sigue. Un registro no puede voltear una corrida.
    """
    global _video, _video_n
    if not RUTA_VIDEO:
        return
    try:
        vis = cv2.resize(frame_bgr, (320, 240), interpolation=cv2.INTER_NEAREST)
        cv2.line(vis, (0, 120), (319, 120), (0, 255, 255), 1)      # el recorte del ROI
        # PANEL DERECHO: la mascara que el planner uso DE VERDAD. Sin esto, cuando
        # el robot se sale no hay forma de distinguir "el trazo se fue por donde no
        # habia cinta" de "la mascara no vio la cinta". Son dos arreglos distintos.
        if r is not None and r.get("mascara") is not None:
            mk = cv2.cvtColor(cv2.resize(r["mascara"], (320, 240),
                              interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
        else:
            mk = np.zeros((240, 320, 3), np.uint8)
        if r is not None and r.get("puntos"):
            p = [(int(x * 2), int(y * 2)) for x, y in r["puntos"]]
            for u, v in zip(p, p[1:]):
                cv2.line(vis, u, v, (0, 255, 0), 2)
            if r.get("mira"):
                mx, my = r["mira"]
                cv2.circle(vis, (int(mx * 2), int(my * 2)), 5, (0, 128, 255), 2)
        cv2.putText(vis, "viejo %+.0f" % ang_viejo, (4, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        if ang_planner is not None:
            cv2.putText(vis, "planner %+.0f" % ang_planner, (4, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        # QUIEN MANDO en este frame. Sin esto, en el hibrido no hay forma de saber
        # si una reaccion la decidio el centroide o el trazo.
        cv2.putText(vis, "manda: " + quien, (4, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 255, 0) if "planner" in quien else (0, 255, 255), 1)
        if r is not None and not r.get("ok"):
            cv2.putText(vis, "MEMORIA: " + str(r.get("motivo", ""))[:14], (4, 232),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)
        if r is not None and r.get("puntos"):
            for x, y in r["puntos"]:
                cv2.circle(mk, (int(x * 2), int(y * 2)), 2, (0, 0, 255), -1)
        cv2.putText(mk, "mascara del planner", (4, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 128, 0), 1)
        vis = np.hstack([vis, mk])
        if _video is None:
            _video = cv2.VideoWriter(os.path.expanduser(RUTA_VIDEO),
                                     cv2.VideoWriter_fourcc(*"MJPG"), 20.0, (640, 240))
            print("[GRABAR] escribiendo en %s" % RUTA_VIDEO)
        _video.write(vis)
        _video_n += 1
    except Exception as _e:
        print("[GRABAR] se apaga por error: %s" % _e)
        globals()["RUTA_VIDEO"] = ""
# =========================================================================
'''

ANCLA_IMPORT = "import threading\nimport queue"

# ---------------------------------------------------------------- bloque 2 ---
# El calculo del angulo. Se deja el viejo SIEMPRE, para poder compararlos en el
# mismo frame y en el mismo video: sin eso no hay forma de saber si el planner
# mejoro o si cambio la pista.
VIEJO_ANGULO = (
    "            green_state = 0\n"
    "            x_resultant = np.mean(x_black)\n"
    "            y_resultant = np.mean(y_black)\n"
    "            angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90\n"
    "            speed = 40\n"
)
NUEVO_ANGULO = (
    '            green_state = 0\n'

    '            x_resultant = np.mean(x_black)\n'

    '            y_resultant = np.mean(y_black)\n'

    '            angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90\n'

    '            speed = 40\n'

    '\n'

    '            # ---- ROI ADAPTATIVO (parche IITA) ----\n'

    '            # El recorte fijo de la fila 60 tira piso util. Medido sobre el\n'

    '            # video del 2026-08-22: el horizonte real esta en la fila 52, se\n'

    '            # descartan 8 filas (mediana, 15 en el p75) y en el 73% de esos\n'

    '            # casos HAY CINTA ahi. Son las filas mas lejanas, o sea justo la\n'

    '            # anticipacion que le falta al robot. Con la camara a altura fija\n'

    '            # esta es la unica vista hacia adelante que se puede ganar.\n'

    '            if ROI_MODO == "auto":\n'

    '                _corte = _fila_horizonte(frame_resized)\n'

    '                if _corte < 60:\n'

    '                    black_mask = cv2.inRange(frame_resized, lower_black, upper_black)\n'

    '                    black_mask[:_corte, :] = 0\n'

    '                    x_black = cv2.bitwise_and(x_com, x_com, mask=black_mask)\n'

    '                    x_black *= (1 - y_com)\n'

    '                    y_black = cv2.bitwise_and(y_com, y_com, mask=black_mask)\n'

    '                    x_resultant = np.mean(x_black)\n'

    '                    y_resultant = np.mean(y_black)\n'

    '                    angle = (math.atan2(y_resultant, x_resultant) / math.pi * 180) - 90\n'

    '\n'

    '            # ---- PLANNER (parche IITA) ----\n'

    '            # El angulo del centroide ya se calculo arriba y queda guardado: es\n'

    '            # la referencia del video y, en modo hibrido, tambien el que manda.\n'

    '            _ang_viejo = angle\n'

    '            _r = None\n'

    '            _quien = "centroide"\n'

    '            if USAR_PLANNER:\n'

    '                try:\n'

    '                    _r = _seguidor.paso(frame_resized, ya_procesado=True)\n'

    '                    if not MODO_HIBRIDO:\n'

    '                        angle = _r["angle_filtrado"]\n'

    '                        _quien = "planner"\n'

    '                    elif _r.get("ok") and abs(_ang_viejo) >= SATURA_DESDE:\n'

    '                        # El centroide se saturo: perdio gradacion y ya no sabe\n'

    '                        # PARA DONDE sigue la cinta, solo que esta mal parado.\n'

    '                        angle = _r["angle_filtrado"]\n'

    '                        _quien = "planner*"\n'

    '                except Exception as _e:\n'

    '                    print("[PLANNER] error, sigo con el centroide: %s" % _e)\n'

    '                    _r = None\n'

    '            # -------------------------------\n'

    '\n'
)

# ---------------------------------------------------------------- bloque 3 ---
# La guarda vieja. Usa black_mask, que es la mascara del metodo VIEJO (inRange
# fijo + recorte en 60). El planner usa su propia mascara adaptativa, asi que
# dejar la guarda activa significaria pisar con 0 un angulo que el planner
# calculo bien. Solo debe aplicarse cuando el planner NO esta manejando.
VIEJA_GUARDA = (
    "            if np.sum(black_mask) < min_line_size:\n"
    "                angle = 0\n"
)
NUEVA_GUARDA = (
    "            if (not USAR_PLANNER) and np.sum(black_mask) < min_line_size:\n"
    "                angle = 0\n"
)

# ---------------------------------------------------------------- bloque 4 ---
ANCLA_ENVIO = (
    "            output = send_frame(speed, round(angle), green_state, silver_line)\n"
)
NUEVO_ENVIO = (
    "            output = send_frame(speed, round(angle), green_state, silver_line)\n"
    "            _grabar(frame_resized, _ang_viejo, angle if USAR_PLANNER else None, _r, _quien)\n"
)

CAMBIOS = [
    ("los imports y el arranque del planner", ANCLA_IMPORT, ANCLA_IMPORT + "\n" + BLOQUE_IMPORT),
    ("el calculo del angulo", VIEJO_ANGULO, NUEVO_ANGULO),
    ("la guarda de min_line_size", VIEJA_GUARDA, NUEVA_GUARDA),
    ("la grabacion, despues del envio", ANCLA_ENVIO, NUEVO_ENVIO),
]


def leer(ruta):
    with io.open(ruta, encoding="utf-8", newline="") as fh:
        return fh.read()


def escribir(ruta, txt):
    with io.open(ruta, "w", encoding="utf-8", newline="") as fh:
        fh.write(txt)


def normalizar(txt):
    """Los saltos de linea no pueden decidir si el parche entra o no."""
    return txt.replace("\r\n", "\n")


def main():
    if not os.path.exists(RUTA):
        print("*** No encuentro el main del robot (busque: %s)" % RUTA)
        print("    Copia parche_planner.py a la MISMA carpeta que main.py,")
        print("    o pasale la ruta:  python3 parche_planner.py /ruta/al/main.py")
        return 2

    bak = RUTA + ".bak"

    if "--revertir" in sys.argv:
        if not os.path.exists(bak):
            print("*** No hay Main.py.bak: no puedo revertir.")
            return 2
        escribir(RUTA, leer(bak))
        print("Revertido: Main.py volvio a como estaba (desde Main.py.bak).")
        return 0

    s = normalizar(leer(RUTA))

    if "PLANNER DE LINEA (parche IITA)" in s:
        print("El parche YA ESTA aplicado. Nada que hacer.")
        print("Para volver atras: python3 parche_planner.py --revertir")
        return 0

    faltan = [nom for nom, viejo, _ in CAMBIOS if viejo not in s]
    if faltan:
        print("*** No encontre estos lugares en Main.py, NO toco nada:")
        for f in faltan:
            print("      - " + f)
        print("    El Main.py de la Pi cambio respecto del que revisamos.")
        return 1

    if "--ver" in sys.argv:
        print("Los 4 lugares estan. El parche entraria limpio.")
        print("Correlo sin --ver para aplicarlo.")
        return 0

    if not os.path.exists(bak):
        escribir(bak, leer(RUTA))
        print("backup: %s" % bak)

    for nom, viejo, nuevo in CAMBIOS:
        s = s.replace(viejo, nuevo, 1)
        print("  parchado: %s" % nom)

    escribir(RUTA, s)

    # Que compile NO prueba que funcione, pero que no compile si prueba que rompe.
    import py_compile
    try:
        py_compile.compile(RUTA, doraise=True)
        print("\nMain.py compila.")
    except Exception as e:
        print("\n*** Main.py NO compila: %s" % e)
        print("    Revirtiendo automaticamente para no dejarte el robot roto.")
        escribir(RUTA, leer(bak))
        return 1

    print("""
LISTO. El parche NO cambia el comportamiento por si solo: sin PLANNER=1 el robot
anda exactamente como antes.

    sudo systemctl stop iita-robot

    PLANNER=1 GRABAR=~/Desktop/con_planner.avi python3 Main.py
    PLANNER=0 GRABAR=~/Desktop/sin_planner.avi python3 Main.py

Para volver atras del todo:  python3 parche_planner.py --revertir
Y al terminar:               sudo systemctl start iita-robot
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())

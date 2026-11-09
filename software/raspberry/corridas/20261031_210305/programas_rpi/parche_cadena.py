# -*- coding: utf-8 -*-
"""Genera main_cadena.py = el main.py DEL ROBOT + la vision de la CADENA.

POR QUE UN ARCHIVO NUEVO Y NO UN PARCHE EN main.py
--------------------------------------------------
El main.py de la Raspberry es el programa que corre en competencia. Si se rompe,
se pierde la sesion. Este script NO LO TOCA: lee main.py, le inserta dos bloques
y escribe main_cadena.py al lado. Para volver atras se borra el archivo nuevo.

    python3 parche_cadena.py                 # genera main_cadena.py
    VISION_LINEA=camino python3 main_cadena.py

QUE INSERTA, y es todo
----------------------
1. El import protegido de vision_linea (el mismo contrato que telemetria_vision:
   si falla, se apaga solo y sigue la vision vieja).
2. Un bloque 5 despues del PLANNER: si la cadena opina, su angulo reemplaza al
   del centroide. Si devuelve None -no opina- no se toca nada.

vision_linea ya se auto-apaga sin la variable VISION_LINEA, asi que
main_cadena.py SIN esa variable se comporta igual que main.py.

EL ANCLA es literal. Si main.py cambia y el ancla no aparece, este script FALLA
RUIDOSAMENTE en vez de escribir un archivo a medias.
"""
import os
import sys
import py_compile

AQUI = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(AQUI, "main.py")
NUEVO = os.path.join(AQUI, "main_cadena.py")

ANCLA_IMPORT = "import queue\n"

IMPORT_NUEVO = '''import queue
# ---- VISION DE LA CADENA (insertado por parche_cadena.py) -------------------
# Mismo contrato que el resto de los parches: apagada salvo que exista la
# variable VISION_LINEA, import protegido, y si algo falla se apaga sola y
# se sigue con la vision de siempre. Un modulo de vision no puede voltear
# una corrida.
try:
    import vision_linea as _VL
    USAR_CADENA = _VL.ACTIVA
except Exception as _e_vl:
    print("[CADENA] no se pudo importar (%s): sigo con la vision vieja" % _e_vl)
    _VL = None
    USAR_CADENA = False
print("[CADENA] %s" % ("ENCENDIDA" if USAR_CADENA else "apagada"))
# ----------------------------------------------------------------------------
'''

ANCLA_BLOQUE = """                except Exception as _e2:
                    print("[PLANNER] error, sigo con el centroide: %s" % _e2)
                    _r = None
"""

BLOQUE_NUEVO = ANCLA_BLOQUE + """
            # 5. CADENA (vision nueva), si se pidio. Va DESPUES del planner a
            #    proposito: si las dos estan encendidas, gana la cadena. None
            #    significa "no opino": se deja el angulo que ya venia.
            if USAR_CADENA:
                _ac = _VL.angulo(frame_resized)
                if _ac is not None:
                    angle = _ac
                    _quien = "cadena"
"""


def main():
    if not os.path.exists(ORIG):
        sys.exit("ERROR: no encuentro %s. Corre esto AL LADO del main.py de la Pi." % ORIG)

    src = open(ORIG, encoding="utf-8", errors="replace").read()

    for nombre, ancla in (("el import", ANCLA_IMPORT), ("el bloque del planner", ANCLA_BLOQUE)):
        n = src.count(ancla)
        if n != 1:
            sys.exit("ERROR: el ancla de %s aparece %d veces (esperaba 1).\n"
                     "main.py cambio. NO escribo nada: revisalo a mano." % (nombre, n))

    if "USAR_CADENA" in src:
        sys.exit("ERROR: main.py ya menciona USAR_CADENA. Ya esta parchado?")

    out = src.replace(ANCLA_IMPORT, IMPORT_NUEVO, 1).replace(ANCLA_BLOQUE, BLOQUE_NUEVO, 1)

    open(NUEVO, "w", encoding="utf-8", newline="\n").write(out)

    try:
        py_compile.compile(NUEVO, doraise=True)
    except py_compile.PyCompileError as e:
        os.remove(NUEVO)
        sys.exit("ERROR: el archivo generado NO COMPILA, lo borre.\n%s" % e)

    print("OK  %s  (%d -> %d bytes, +%d)"
          % (NUEVO, len(src), len(out), len(out) - len(src)))
    print()
    print("main.py NO se toco. Para probar:")
    print("    VISION_LINEA=camino python3 main_cadena.py")
    print("Para volver a lo de siempre:")
    print("    python3 main.py")


if __name__ == "__main__":
    main()

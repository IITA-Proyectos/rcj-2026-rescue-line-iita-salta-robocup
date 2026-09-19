# -*- coding: utf-8 -*-
"""Aplica el retardo de envio a main.py. Reversible, con backup y verificacion.

Por que un parcheador y no un main.py reescrito
-----------------------------------------------
El main.py de la Pi tiene ~1000 lineas y se toca seguido. Reescribirlo entero
para agregar dos lineas arriesga pisar cambios y meter erratas de transcripcion.
Este script hace SOLO los dos cambios, guarda un backup con fecha y verifica que
el archivo siga compilando. Si algo no cierra, no escribe nada.

Que cambia, exactamente dos cosas
---------------------------------
  1. agrega, despues de los imports:
         from retardo import Retardo
         _retardo = Retardo()
  2. reemplaza en el lazo de linea:
         output = send_frame(speed, round(angle), green_state, silver_line)
     por:
         output = _retardo.enviar(send_frame, speed, round(angle),
                                  green_state, silver_line)

NO toca el `send_frame` del modo rescate: ahi el retardo no tiene sentido y
meterlo mezclaria dos experimentos.

Sin la variable de entorno RETARDO_MS, el comportamiento queda IDENTICO byte por
byte al de hoy.

Uso
---
    python3 aplicar_retardo.py main.py            # aplica
    python3 aplicar_retardo.py main.py --ver      # solo muestra que haria
    python3 aplicar_retardo.py main.py --revertir # vuelve al ultimo backup
"""

import argparse
import ast
import datetime
import io
import os
import re
import shutil
import sys

IMPORT = "from retardo import Retardo"
INSTANCIA = "_retardo = Retardo()          # RETARDO_MS del entorno; sin ella, no hace nada"

VIEJO = "output = send_frame(speed, round(angle), green_state, silver_line)"
NUEVO = ("output = _retardo.enviar(send_frame, speed, round(angle),\n"
         "                                     green_state, silver_line)")


def backups(ruta):
    d = os.path.dirname(os.path.abspath(ruta)) or "."
    b = os.path.basename(ruta)
    return sorted(f for f in os.listdir(d)
                  if f.startswith(b + ".backup_"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("main", nargs="?", default="main.py")
    ap.add_argument("--ver", action="store_true", help="no escribe, solo muestra")
    ap.add_argument("--revertir", action="store_true")
    a = ap.parse_args(argv)

    ruta = a.main
    if not os.path.exists(ruta):
        print("no existe %s" % ruta)
        return 1

    if a.revertir:
        bs = backups(ruta)
        if not bs:
            print("no hay backups de %s" % ruta)
            return 1
        d = os.path.dirname(os.path.abspath(ruta)) or "."
        ult = os.path.join(d, bs[-1])
        shutil.copy2(ult, ruta)
        print("revertido desde %s" % bs[-1])
        return 0

    src = io.open(ruta, encoding="utf-8", errors="replace").read()

    # --- ya esta aplicado? -------------------------------------------------
    if "_retardo.enviar(" in src:
        print("  %s YA tiene el retardo aplicado. No se toca." % ruta)
        return 0

    # --- 1. el import, despues del ultimo import de arriba -----------------
    lineas = src.split("\n")
    ult_import = 0
    for k, l in enumerate(lineas[:80]):
        if re.match(r"^\s*(import|from)\s+\w", l):
            ult_import = k
    nuevas = lineas[:ult_import + 1] + [
        "",
        "# --- retardo de envio (experimento). Sin RETARDO_MS es transparente. ---",
        IMPORT,
        INSTANCIA,
    ] + lineas[ult_import + 1:]
    src2 = "\n".join(nuevas)

    # --- 2. el envio del lazo de LINEA -------------------------------------
    n = src2.count(VIEJO)
    if n == 0:
        print("  *** No encontre la linea de envio del lazo de linea:")
        print("      %s" % VIEJO)
        print("  *** Puede que tu main.py la tenga escrita distinto. Revisala a")
        print("      mano y avisá; NO escribo nada.")
        return 1
    if n > 1:
        print("  *** La linea de envio aparece %d veces. No se cual es la del" % n)
        print("      lazo de linea, asi que NO escribo nada.")
        return 1

    # respetar la indentacion original
    m = re.search(r"^([ \t]*)" + re.escape(VIEJO), src2, re.M)
    sangria = m.group(1)
    reemplazo = (sangria + "output = _retardo.enviar(send_frame, speed, round(angle),\n"
                 + sangria + "                         green_state, silver_line)")
    src2 = re.sub(r"^[ \t]*" + re.escape(VIEJO), reemplazo, src2, count=1, flags=re.M)

    # --- 3. verificar que compila ------------------------------------------
    try:
        ast.parse(src2)
    except SyntaxError as e:
        print("  *** El resultado NO compila (%s). No escribo nada." % e)
        return 1

    if a.ver:
        print("  Cambios que se aplicarian a %s:" % ruta)
        print("")
        print("  1. despues de la linea %d:" % (ult_import + 1))
        print("       %s" % IMPORT)
        print("       %s" % INSTANCIA)
        print("")
        print("  2. en el lazo de linea:")
        print("       -  %s" % VIEJO)
        print("       +  output = _retardo.enviar(send_frame, speed, round(angle),")
        print("       +                           green_state, silver_line)")
        print("")
        print("  (--ver: no se escribio nada)")
        return 0

    sello = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = "%s.backup_%s" % (ruta, sello)
    shutil.copy2(ruta, bak)
    io.open(ruta, "w", encoding="utf-8").write(src2)
    print("  backup : %s" % os.path.basename(bak))
    print("  aplicado a %s" % ruta)
    print("")
    print("  Comprobar que quedo transparente:")
    print("      python3 main.py            # sin RETARDO_MS, igual que antes")
    print("  Y para el barrido:")
    print("      RETARDO_MS=60 python3 main.py")
    print("")
    print("  Para volver atras:")
    print("      python3 aplicar_retardo.py main.py --revertir")
    return 0


if __name__ == "__main__":
    sys.exit(main())

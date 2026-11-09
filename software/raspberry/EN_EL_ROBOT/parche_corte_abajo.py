#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PARCHE: recorte de las filas de ABAJO del ROI.  2026-08-28

QUE HACE
  Agrega la variable de entorno CORTE_ABAJO al main.py que corre en la Pi.
  Con CORTE_ABAJO=120 (el defecto) NO CAMBIA NADA: el robot se comporta
  exactamente igual que hoy.  Con CORTE_ABAJO=105 el angulo se calcula sin
  las filas 105-119.

POR QUE
  Las filas de abajo del ROI son la linea que el robot YA PISO.  En la ley
  `angle = atan2(sum(y_com), sum(x_com*(1-y_com)))` la fila 119 pesa 1,00 en
  el termino lateral y la fila 60 pesa 0,51.  Medido sobre 12.297 frames de
  8 corridas del 22-ago: esas 15 filas son el 33% de los pixeles negros pero
  se llevan el 45% del voto lateral, y en el 99% de los frames de codo votan
  con el signo CONTRARIO al de la linea de adelante.

RESPALDO
  Si el recorte deja la mascara vacia se usa la mascara entera.  Por eso los
  frames ciegos quedan IDENTICOS a los de la base -no se pierde ni uno-.

QUE NO HACE
  No toca el atan2, no toca el recorte de arriba, no toca black_mask (asi
  CTRL=lineal y RECUP siguen viendo exactamente lo que veian).  Solo cambia
  que pixeles entran al calculo del angulo.

COMO SE USA
  python3 parche_corte_abajo.py                 # parchea /home/iita/Desktop/main.py
  python3 parche_corte_abajo.py --revertir      # vuelve al backup
  python3 parche_corte_abajo.py ruta/al/main.py

  y despues, en el robot:
      CORTE_ABAJO=120 GRABAR=~/base.avi    python3 main.py   # control
      CORTE_ABAJO=105 GRABAR=~/corte.avi   python3 main.py   # tratamiento

  El overlay del video graba las DOS leyes en el mismo frame:
      "viejo N"  = lo que manda hoy
      "manda N"  = lo que manda con el recorte
      "corte105" = etiqueta de que el recorte actuo en ese frame
"""
import io, os, sys, glob, shutil

DEFECTO = "/home/iita/Desktop/main.py"

ANCLA = (
    "            _ang_viejo = angle\n"
    "            _quien = \"centroide\"\n"
    "            _r = None\n"
)

MARCA = "PARCHE CORTE_ABAJO"

PARCHE = '''
            # ---- PARCHE CORTE_ABAJO (2026-08-28) -------------------------
            # Las filas de abajo del ROI son la linea que el robot YA PISO.
            # Pesan 1,00 en el termino lateral contra 0,51 de la fila 60, y
            # en el 99% de los frames de codo votan con el signo CONTRARIO
            # al de la linea de adelante (12.297 frames, 8 corridas).
            # CORTE_ABAJO=120 = apagado, comportamiento identico al de hoy.
            _CA = int(os.environ.get("CORTE_ABAJO", "120"))
            if _CA < 120:
                _bm = black_mask.copy()
                _bm[_CA:, :] = 0
                if _bm.any():                      # RESPALDO: si queda vacia,
                    _xb = cv2.bitwise_and(x_com, x_com, mask=_bm)
                    _xb *= (1 - y_com)             # se usa la mascara entera
                    _yb = cv2.bitwise_and(y_com, y_com, mask=_bm)
                    angle = (math.atan2(np.mean(_yb), np.mean(_xb))
                             / math.pi * 180) - 90
                    _quien = "corte%d" % _CA
            # ---- fin PARCHE CORTE_ABAJO ----------------------------------
'''


def salir(msg, codigo=1):
    print(msg)
    sys.exit(codigo)


def revertir(ruta):
    baks = sorted(glob.glob(ruta + ".bak-corte_abajo-*"))
    if not baks:
        salir("No hay backup de este parche al lado de %s" % ruta)
    shutil.copyfile(baks[-1], ruta)
    print("Restaurado desde %s" % baks[-1])
    sys.exit(0)


def main():
    args = [a for a in sys.argv[1:]]
    rev = "--revertir" in args
    args = [a for a in args if not a.startswith("--")]
    ruta = args[0] if args else DEFECTO

    if not os.path.isfile(ruta):
        salir("No encuentro %s\nPasa la ruta como argumento." % ruta)
    if rev:
        revertir(ruta)

    src = io.open(ruta, encoding="utf-8").read()

    if MARCA in src:
        salir("Ya esta parcheado (%s). Nada que hacer." % ruta, 0)

    n = src.count(ANCLA)
    if n != 1:
        salir("El ancla aparece %d veces (esperaba 1). NO toco el archivo.\n"
              "El main.py del robot no es el que espera este parche." % n)

    nuevo = src.replace(ANCLA, ANCLA + PARCHE, 1)

    # control de sintaxis ANTES de escribir
    try:
        compile(nuevo, ruta, "exec")
    except SyntaxError as e:
        salir("El resultado NO compila (%s, linea %s). No escribo nada." % (e.msg, e.lineno))

    i = 1
    while os.path.exists("%s.bak-corte_abajo-%d" % (ruta, i)):
        i += 1
    bak = "%s.bak-corte_abajo-%d" % (ruta, i)
    shutil.copyfile(ruta, bak)
    io.open(ruta, "w", encoding="utf-8").write(nuevo)

    # control de sintaxis del archivo YA escrito
    try:
        compile(io.open(ruta, encoding="utf-8").read(), ruta, "exec")
    except SyntaxError as e:
        shutil.copyfile(bak, ruta)
        salir("El archivo escrito no compila. RESTAURADO desde %s" % bak)

    print("OK  %s parcheado" % ruta)
    print("    backup en %s" % bak)
    print("    lineas agregadas: %d" % (nuevo.count("\n") - src.count("\n")))
    print()
    print("Probalo asi, alternando:")
    print("    CORTE_ABAJO=120 GRABAR=~/base_1.avi  python3 main.py")
    print("    CORTE_ABAJO=105 GRABAR=~/corte_1.avi python3 main.py")
    print()
    print("Con CORTE_ABAJO=120 tiene que comportarse EXACTAMENTE igual que antes.")
    print("Si no, algo del parche esta mal: revertí con --revertir y avisá.")


if __name__ == "__main__":
    main()

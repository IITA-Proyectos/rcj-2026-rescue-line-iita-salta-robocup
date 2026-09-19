# -*- coding: utf-8 -*-
"""RECORTE DEL ROI. Cambia que franja de la imagen decide el angulo. Reversible.

QUE SE MIDIO ANTES DE ESCRIBIR ESTO
-----------------------------------
La idea era recortar ABAJO: sacar las filas pegadas al robot -que pesan el doble
que las lejanas, peso = (i+1)/120- para que el angulo lo decida la banda que ve
el codo. Se midio sobre `video_4.avi`, el unico video CRUDO que hay (640x480,
591 frames validos; f524-574 excluidos por MANUAL_LIFT), reproduciendo el
pipeline exacto de main.py. En los 349 frames donde hoy el firmware pivotea:

    ROI_ABAJO=95    ->  |ang| BAJA 13,1 gr   (baja en 336 de 349 frames)
    ROI_ABAJO=100   ->  |ang| BAJA 10,9 gr   (baja en 334 de 349)
    ROI_ARRIBA=70   ->  |ang| SUBE  4,0 gr
    ROI_ARRIBA=80   ->  |ang| SUBE  7,9 gr
    ROI_ARRIBA=90   ->  |ang| SUBE 12,4 gr
    ROI_ARRIBA=40   ->  |ang| BAJA  9,3 gr   <- esto es lo que hace ROI=auto

O sea que EL RECORTE DE ABAJO VA PARA EL LADO CONTRARIO. Vale la pena entender
por que, porque explica varias cosas de una vez:

    angle = atan2( mean(y_com*mask), mean(x_com*(1-y_com)*mask) ) - 90

`y_com` vale 0 en la fila de abajo y 0,49 en la fila 60. Las filas LEJANAS
tienen y_com ALTO. Sumar vision lejana sube `mean(y_com)`, empuja el atan2 hacia
90 grados y el angulo hacia 0. En esta formula, MAS VISTA ADELANTE = MENOS GIRO
PEDIDO. Es la misma inversion que ya estaba anotada en `_angulo_lineal`: "su
ganancia esta INVERTIDA".

Corolario incomodo: `ROI=auto`, que sube el ROI al horizonte real para
"anticipar mejor", BAJA el angulo pedido 9,3 grados en las curvas.

Advertencia de alcance: esto es UN video y es LAZO ABIERTO. Dice que el numero
que sale de la camara cambia, no que el robot complete la curva. Y un angulo mas
grande no equivale a tomar el codo: segun el handoff la Pi ya manda 32-38 grados
en el codo, asi que el problema puede estar despues del byte.

QUE HACE ESTE PARCHE
--------------------
Deja los dos cortes disponibles, apagados por defecto:

    ROI_ARRIBA=60  ROI_ABAJO=120     como hoy, no cambia un byte
    ROI_ARRIBA=80                    mas giro en curva
    ROI_ABAJO=95                     menos giro (por si se quiere lo contrario)

Tres cosas que hace a proposito
-------------------------------
1. NO toca `black_mask`. Recorta una COPIA que se usa solo para el angulo. El
   verde usa `black_mask[60:90]` y `black_mask[90:, :]` para calcular
   `cx_black`, y sacarle filas cambiaria la decision izquierda/derecha de las
   marcas verdes sin que nadie lo pida. Eso seria una segunda variable.

2. GUARDA CONTRA EL -90. Si en la banda recortada no queda ni un pixel negro,
   `mean` da 0 en los dos ejes, `atan2(0, 0)` da 0 y el angulo sale -90:
   volantazo a fondo salido de la nada. Hoy eso no pasa porque
   `np.sum(black_mask) < min_line_size` lo ataja, pero con el recorte la banda
   puede quedar vacia MIENTRAS abajo sigue habiendo cinta, y ese guard no se
   activa. Sin esta proteccion el robot pega el volantazo justo cuando la cinta
   se va del campo lejano, que es el momento del codo. Si la banda queda vacia
   se deja el angulo de siempre y el overlay dice "sin_banda".

3. `ROI_ARRIBA` PISA a `ROI=auto`. Son dos experimentos sobre la misma perilla:
   no correrlos juntos.

Uso
---
    python3 aplicar_recorte.py main.py --ver       # muestra que haria
    python3 aplicar_recorte.py main.py             # aplica
    python3 aplicar_recorte.py main.py --revertir  # vuelve al ultimo backup

    ROI_ARRIBA=60 python3 main.py                  # control, identico a hoy
    GRABAR=~/a80.avi ROI_ARRIBA=80 python3 main.py

Se puede aplicar junto con aplicar_retardo.py -tocan lineas distintas- pero NO
correr los dos experimentos a la vez: una variable por corrida.

Que mirar
---------
Grabá con GRABAR=. El overlay muestra `viejo` (el angulo sin recortar) y `manda`
(el que sale). El umbral que importa: con LINE_STEER_GAIN=1.35 y
LINE_PIVOTE_ENTRA=0.60 el firmware pivotea recien con |angle| >= 40 grados. Un
angulo que sube de 18 a 25 no cambia nada del comportamiento.
"""

import argparse
import ast
import datetime
import io
import os
import shutil
import sys

NL = chr(10)

DECL = (
    'ROI_ABAJO    = int(os.environ.get("ROI_ABAJO", "120"))   # 120 = sin recorte abajo'
    + NL +
    'ROI_ARRIBA   = int(os.environ.get("ROI_ARRIBA", "60"))    # 60 = como hoy'
)

ANCLA_DECL = ('AREA_MIN_LINEA = float(os.environ.get("AREA_MIN", "200"))'
              '   # px; ver _solo_mi_linea')

ANCLA_BLOQUE = ('            _ang_viejo = angle' + NL +
                '            _quien = "centroide"' + NL +
                '            _r = None' + NL)

BLOQUE = '''            _ang_viejo = angle
            _quien = "centroide"
            _r = None

            # 1.b RECORTE DEL ROI. Medido sobre video_4.avi -591 frames
            #     validos, f524-574 fuera por MANUAL_LIFT-, en los 349 frames
            #     donde hoy el firmware pivotea:
            #
            #         ROI_ABAJO=95   ->  |ang| BAJA 13,1 gr  (336 de 349)
            #         ROI_ARRIBA=80  ->  |ang| SUBE  7,9 gr
            #         ROI_ARRIBA=90  ->  |ang| SUBE 12,4 gr
            #         ROI_ARRIBA=40  ->  |ang| BAJA  9,3 gr   <- esto hace ROI=auto
            #
            #     angle = atan2(mean(y_com), mean(x_com*(1-y_com))) - 90, y las
            #     filas lejanas tienen y_com ALTO. Sumar vision lejana empuja el
            #     atan2 hacia 90 y el angulo hacia 0: MAS VISTA ADELANTE = MENOS
            #     GIRO PEDIDO. Por eso recortar abajo -que era la idea- va para
            #     el lado contrario, y la palanca que sube el giro es bajar el
            #     corte de arriba.
            #
            #     Sobre una COPIA: black_mask lo usa el verde para cx_black.
            if ROI_ARRIBA != 60 or ROI_ABAJO < 120:
                _m_ang = cv2.inRange(frame_resized, lower_black, upper_black)
                _m_ang[:ROI_ARRIBA, :] = 0
                if ROI_ABAJO < 120:
                    _m_ang[ROI_ABAJO:, :] = 0
                if np.count_nonzero(_m_ang):
                    _xb = cv2.bitwise_and(x_com, x_com, mask=_m_ang)
                    _xb = _xb * (1 - y_com)
                    _yb = cv2.bitwise_and(y_com, y_com, mask=_m_ang)
                    angle = (math.atan2(float(np.mean(_yb)),
                                        float(np.mean(_xb))) / math.pi * 180) - 90
                    _quien = "recorte"
                else:
                    # banda vacia: atan2(0,0) daria -90, un volantazo salido de
                    # la nada. Se deja el angulo de siempre.
                    _quien = "sin_banda"
'''


def backups(ruta):
    d = os.path.dirname(os.path.abspath(ruta)) or "."
    b = os.path.basename(ruta)
    return sorted(f for f in os.listdir(d) if f.startswith(b + ".recorte_"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split(NL)[0])
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
            print("no hay backups de recorte para %s" % ruta)
            return 1
        d = os.path.dirname(os.path.abspath(ruta)) or "."
        shutil.copy2(os.path.join(d, bs[-1]), ruta)
        print("revertido desde %s" % bs[-1])
        return 0

    src = io.open(ruta, encoding="utf-8", errors="replace").read()

    if "ROI_ABAJO" in src or "ROI_ARRIBA" in src:
        print("  %s YA tiene el recorte aplicado. No se toca." % ruta)
        return 0

    # --- 1. la declaracion, junto a las otras variables de entorno ----------
    if src.count(ANCLA_DECL) != 1:
        print("  *** No encontre la linea de AREA_MIN_LINEA (%d veces)."
              % src.count(ANCLA_DECL))
        print("  *** NO escribo nada.")
        return 1
    src2 = src.replace(ANCLA_DECL, ANCLA_DECL + NL + DECL, 1)

    # --- 2. el bloque, en el lazo de linea ---------------------------------
    n = src2.count(ANCLA_BLOQUE)
    if n != 1:
        print("  *** El bloque `_ang_viejo / _quien / _r` aparece %d veces." % n)
        print("  *** Esperaba exactamente 1. NO escribo nada.")
        return 1
    src2 = src2.replace(ANCLA_BLOQUE, BLOQUE, 1)

    # --- 3. verificar que compila ------------------------------------------
    try:
        ast.parse(src2)
    except SyntaxError as e:
        print("  *** El resultado NO compila (%s). No escribo nada." % e)
        return 1

    if a.ver:
        print("  Cambios que se aplicarian a %s:" % ruta)
        print("")
        print("  1. junto a las variables de entorno:")
        for l in DECL.split(NL):
            print("     + %s" % l)
        print("")
        print("  2. en el lazo de linea, despues de `_r = None`:")
        for l in BLOQUE.split(NL)[3:]:
            print("     + %s" % l)
        print("  (--ver: no se escribio nada)")
        return 0

    sello = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = "%s.recorte_%s" % (ruta, sello)
    shutil.copy2(ruta, bak)
    io.open(ruta, "w", encoding="utf-8").write(src2)
    print("  backup : %s" % os.path.basename(bak))
    print("  aplicado a %s" % ruta)
    print("")
    print("  Control PRIMERO. Tiene que andar igual que hoy:")
    print("      ROI_ARRIBA=60 python3 main.py")
    print("")
    print("  Y despues el barrido. MAS giro = BAJAR el corte de arriba:")
    print("      GRABAR=~/a70.avi ROI_ARRIBA=70 python3 main.py")
    print("      GRABAR=~/a80.avi ROI_ARRIBA=80 python3 main.py")
    print("      GRABAR=~/a90.avi ROI_ARRIBA=90 python3 main.py")
    print("")
    print("  El recorte de ABAJO baja el giro. Esta por si se quiere lo otro:")
    print("      GRABAR=~/b95.avi ROI_ABAJO=95 python3 main.py")
    print("")
    print("  Para volver atras:")
    print("      python3 aplicar_recorte.py main.py --revertir")
    return 0


if __name__ == "__main__":
    sys.exit(main())

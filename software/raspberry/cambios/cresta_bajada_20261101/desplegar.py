# -*- coding: utf-8 -*-
"""Instala CRESTA-BAJADA + PLATEADO en la Pi. Correr EN LA PI desde la carpeta copiada (ver RESULTADO.md):

    python3 desplegar.py

Comprueba que el main.py del Desktop sea el que se espera, que los archivos nuevos sean los de este paquete y que
compilen; hace un respaldo y reemplaza. Si algo no coincide, no toca nada.
"""
import datetime
import hashlib
import json
import os
import py_compile
import shutil
import sys
from pathlib import Path

D = Path(os.environ.get('DESKTOP_PI', '/home/iita/Desktop'))
AQUI = Path(__file__).resolve().parent
ACTUAL = {
    'df73beb17034566873db5bf2d32655f73a8aa8ac12cc7036e662db85fe5f5097',   # main.py de la Pi al 1-nov 14:09
    'eb60f7a26c6298ff36eb034a24ee21c6e82e9299adb29aab544a9f0906a3e10f',   # CRESTA-BAJADA sin el plateado (1-nov)
    'e91869114a80507fc92aea627b96e624c22715a3ca9d3c5425fdf11346d2ee81',   # este paquete con umbral 1740 (7-nov)
}
NUEVOS = {
    'main.py': '9da00beb31af7af6fdd39785b9b2ff886be002c3e6ec108bb60dfb819099d578',
    'verde_cresta.py': '5d93c15671ed37993f63e25db257f2cb741c6e3da5fbb681f08ac44203612737',
    'rampa_transicion.py': '642df9735e4f96de031cffb5d71e0f3b31f980b9036049d873e780e7a6af203c',
    'plateado_entrada.py': '9abbfe476ffdaa1540da3805466a77a35b313eb07fc89f802bd66144f33ce517',
    'calibrar_plateado.py': 'f825fe52834a1c68529103c37a5fc3fd2b29b32dcf88bacca529515835eb0797',
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if sha(D / 'main.py') not in ACTUAL:
        sys.exit('NO SE INSTALA: el main.py del Desktop no es el esperado (%s). Alguien lo cambio.' % sha(D / 'main.py'))
    for nombre, h in NUEVOS.items():
        if sha(AQUI / nombre) != h:
            sys.exit('NO SE INSTALA: %s no es el del paquete (copia incompleta?)' % nombre)
        py_compile.compile(str(AQUI / nombre), doraise=True)
    sys.path.insert(0, str(AQUI))
    os.environ['VERDE_CRESTA'] = '1'
    import verde_cresta
    g = verde_cresta.VerdeCresta()
    assert g.verde(2, True, 0.0) == 2 and g.activo(0.1) and g.verde(0, True, 0.6) == 0
    assert g.verde(1, True, 1.2) == 0   # el mismo cuadrado visto otra vez: no se repite
    os.environ['PLATEADO_RECTA'] = '1'
    import numpy as np
    import plateado_entrada
    gris = np.full((120, 160, 3), 130, np.uint8); gris[::2, ::2] = 175; gris[1::2, 1::2] = 175
    blanco = np.full((120, 160, 3), 255, np.uint8)
    p = plateado_entrada.PlateadoEntrada()
    for _ in range(6):
        p.observar(gris)
    p.perdida(); p.despues_del_retroceso(gris)
    assert p.evaluar('CURVA IZQ')[0] is True             # banda al llegar y despues: derecho
    p.perdida(); p.despues_del_retroceso(gris)
    assert p.evaluar('CURVA DER')[0] is False            # a la derecha solo se anota
    p.perdida(); p.despues_del_retroceso(gris)
    assert p.evaluar('CURVA IZQ', 5.0)[0] is False       # rampa hace 5 s: no actua
    p.perdida(); p.despues_del_retroceso(blanco)
    assert p.evaluar('CURVA IZQ')[0] is False            # sin banda despues del retroceso: no toca nada
    respaldo = D / ('respaldo_cresta_bajada_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    respaldo.mkdir()
    for nombre in NUEVOS:
        if (D / nombre).exists():
            shutil.copy2(D / nombre, respaldo / nombre)
    for nombre in NUEVOS:
        shutil.copy2(AQUI / nombre, D / nombre)
    for nombre, h in NUEVOS.items():
        assert sha(D / nombre) == h, nombre
    r = dict(respaldo=str(respaldo), **{n: sha(D / n) for n in NUEVOS})
    (respaldo / 'despliegue.json').write_text(json.dumps(r, indent=2))
    print(json.dumps(r, indent=2))
    print('Instalado. Al arrancar main.py tienen que aparecer: [VERDE-CRESTA] VERDE-CRESTA-1 VERDE_CRESTA=1')
    print('                                                  y [PLATEADO] PLATEADO-ENTRADA-1 PLATEADO_RECTA=1 umbral=1790')
    print('En la sede, el umbral del plateado: python3 calibrar_plateado.py --entrada ... --vuelta ... (ver RESULTADO.md)')
    print('Para volver atras: cp %s/* /home/iita/Desktop/' % respaldo)


if __name__ == '__main__':
    main()

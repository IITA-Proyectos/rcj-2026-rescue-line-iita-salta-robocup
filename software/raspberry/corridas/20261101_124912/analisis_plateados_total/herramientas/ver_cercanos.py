# Cuadros de llegada y post de las curvas IZQ que no son plateado y quedan mas cerca del umbral, junto a dos plateados.
import json, os, sys, csv, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rasgos_plateado as RP
from al_decidir import puntaje
BASE = RP.BASE
eps = {(e['corrida'], e['video']): e for e in json.load(open('episodios.json'))}
casos = [('1-nov 13:54', '4:03.30'), ('31-oct 22:11', '5:28.70'), ('1-nov 12:49', '18:13.75'), ('1-nov 12:49', '13:26.45'), ('1-nov 12:49', '17:31.75')]
filas = []
for k in casos:
    e = eps[k]; r = list(csv.DictReader(open(os.path.join(BASE, e['run'], e['cr'], 'cuadros.csv')))); idx = {int(x['n']): i for i, x in enumerate(r)}
    i0 = idx[e['n_gs4']]; kc = next(j for j in range(i0, i0 + 80) if r[j]['quien'] == 'recup-CURVA')
    ini = idx[e['post'][0]]
    ns = [int(r[j]['n']) for j in range(i0 - 6, i0)] + [int(r[j]['n']) for j in range(ini, kc + 1)]
    ims = []
    for j, n in enumerate(ns):
        im = cv2.resize(RP.cuadro(e, n), (320, 240), interpolation=cv2.INTER_NEAREST)
        cv2.putText(im, ('L' if j < 6 else 'P') + ' %d' % puntaje(RP.cuadro(e, n)), (4, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        ims.append(im)
    while len(ims) < 10: ims.append(np.zeros_like(ims[0]))
    fila = np.hstack(ims[:10]); cv2.putText(fila, '%s %s' % k, (4, 232), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    filas.append(fila)
cv2.imwrite('cercanos.jpg', cv2.resize(np.vstack(filas), None, fx=0.6, fy=0.6))
print('ok')

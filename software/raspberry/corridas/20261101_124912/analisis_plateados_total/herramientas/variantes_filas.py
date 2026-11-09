# Puntaje de banda desde distintas filas: con la camara mirando lejos los reflejos quedan en el medio de la imagen.
import csv, json, os, sys, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rasgos_plateado as RP
from rasgos2 import PLATEADO
BASE = RP.BASE
FILAS = (40, 50, 60, 70, 80)
def puntajes(im):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); S = hsv[..., 1].astype(np.float32); V = hsv[..., 2].astype(np.float32)
    m = cv2.blur(V, (5, 5)); sd = np.sqrt(np.maximum(cv2.blur(V * V, (5, 5)) - m * m, 0))
    t = (S < 60) & (V > 110) & (V < 225) & (sd > 7)
    return [int(t[f:].sum()) for f in FILAS]
eps = json.load(open('episodios.json')); cache = {}; out = []
for e in eps:
    key = (e['run'], e['cr'])
    if key not in cache:
        r = list(csv.DictReader(open(os.path.join(BASE, e['run'], e['cr'], 'cuadros.csv')))); cache[key] = (r, {int(x['n']): i for i, x in enumerate(r)})
    r, idx = cache[key]; i0 = idx[e['n_gs4']]
    kc = next((k for k in range(i0, min(len(r), i0 + 80)) if r[k]['quien'] == 'recup-CURVA'), None)
    if kc is None or float(r[kc]['angle']) <= 0: continue
    ini = idx.get(e['post'][0], kc) if e['post'] else kc
    post = [int(r[k]['n']) for k in range(min(ini, kc), kc + 1)]
    pre = [int(r[k]['n']) for k in range(i0 - 6, i0)]
    sp = np.array([puntajes(RP.cuadro(e, n)) for n in post]); sa = np.array([puntajes(RP.cuadro(e, n)) for n in pre])
    out.append(dict(k=e['corrida'] + ' ' + e['video'], plateado=(e['corrida'], e['video']) in PLATEADO,
                    pre=np.median(sa, axis=0).tolist(), post=np.median(sp, axis=0).tolist()))
for v, f in enumerate(FILAS):
    pl = [f2 for f2 in out if f2['plateado']]; no = [f2 for f2 in out if not f2['plateado']]
    mpl = min(min(x['pre'][v], x['post'][v]) for x in pl)
    tops = sorted(no, key=lambda x: -min(x['pre'][v], x['post'][v]))[:3]
    print('filas %d+: plateado min %5d | no plateado: %s | cociente %.2f' % (
        f, mpl, ', '.join('%s %d/%d' % (x['k'], x['pre'][v], x['post'][v]) for x in tops), mpl / min(tops[0]['pre'][v], tops[0]['post'][v])))

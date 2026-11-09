# Variantes del puntaje de banda sobre las 279 CURVA: actual vs sin los bordes de la cinta negra.
import csv, json, os, sys, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rasgos_plateado as RP
from rasgos2 import PLATEADO
BASE = RP.BASE
K5 = np.ones((5, 5), np.uint8); K9 = np.ones((9, 9), np.uint8)
def puntajes(im):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); S = hsv[..., 1].astype(np.float32); V = hsv[..., 2].astype(np.float32)
    m = cv2.blur(V, (5, 5)); sd = np.sqrt(np.maximum(cv2.blur(V * V, (5, 5)) - m * m, 0))
    t = (S < 60) & (V > 110) & (V < 225) & (sd > 7)
    negro = cv2.inRange(im, np.array([0, 0, 0]), np.array([90, 90, 90]))
    cerca5 = cv2.dilate(negro, K5) > 0; cerca9 = cv2.dilate(negro, K9) > 0
    return (int(t[40:].sum()), int((t & ~cerca5)[40:].sum()), int((t & ~cerca9)[40:].sum()))
eps = json.load(open('episodios.json')); cache = {}; out = []
for e in eps:
    key = (e['run'], e['cr'])
    if key not in cache:
        r = list(csv.DictReader(open(os.path.join(BASE, e['run'], e['cr'], 'cuadros.csv')))); cache[key] = (r, {int(x['n']): i for i, x in enumerate(r)})
    r, idx = cache[key]; i0 = idx[e['n_gs4']]
    kc = next((k for k in range(i0, min(len(r), i0 + 80)) if r[k]['quien'] == 'recup-CURVA'), None)
    if kc is None: continue
    ini = idx.get(e['post'][0], kc) if e['post'] else kc
    post = [int(r[k]['n']) for k in range(min(ini, kc), kc + 1)]
    pre = [int(r[k]['n']) for k in range(i0 - 6, i0)]
    sp = np.array([puntajes(RP.cuadro(e, n)) for n in post]); sa = np.array([puntajes(RP.cuadro(e, n)) for n in pre])
    out.append(dict(k=[e['corrida'], e['video']], lado='IZQ' if float(r[kc]['angle']) > 0 else 'DER', plateado=(e['corrida'], e['video']) in PLATEADO,
                    pre=np.median(sa, axis=0).tolist(), post=np.median(sp, axis=0).tolist()))
json.dump(out, open('variantes_banda.json', 'w'))
for v, nom in enumerate(('actual', 'sin borde 5x5', 'sin borde 9x9')):
    print('==', nom)
    for lado in ('IZQ', 'DER'):
        pl = [f for f in out if f['lado'] == lado and f['plateado']]; no = [f for f in out if f['lado'] == lado and not f['plateado']]
        if not pl: continue
        mpl = min(min(f['pre'][v], f['post'][v]) for f in pl)
        top = sorted((min(f['pre'][v], f['post'][v]) for f in no), reverse=True)[:4]
        print('  %s plateado min(pre,post) minimo %d (pre %s) | no plateado mayores %s  -> cociente %.2f' % (
            lado, mpl, sorted(int(f['pre'][v]) for f in pl), [int(x) for x in top], mpl / top[0]))

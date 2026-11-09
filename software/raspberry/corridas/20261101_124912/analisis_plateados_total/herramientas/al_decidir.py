# Puntaje de banda con los cuadros que la Pi tiene AL DECIDIR la CURVA (desde el fin del retroceso hasta el primer
# 'recup-CURVA'), y con los 6 cuadros de la llegada (antes del GS4).
import json, sys, csv, os, cv2, numpy as np
NEW = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, NEW)
import rasgos_plateado as RP
from rasgos2 import PLATEADO
BASE = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas'
def puntaje(im):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); S = hsv[..., 1].astype(np.float32); V = hsv[..., 2].astype(np.float32)
    m = cv2.blur(V, (5, 5)); sd = np.sqrt(np.maximum(cv2.blur(V * V, (5, 5)) - m * m, 0))
    t = (S < 60) & (V > 110) & (V < 225) & (sd > 7)
    return int(t[40:].sum())
if __name__ == '__main__':
    eps = json.load(open(NEW + '/episodios.json')); cache = {}; filas = []
    for e in eps:
        key = (e['run'], e['cr'])
        if key not in cache:
            r = list(csv.DictReader(open(os.path.join(BASE, e['run'], e['cr'], 'cuadros.csv')))); cache[key] = (r, {int(x['n']): i for i, x in enumerate(r)})
        r, idx = cache[key]; i0 = idx[e['n_gs4']]
        kc = next((k for k in range(i0, min(len(r), i0 + 80)) if r[k]['quien'] == 'recup-CURVA'), None)
        if kc is None: continue
        ang = float(r[kc]['angle'])
        ini = idx.get(e['post'][0], kc) if e['post'] else kc
        post = [int(r[k]['n']) for k in range(min(ini, kc), kc + 1)]
        pre = [int(r[k]['n']) for k in range(i0 - 6, i0)]
        sp = [puntaje(RP.cuadro(e, n)) for n in post]; sa = [puntaje(RP.cuadro(e, n)) for n in pre]
        filas.append(dict(k=[e['corrida'], e['video']], lado='IZQ' if ang > 0 else 'DER', plateado=(e['corrida'], e['video']) in PLATEADO,
                          n_post=len(post), post_med=float(np.median(sp)), post_max=max(sp), pre_med=float(np.median(sa))))
    json.dump(filas, open(NEW + '/al_decidir.json', 'w'))
    izq = [f for f in filas if f['lado'] == 'IZQ']
    for campo in ('post_med', 'post_max', 'pre_med'):
        pl = sorted(int(f[campo]) for f in izq if f['plateado']); no = sorted((int(f[campo]) for f in izq if not f['plateado']), reverse=True)
        print('%-8s plateado %s | resto (mayores) %s' % (campo, pl, no[:6]))
    print('cuadros entre fin del retroceso y la decision:', sorted(f['n_post'] for f in izq if f['plateado']), 'resto mediana', int(np.median([f['n_post'] for f in izq if not f['plateado']])))

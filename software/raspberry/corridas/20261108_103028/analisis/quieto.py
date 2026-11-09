# Cuando estuvo quieto el robot en la corrida del 8-nov 10:30 y que estaba mandando la Pi en ese momento.
import csv, sys, collections
import cv2, numpy as np
from concurrent.futures import ProcessPoolExecutor
D = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas/20261108_103028/crudo_prueba_103028/1108_103036'
def gris(n):
    im = cv2.imread('%s/f_%06d.png' % (D, n), cv2.IMREAD_GRAYSCALE)
    return im
def dif(par):
    a, b = gris(par[0]), gris(par[1])
    if a is None or b is None: return -1.0
    return float(cv2.absdiff(a, b).mean())
if __name__ == '__main__':
    F = list(csv.DictReader(open(D + '/cuadros.csv')))
    pares = [(int(F[k - 1]['n']), int(F[k]['n'])) for k in range(1, len(F))]
    with ProcessPoolExecutor(12) as ex: d = [0.0] + list(ex.map(dif, pares, chunksize=200))
    t = [float(x['t']) for x in F]
    with open('quieto_dif.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['n', 't', 'dif'])
        for x, v in zip(F, d): w.writerow([x['n'], x['t'], round(v, 3)])
    print('dif mediana', np.median(d), 'p5', np.percentile(d, 5), 'p95', np.percentile(d, 95))
    print('huecos de tiempo > 0.5 s:')
    for k in range(1, len(F)):
        if t[k] - t[k - 1] > .5: print('  n=%s t=%.1f hueco %.2f s (%s/%s -> %s/%s)' % (F[k]['n'], t[k], t[k] - t[k - 1], F[k - 1]['estado'], F[k - 1]['quien'][:18], F[k]['estado'], F[k]['quien'][:18]))
    U = 0.9   # bajo este cambio medio la imagen esta quieta (se ajusta mirando la mediana)
    tramos = []; ini = None
    for k, v in enumerate(d):
        if v >= 0 and v < U:
            if ini is None: ini = k
        else:
            if ini is not None and t[k - 1] - t[ini] >= .8: tramos.append((ini, k - 1))
            ini = None
    if ini is not None and t[-1] - t[ini] >= .8: tramos.append((ini, len(F) - 1))
    print('imagen quieta >= 0.8 s: %d tramos' % len(tramos))
    for a, b in tramos:
        s = F[a:b + 1]
        q = collections.Counter(x['quien'][:24] for x in s).most_common(3)
        e = collections.Counter(x['estado'] for x in s).most_common(1)[0][0]
        sp = collections.Counter(x['speed'] for x in s).most_common(2)
        g = collections.Counter(x['green_state'] for x in s).most_common(3)
        print('  n=%s-%s t=%.1f-%.1f dura %.1f s | %s | vel %s | gs %s | %s | ang %.0f..%.0f | rampa %s' % (s[0]['n'], s[-1]['n'], t[a], t[b], t[b] - t[a], e, sp, g, q, min(float(x['angle']) for x in s), max(float(x['angle']) for x in s), s[0]['rampa']))

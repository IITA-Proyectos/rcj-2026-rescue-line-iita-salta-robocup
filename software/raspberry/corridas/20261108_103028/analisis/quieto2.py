import csv, collections, sys
import cv2, numpy as np
D = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas/20261108_103028/crudo_prueba_103028/1108_103036'
F = list(csv.DictReader(open(D + '/cuadros.csv')))
dif = {int(x['n']): float(x['dif']) for x in csv.DictReader(open('quieto_dif.csv'))}
t = [float(x['t']) for x in F]
d = [dif[int(x['n'])] for x in F]
print('histograma dif:', np.histogram(d, bins=[0, 1, 2, 3, 4, 5, 6, 8, 10, 15, 20, 40, 200])[0].tolist())
g = lambda n: cv2.imread('%s/f_%06d.png' % (D, n), cv2.IMREAD_GRAYSCALE)
print('\n=== HUECOS: se movio entre antes y despues? (dif entre el cuadro de antes y el de despues; movido si >>4)')
print(' n antes  dura  dif_ab | estado/quien antes -> despues | vel antes')
for k in range(1, len(F)):
    h = t[k] - t[k - 1]
    if h > .5:
        a, b = g(int(F[k - 1]['n'])), g(int(F[k]['n']))
        da = float(cv2.absdiff(a, b).mean())
        print(' %6s %6.2f %6.1f | %s/%s -> %s/%s | v=%s a=%s gs=%s' % (F[k - 1]['n'], h, da, F[k - 1]['estado'][:6], F[k - 1]['quien'][:24], F[k]['estado'][:6], F[k]['quien'][:22], F[k - 1]['speed'], F[k - 1]['angle'], F[k - 1]['green_state']))
for U in (3.0, 4.5):
    tramos = []; ini = None
    for k, v in enumerate(d):
        if k and t[k] - t[k - 1] > .5:  # el hueco corta
            if ini is not None and t[k - 1] - t[ini] >= .5: tramos.append((ini, k - 1))
            ini = None
        if v < U:
            if ini is None: ini = k
        else:
            if ini is not None and t[k - 1] - t[ini] >= .5: tramos.append((ini, k - 1))
            ini = None
    print('\n=== imagen casi quieta (dif<%.1f) >= 0.5 s: %d tramos' % (U, len(tramos)))
    for a, b in tramos[:45]:
        s = F[a:b + 1]
        q = collections.Counter(x['quien'][:26] for x in s).most_common(2)
        sp = collections.Counter(x['speed'] for x in s).most_common(2)
        gg = collections.Counter(x['green_state'] for x in s).most_common(2)
        print('  n=%s-%s t=%.1f-%.1f dura %.1f | vel %s | gs %s | %s | ang %.0f..%.0f' % (s[0]['n'], s[-1]['n'], t[a], t[b], t[b] - t[a], sp, gg, q, min(float(x['angle']) for x in s), max(float(x['angle']) for x in s)))
c0 = collections.Counter(x['quien'] for x in F if float(x['speed']) == 0)
print('\ncuadros con velocidad 0 mandada: %d | por etiqueta: %s' % (sum(c0.values()), c0.most_common(12)))

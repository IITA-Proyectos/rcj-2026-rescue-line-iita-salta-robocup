import csv
import cv2
C = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas'
RUNS = {'31-oct 19:53': C + '/20261031_195318/crudo_20261031_195318/1031_195426', '1-nov 11:47': C + '/20261101_114747/crudo_verde_sombra_20261101_114747/1101_114752',
        '1-nov 12:49': C + '/20261101_124912/crudo_doble_dato_20261101_124912/1101_124926', '7-nov 18:41': C + '/20261107_182348/crudo_prueba_182348/1107_184121',
        '7-nov 19:03': C + '/20261107_190335/crudo_prueba_190335/1107_190339', '8-nov 10:30': C + '/20261108_103028/crudo_prueba_103028/1108_103036'}
for nom, D in RUNS.items():
    F = list(csv.DictReader(open(D + '/cuadros.csv'))); t = [float(x['t']) for x in F]; s = []
    tot = 0
    for k in range(1, len(F)):
        h = t[k] - t[k - 1]
        if h > .5:
            tot += 1
            a = cv2.imread('%s/f_%06d.png' % (D, int(F[k - 1]['n'])), 0); b = cv2.imread('%s/f_%06d.png' % (D, int(F[k]['n'])), 0)
            if a is None or b is None: continue
            d = float(cv2.absdiff(a, b).mean())
            if d < 14: s.append('n=%s %.2fs (dif %.1f) %s' % (F[k]['n'], h, d, F[k - 1]['quien'][:14]))
    print(nom, '| huecos', tot, '| sin moverse:', s)

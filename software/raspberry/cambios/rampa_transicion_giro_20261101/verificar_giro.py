"""Replay de RAMPA-TRANSICION-2 sobre la corrida 20261101_124912 (mascara desde el panel del video)."""
import sys, csv, cv2, numpy as np
sys.path.insert(0, '.')
import rampa_transicion as rt

C = '../../corridas/20261101_124912/'
r = {int(x['n']): x for x in csv.DictReader(open(C + 'cuadros.csv'))}
cap = cv2.VideoCapture(C + 'pista_doble_dato_20261101_124912.avi')
t = rt.RampTransition()
n = 0
while True:
    ok, im = cap.read()
    n += 1
    if not ok or n not in r:
        break
    x = r[n]
    q = x['quien']
    who = 'rampa-linea' if q.startswith('rampa-transicion') else q
    m = cv2.resize(im[:, 320:, 0], (160, 120), interpolation=cv2.INTER_NEAREST) > 128
    m[:60] = False
    armado = t.armed
    res = t.step(x['rampa'] == '1', who, m.astype(np.uint8), float(x['t']))
    if armado and not t.armed and t.side_bottoms:
        print('suelta', n, '%d:%05.2f' % (n / 20 // 60, n / 20 % 60))
    if q.startswith('rampa-transicion') and res is None:
        print('  cambia', n, q)

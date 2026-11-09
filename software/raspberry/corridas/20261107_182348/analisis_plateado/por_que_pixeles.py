# Por que la banda cuenta poco: cada pixel de la fila 40 para abajo, coloreado por la condicion que no cumple.
import csv, sys, cv2, numpy as np
SW = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas'
def frame(cr, hhmmss=None, t0=None, n=None):
    if n is None:
        r = list(csv.DictReader(open(cr + '/cuadros.csv')))
        h, m, s = [float(x) for x in hhmmss.split(':')]; th = h * 3600 + m * 60 + s - t0
        n = int(min(r, key=lambda x: abs(float(x['t']) - th))['n'])
    return n, cv2.imread(cr + '/f_%06d.png' % n)
def capas(im):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); S = hsv[..., 1].astype(np.float32); V = hsv[..., 2].astype(np.float32)
    m = cv2.blur(V, (5, 5)); sd = np.sqrt(np.maximum(cv2.blur(V * V, (5, 5)) - m * m, 0))
    cuenta = (S < 60) & (V > 110) & (V < 225) & (sd > 7)
    out = np.zeros_like(im)
    out[(V >= 225)] = (0, 220, 255)                       # amarillo: demasiado brillante
    out[(V <= 110)] = (90, 90, 90)                        # gris: oscuro
    out[(S >= 60) & (V > 110) & (V < 225)] = (255, 0, 255)  # magenta: color (saturado)
    out[(S < 60) & (V > 110) & (V < 225) & (sd <= 7)] = (255, 120, 0)  # azul: gris liso, sin textura
    out[cuenta] = (0, 200, 0)                             # verde: cuenta
    out[:40] = 0
    return int(cuenta[40:].sum()), {k: int(v[40:].sum()) for k, v in (('brillo>=225', V >= 225), ('liso', (S < 60) & (V > 110) & (V < 225) & (sd <= 7)))}, out
C7 = SW + '/20261107_182348/crudo_prueba_182348/1107_184121'; T7 = 18 * 3600 + 41 * 60 + 21
C1 = SW + '/20261101_124912/crudo_doble_dato_20261101_124912/1101_124926'
casos = [('7-nov 18:55:03 zona real, no actua', *frame(C7, '18:55:02.9', T7)),
         ('7-nov 18:45:07 zona real, no actua', *frame(C7, '18:45:07.7', T7)),
         ('7-nov 18:43:35 otra entrada, RECTA', *frame(C7, '18:43:35.3', T7)),
         ('1-nov 12:49 13:26 entrada (1856)', *frame(C1, n=16126)),
         ('1-nov 12:49 12:47 entrada (3406)', *frame(C1, n=15337))]
filas = []
for nombre, n, im in casos:
    tot, otros, ov = capas(im)
    a = cv2.resize(im, (320, 240), interpolation=cv2.INTER_NEAREST); b = cv2.resize(ov, (320, 240), interpolation=cv2.INTER_NEAREST)
    f = np.hstack([a, b]); cv2.putText(f, '%s  n=%d' % (nombre, n), (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    cv2.putText(f, 'cuenta %d | brillo>=225 %d | liso %d' % (tot, otros['brillo>=225'], otros['liso']), (4, 234), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    filas.append(f); print('%-38s cuenta %5d  brillo>=225 %5d  liso %5d' % (nombre, tot, otros['brillo>=225'], otros['liso']))
cv2.imwrite('por_que_pixeles.jpg', np.vstack(filas))

import csv
import cv2, numpy as np
D = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas/20261108_103028/crudo_prueba_103028/1108_103036'
F = list(csv.DictReader(open(D + '/cuadros.csv')))
t = [float(x['t']) for x in F]
W, H = 240, 180
pares = []
for k in range(1, len(F)):
    h = t[k] - t[k - 1]
    if h > .5:
        n0, n1 = int(F[k - 1]['n']), int(F[k]['n'])
        a = cv2.resize(cv2.imread('%s/f_%06d.png' % (D, n0)), (W, H), interpolation=cv2.INTER_NEAREST)
        b = cv2.resize(cv2.imread('%s/f_%06d.png' % (D, n1)), (W, H), interpolation=cv2.INTER_NEAREST)
        cv2.putText(a, '%d antes' % n0, (3, 14), cv2.FONT_HERSHEY_SIMPLEX, .42, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(b, 'despues %.1f s' % h, (3, 14), cv2.FONT_HERSHEY_SIMPLEX, .42, (0, 255, 255), 1, cv2.LINE_AA)
        sep = np.full((H, 3, 3), 255, np.uint8)
        pares.append(np.hstack([a, b, sep, sep]))
filas = [np.hstack(pares[i:i + 3]) for i in range(0, len(pares), 3)]
ancho = max(f.shape[1] for f in filas)
filas = [np.hstack([f, np.zeros((H, ancho - f.shape[1], 3), np.uint8)]) if f.shape[1] < ancho else f for f in filas]
cv2.imwrite('huecos_103028.jpg', np.vstack(filas), [cv2.IMWRITE_JPEG_QUALITY, 86])
print(len(pares))

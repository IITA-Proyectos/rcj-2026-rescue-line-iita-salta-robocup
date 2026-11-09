# Figura para el equipo: que mira la regla nueva en el verde a ignorar y en verdes buenos.
import cv2, numpy as np
OLD2 = 'C:/Users/villa/AppData/Local/Temp/claude/C--Users-villa-rcj-2026-rescue-line-iita-salta-robocup-priority-fixes-software/854db1e8-8208-468d-aedc-be6567aabe63/scratchpad'
C = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas'
D = {'0719': C + '/20261107_190335/crudo_prueba_190335/1107_190339', '1249': C + '/20261101_124912/crudo_doble_dato_20261101_124912/1101_124926', '1953': C + '/20261031_195318/crudo_20261031_195318/1031_195426'}
LG, UG = np.array([120, 90, 110]), np.array([198, 109, 134])
K = 3
def fila(run, n, titulo, sub, color):
    im = cv2.imread('%s/f_%06d.png' % (D[run], n)); lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)
    lo = LG.copy(); up = UG.copy(); lo[0] = min(int(lo[0]), 60); up[1] = max(int(up[1]), 111); up[2] = max(int(up[2]), 137)
    m = np.zeros(lab.shape[:2], np.uint8); m[80:] = cv2.inRange(lab[80:], lo, up)
    xs = np.flatnonzero(m.any(axis=0)); L, R = int(xs[0]), int(xs[-1])
    col = lab[:, L:R + 1]; v = col[..., 1] < 120; neg = (col[..., 0] < 97) & ~v
    fr = v.mean(axis=1); f = np.flatnonzero(m[:, L:R + 1].any(axis=1)); y0, y1 = int(f[0]), int(f[-1])
    while y0 > 0 and fr[y0 - 1] > .15: y0 -= 1
    while y1 < 119 and fr[y1 + 1] > .15: y1 += 1
    a0, a1 = max(0, y0 - 14), max(0, y0 - 2); b0, b1 = y1 + 3, min(120, y1 + 15)
    ar = float(neg[a0:a1].mean()) if a1 > a0 else -1; ab = float(neg[b0:b1].mean()) if b1 > b0 else -1
    a = cv2.resize(im, (160 * K, 120 * K), interpolation=cv2.INTER_NEAREST)
    cv2.rectangle(a, (L * K, a0 * K), ((R + 1) * K - 1, a1 * K - 1), (0, 255, 255), 2)
    cv2.rectangle(a, (L * K, b0 * K), ((R + 1) * K - 1, b1 * K - 1), (255, 0, 255), 2)
    t = np.full((a.shape[0], 400, 3), 255, np.uint8)
    cv2.putText(t, titulo, (12, 44), cv2.FONT_HERSHEY_SIMPLEX, .72, color, 2, cv2.LINE_AA)
    cv2.putText(t, sub, (12, 80), cv2.FONT_HERSHEY_SIMPLEX, .5, (70, 70, 70), 1, cv2.LINE_AA)
    cv2.rectangle(t, (12, 120), (40, 142), (0, 255, 255), -1); cv2.putText(t, 'cinta arriba: %.0f %%' % (100 * ar), (50, 139), cv2.FONT_HERSHEY_SIMPLEX, .68, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.rectangle(t, (12, 168), (40, 190), (255, 0, 255), -1); cv2.putText(t, 'cinta abajo: %.0f %%' % (100 * ab), (50, 187), cv2.FONT_HERSHEY_SIMPLEX, .68, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.putText(t, 'ignora solo si: arriba < 5 %', (12, 250), cv2.FONT_HERSHEY_SIMPLEX, .52, (70, 70, 70), 1, cv2.LINE_AA)
    cv2.putText(t, 'y abajo > 80 %', (118, 276), cv2.FONT_HERSHEY_SIMPLEX, .52, (70, 70, 70), 1, cv2.LINE_AA)
    return np.hstack([a, t])
filas = [fila('0719', 9507, 'IGNORA (el que fallo)', '7-nov 19:03, cuadro 9507', (0, 0, 200)),
         fila('1953', 6573, 'IGNORA (mismo caso, a la derecha)', '31-oct 19:53, cuadro 6573', (0, 0, 200)),
         fila('1249', 18853, 'GIRA igual que antes', 'verde bueno mas parecido (1-nov 12:49, 18853)', (0, 130, 0))]
cv2.imwrite('regla_verde_ya_cruzado.jpg', np.vstack(filas), [cv2.IMWRITE_JPEG_QUALITY, 90])

# Cada verde que ejecuto el robot hoy (primer cuadro con gs != 0): tiene el mismo patron de "ya cruzado"? Lo decidio otro detector?
import csv
import cv2, numpy as np
D = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas/20261108_103028/crudo_prueba_103028/1108_103036'
F = list(csv.DictReader(open(D + '/cuadros.csv'))); N = {int(x['n']): k for k, x in enumerate(F)}
S = {int(x['n']): x for x in csv.DictReader(open('hoy_sombra.csv'))}
LG, UG = np.array([120, 90, 110]), np.array([198, 109, 134])
def banda(n):
    im = cv2.imread('%s/f_%06d.png' % (D, n)); lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)
    lo = LG.copy(); up = UG.copy(); lo[0] = min(int(lo[0]), 60); up[1] = max(int(up[1]), 111); up[2] = max(int(up[2]), 137)
    m = np.zeros(lab.shape[:2], np.uint8); m[80:] = cv2.inRange(lab[80:], lo, up)
    xs = np.flatnonzero(m.any(axis=0))
    if len(xs) < 2: return None
    L, R = int(xs[0]), int(xs[-1])
    col = lab[:, L:R + 1]; v = col[..., 1] < 120; neg = (col[..., 0] < 97) & ~v
    fr = v.mean(axis=1); f = np.flatnonzero(m[:, L:R + 1].any(axis=1)); y0, y1 = int(f[0]), int(f[-1])
    while y0 > 0 and fr[y0 - 1] > .15: y0 -= 1
    while y1 < 119 and fr[y1 + 1] > .15: y1 += 1
    a0, a1 = max(0, y0 - 14), max(0, y0 - 2); b0, b1 = y1 + 3, min(120, y1 + 15)
    return L, R, (float(neg[a0:a1].mean()) if a1 > a0 else -1.0), (float(neg[b0:b1].mean()) if b1 > b0 else -1.0)
ini = []; ult = -999
for k, x in enumerate(F):
    if x['green_state'] in ('1', '2', '3'):
        n = int(x['n'])
        if n - ult > 25: ini.append(n)
        ult = n
filas = []
for n in ini:
    b = banda(n)
    filas.append((n, F[N[n]]['green_state'], 'sombra' if n in S else 'otro', b))
print('verdes ejecutados hoy:', len(filas), '| por detector de sombra:', sum(1 for f in filas if f[2] == 'sombra'))
print('con menos cinta arriba:')
for n, gs, q, b in sorted([f for f in filas if f[3] and f[3][2] >= 0], key=lambda f: f[3][2])[:14]:
    print('  n=%d video %d:%04.1f gs%s %s L-R %d-%d arriba %.3f abajo %.3f' % (n, n // 1200, (n % 1200) / 20.0, gs, q, b[0], b[1], b[2], b[3]))
ev = [2221, 2449, 4985, 5070, 5143]
W, H = 200, 150; hoja = []
for n in ev:
    c = []
    for d in (-3, 0, 14, 28, 44, 60):
        m = n + d
        if m not in N: continue
        im = cv2.resize(cv2.imread('%s/f_%06d.png' % (D, m)), (W, H), interpolation=cv2.INTER_NEAREST)
        cv2.putText(im, '%d gs%s' % (m, F[N[m]]['green_state']), (3, 13), cv2.FONT_HERSHEY_SIMPLEX, .42, (0, 255, 255), 1, cv2.LINE_AA)
        c.append(im)
    while len(c) < 6: c.append(np.zeros((H, W, 3), np.uint8))
    hoja.append(np.hstack(c))
cv2.imwrite('falsos_hoy.jpg', np.vstack(hoja), [cv2.IMWRITE_JPEG_QUALITY, 86])

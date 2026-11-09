# Giro (yaw) acumulado de la camara desde el video GRABAR, con flujo optico LK sobre el fondo (franja de arriba).
# f ~ 238 px en el panel de 320 (f 119 px a 160, medido 15-sep). Positivo = izquierda (igual que el angulo de la Pi).
import csv, sys, math, cv2, numpy as np
run, video, a, b = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
F = 238.0
r = {int(x['n']): x for x in csv.DictReader(open(run + '/crudo/cuadros.csv'))}
cap = cv2.VideoCapture(run + '/' + video)
cap.set(cv2.CAP_PROP_POS_FRAMES, a - 1)
prev = None; acc = 0.0
mask = np.zeros((240, 320), np.uint8); mask[0:105, :] = 255; mask[0:60, 0:150] = 0
for n in range(a, b + 1):
    ok, f = cap.read()
    if not ok: break
    g = cv2.cvtColor(f[:, :320], cv2.COLOR_BGR2GRAY)
    d = ''
    if prev is not None:
        p0 = cv2.goodFeaturesToTrack(prev, 80, 0.01, 6, mask=mask)
        if p0 is not None and len(p0) >= 6:
            p1, st, err = cv2.calcOpticalFlowPyrLK(prev, g, p0, None, winSize=(21, 21), maxLevel=3)
            ok2 = st.ravel() == 1
            if ok2.sum() >= 6:
                dx = (p1[ok2, 0, 0] - p0[ok2, 0, 0])
                # dx>0: el fondo se corre a la derecha -> la camara gira a la izquierda
                dyaw = math.degrees(math.atan(np.median(dx) / F))
                acc += dyaw; d = '%+.1f' % dyaw
    prev = g
    x = r.get(n, {})
    print('%5d t=%s gs%s %-26s manda %6s | dyaw %5s acum %+6.1f' % (n, x.get('t'), x.get('green_state'), x.get('quien', '')[:26], x.get('angle'), d, acc))

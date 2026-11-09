# Barre TODOS los cuadros crudos y anota cada vez que decide detectar_verde_sombra (principal y oscuro en 0):
# que parte del "negro arriba" es negro de verdad y que parte es verde oscuro.
import csv, os, sys, json
import cv2, numpy as np
from concurrent.futures import ProcessPoolExecutor
OLD = 'C:/Users/villa/AppData/Local/Temp/claude/274c7b50715ed49f/854db1e8-8208-468d-aedc-be6567aabe63/scratchpad'
OLD2 = 'C:/Users/villa/AppData/Local/Temp/claude/C--Users-villa-rcj-2026-rescue-line-iita-salta-robocup-priority-fixes-software/854db1e8-8208-468d-aedc-be6567aabe63/scratchpad'
C = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas'
RUNS = [('1953', C + '/20261031_195318/crudo_20261031_195318/1031_195426'),
        ('2103', C + '/20261031_210305/crudo_pista_completa_20261031_210305/1031_210325'),
        ('2136', C + '/20261031_213650/crudo_recuperacion_corregida_20261031_213650/1031_213701'),
        ('2211', C + '/20261031_221132/crudo_reenganche_20261031_221132/1031_221136'),
        ('1031', C + '/20261101_103155/crudo_cierre3_20261101_103155/1101_103200'),
        ('1111', C + '/20261101_111110/crudo_rampa_transicion_20261101_111110/1101_111120'),
        ('1147', C + '/20261101_114747/crudo_verde_sombra_20261101_114747/1101_114752'),
        ('1238', C + '/20261101_124912/crudo_doble_dato_20261101_123804/1101_123809'),
        ('1249', C + '/20261101_124912/crudo_doble_dato_20261101_124912/1101_124926'),
        ('1354', OLD2 + '/fr135438'),
        ('1409', OLD2 + '/fr140905'),
        ('0718', C + '/20261107_182348/crudo_prueba_182348/1107_184121'),
        ('0719', C + '/20261107_190335/crudo_prueba_190335/1107_190339')]
LG, UG = np.array([120, 90, 110]), np.array([198, 109, 134])
TS = (112, 114, 116, 118, 120, 122, 124, 126)
ZB, UB = np.zeros(3, np.uint8), np.array([90, 90, 90], np.uint8)

def una(job):
    nombre, D = job
    sys.dont_write_bytecode = True
    sys.path.insert(0, OLD + '/simE')
    from verde_oscuro import detectar_verde_oscuro, detectar_verde_sombra
    filas = list(csv.DictReader(open(D + '/cuadros.csv')))
    out = []; vistos = faltan = 0
    for f in filas:
        n = int(f['n']); im = cv2.imread('%s/f_%06d.png' % (D, n))
        if im is None: faltan += 1; continue
        vistos += 1
        lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)
        neg = cv2.inRange(im, ZB, UB); neg[:60] = 0
        gm = np.zeros((120, 160), np.uint8); gm[80:] = cv2.inRange(lab[80:], LG, UG)
        gs_p = 0
        if np.count_nonzero(gm) > 200:
            cols = np.amax(gm, axis=0); idx = np.where(cols == cols.max())[0]; L, R = int(idx[0]), int(idx[-1])
            if R > L and np.sum(neg[60:90, L:R + 1]) / (255 * 30 * (R - L)) > .32 and np.sum(neg[90:]): gs_p = 1
        if gs_p: continue
        go, _ = detectar_verde_oscuro(lab, neg, LG, UG, 200, 1.0)
        if go: continue
        gs, msk = detectar_verde_sombra(lab, neg, LG, UG, 200, 1.0)
        if not gs: continue
        # misma mascara cruda que usa la ocupacion
        lo = LG.copy(); up = UG.copy(); lo[0] = min(int(lo[0]), 60); up[1] = max(int(up[1]), 111); up[2] = max(int(up[2]), 137)
        m = np.zeros(neg.shape, np.uint8); m[80:] = cv2.inRange(lab[80:], lo, up)
        xs = np.flatnonzero(m.any(axis=0)); L, R = int(xs[0]), int(xs[-1])
        sl = neg[60:90, L:R + 1] > 0
        a = lab[60:90, L:R + 1, 1]; b = lab[60:90, L:R + 1, 2]; ll = lab[60:90, L:R + 1, 0]
        den = 30.0 * (R - L); occ = np.count_nonzero(sl) / den
        fila = dict(run=nombre, n=n, robot=int(f['green_state']), quien=f['quien'], gs=int(gs), area=int(np.count_nonzero(m)), L=L, R=R, occ=round(occ, 3))
        pa = np.percentile(a[sl], [5, 50, 95]).astype(int).tolist() if sl.any() else [0, 0, 0]
        pb = np.percentile(b[sl], [5, 50, 95]).astype(int).tolist() if sl.any() else [0, 0, 0]
        pl = np.percentile(ll[sl], [5, 50, 95]).astype(int).tolist() if sl.any() else [0, 0, 0]
        fila.update(a5=pa[0], a50=pa[1], a95=pa[2], b5=pb[0], b50=pb[1], b95=pb[2], l5=pl[0], l50=pl[1], l95=pl[2])
        for T in TS: fila['o%d' % T] = round(np.count_nonzero(sl & (a >= T)) / den, 3)
        out.append(fila)
    return nombre, vistos, faltan, out

if __name__ == '__main__':
    with ProcessPoolExecutor(12) as ex:
        res = list(ex.map(una, RUNS))
    todas = []
    for nombre, v, fa, out in res:
        print('%s cuadros %6d faltan %5d | decide sombra %3d' % (nombre, v, fa, len(out)), flush=True); todas += out
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'barrido_sombra.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(todas[0].keys())); w.writeheader(); w.writerows(todas)
    print('total', len(todas))

# Regla candidata solo con LAB (lo que recibe detectar_verde_sombra) y barrido de parametros: que cuadros cambian.
import csv, itertools, collections
import cv2, numpy as np
from concurrent.futures import ProcessPoolExecutor
OLD2 = 'C:/Users/villa/AppData/Local/Temp/claude/C--Users-villa-rcj-2026-rescue-line-iita-salta-robocup-priority-fixes-software/854db1e8-8208-468d-aedc-be6567aabe63/scratchpad'
C = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas'
D = {'1953': C + '/20261031_195318/crudo_20261031_195318/1031_195426',
     '2103': C + '/20261031_210305/crudo_pista_completa_20261031_210305/1031_210325',
     '2136': C + '/20261031_213650/crudo_recuperacion_corregida_20261031_213650/1031_213701',
     '2211': C + '/20261031_221132/crudo_reenganche_20261031_221132/1031_221136',
     '1031': C + '/20261101_103155/crudo_cierre3_20261101_103155/1101_103200',
     '1111': C + '/20261101_111110/crudo_rampa_transicion_20261101_111110/1101_111120',
     '1147': C + '/20261101_114747/crudo_verde_sombra_20261101_114747/1101_114752',
     '1238': C + '/20261101_124912/crudo_doble_dato_20261101_123804/1101_123809',
     '1249': C + '/20261101_124912/crudo_doble_dato_20261101_124912/1101_124926',
     '1409': OLD2 + '/fr140905', '0719': C + '/20261107_190335/crudo_prueba_190335/1107_190339'}
LG, UG = np.array([120, 90, 110]), np.array([198, 109, 134])
def medir(x, LN=97, AV=120, FR=.15, ALTO=12, GAP=2):
    im = cv2.imread('%s/f_%06d.png' % (D[x['run']], int(x['n']))); lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)
    lo = LG.copy(); up = UG.copy(); lo[0] = min(int(lo[0]), 60); up[1] = max(int(up[1]), 111); up[2] = max(int(up[2]), 137)
    m = np.zeros(lab.shape[:2], np.uint8); m[80:] = cv2.inRange(lab[80:], lo, up)
    xs = np.flatnonzero(m.any(axis=0)); L, R = int(xs[0]), int(xs[-1])
    col = lab[:, L:R + 1]; verd = col[..., 1] < AV; neg = (col[..., 0] < LN) & ~verd
    fr = verd.mean(axis=1); f = np.flatnonzero(m[:, L:R + 1].any(axis=1)); y0, y1 = int(f[0]), int(f[-1])
    while y0 > 0 and fr[y0 - 1] > FR: y0 -= 1
    while y1 < 119 and fr[y1 + 1] > FR: y1 += 1
    a0, a1 = max(0, y0 - GAP - ALTO), max(0, y0 - GAP); b0, b1 = min(120, y1 + 1 + GAP), min(120, y1 + 1 + GAP + ALTO)
    return (float(neg[a0:a1].mean()) if a1 > a0 else -1.0, float(neg[b0:b1].mean()) if b1 > b0 else -1.0)
def m_rejilla(x):
    out = {}
    for LN, AV, ALTO, GAP in itertools.product((85, 97, 110), (116, 120, 124), (9, 12, 15), (1, 2, 3)):
        out[(LN, AV, ALTO, GAP)] = medir(x, LN, AV, .15, ALTO, GAP)
    return out
if __name__ == '__main__':
    print('BGR 90 gris -> L', cv2.cvtColor(np.uint8([[[90, 90, 90]]]), cv2.COLOR_BGR2LAB).ravel())
    r = [x for x in csv.DictReader(open('barrido_sombra.csv')) if x['run'] != '1354']
    with ProcessPoolExecutor(12) as ex:
        base = list(ex.map(medir, r, chunksize=20))
        rej = list(ex.map(m_rejilla, r, chunksize=20))
    print('valores base (L<97, a>=120, banda 12, gap 2):')
    orden = sorted(zip(base, r), key=lambda t: t[0][0])
    for (ar, ab), x in orden[:14]:
        print(' ', x['run'], x['n'], 'rob', x['robot'], 'gs', x['gs'], 'L-R', x['L'], x['R'], 'arriba %.3f abajo %.3f' % (ar, ab))
    print('\numbral arriba / abajo -> cuadros que cambian (con cada ajuste de la rejilla)')
    conj = collections.Counter(); tabla = collections.defaultdict(set)
    claves = list(rej[0].keys())
    for k in claves:
        for ua, ub in itertools.product((.02, .05, .08, .12), (.3, .5, .7, .9)):
            s = frozenset((x['run'], int(x['n'])) for x, m in zip(r, rej) if m[k][0] >= 0 and m[k][1] >= 0 and m[k][0] < ua and m[k][1] > ub)
            conj[s] += 1; tabla[s].add((k, ua, ub))
    tot = sum(conj.values())
    for s, c in conj.most_common(12):
        print('%5d de %d ajustes -> %s' % (c, tot, sorted(s)))

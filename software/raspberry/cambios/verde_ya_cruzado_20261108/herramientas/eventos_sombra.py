# Agrupa en eventos los cuadros donde decide sombra y mira, en la imagen ENTERA (sin el recorte de la fila 60),
# que hay justo arriba del borde superior del cuadrado: cinta negra de verdad o piso claro.
import csv, sys, collections
import cv2, numpy as np
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
r = list(csv.DictReader(open('barrido_sombra.csv')))
def medir(run, n, L, R):
    im = cv2.imread('%s/f_%06d.png' % (D[run], n)); lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)
    neg = cv2.inRange(im, np.zeros(3, np.uint8), np.array([90, 90, 90], np.uint8)) > 0
    verdoso = lab[..., 1] < 120
    negro_real = neg & ~verdoso
    claro = (im.min(axis=2) > 120) & ~verdoso
    sub = slice(L, R + 1)
    # primera fila (de abajo hacia arriba desde 100) sin verde/verde oscuro: borde superior del cuadrado
    col = verdoso[:, sub] & (lab[:, sub, 0] < 200)
    frac = col.mean(axis=1)
    y = 100
    while y > 0 and frac[y] > 0.15: y -= 1
    tope = y + 1
    b0, b1 = max(0, tope - 14), max(1, tope - 2)
    ban_neg = negro_real[b0:b1, sub].mean() if b1 > b0 else 0.0
    ban_cla = claro[b0:b1, sub].mean() if b1 > b0 else 0.0
    return tope, float(ban_neg), float(ban_cla)
ev = []; act = None
for x in r:
    n = int(x['n'])
    if act and act['run'] == x['run'] and n - act['ult'] <= 3:
        act['ult'] = n; act['filas'].append(x)
    else:
        act = dict(run=x['run'], ini=n, ult=n, filas=[x]); ev.append(act)
print('eventos', len(ev))
sal = []
for e in ev:
    falso = [x for x in e['filas'] if float(x['o120']) <= 0.32]
    x = e['filas'][0]; n = int(x['n'])
    t, bn, bc = medir(x['run'], n, int(x['L']), int(x['R']))
    e.update(tope=t, bn=bn, bc=bc, nfalso=len(falso), n=len(e['filas']))
    sal.append(dict(run=e['run'], ini=e['ini'], ult=e['ult'], cuadros=len(e['filas']), filtrados=len(falso), robot=','.join(sorted(set(q['robot'] for q in e['filas']))),
                    gs=x['gs'], area=x['area'], L=x['L'], R=x['R'], occ=x['occ'], o120=x['o120'], tope=t, negro_arriba=round(bn, 3), claro_arriba=round(bc, 3), quien=x['quien']))
with open('eventos_sombra.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(sal[0].keys())); w.writeheader(); w.writerows(sal)

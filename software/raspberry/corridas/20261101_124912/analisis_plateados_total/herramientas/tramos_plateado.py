# A/B por tramos: cada corrida se corta en los huecos de tiempo (reubicacion, rescate) y cada tramo se simula
# desde cero con simB (paquete cresta_bajada) y simC (+ PLATEADO_RECTA=1).
import csv, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
SP = os.path.dirname(os.path.abspath(__file__))
C = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas'
V1 = C + '/20261101_135438/pista_giro_cresta_20261101_135438.avi'
RUNS = [('1953', C + '/20261031_195318/crudo_20261031_195318/1031_195426', None),
        ('2103', C + '/20261031_210305/crudo_pista_completa_20261031_210305/1031_210325', None),
        ('2136', C + '/20261031_213650/crudo_recuperacion_corregida_20261031_213650/1031_213701', None),
        ('2211', C + '/20261031_221132/crudo_reenganche_20261031_221132/1031_221136', None),
        ('1031', C + '/20261101_103155/crudo_cierre3_20261101_103155/1101_103200', None),
        ('1111', C + '/20261101_111110/crudo_rampa_transicion_20261101_111110/1101_111120', None),
        ('1147', C + '/20261101_114747/crudo_verde_sombra_20261101_114747/1101_114752', None),
        ('1238', C + '/20261101_124912/crudo_doble_dato_20261101_123804/1101_123809', None),
        ('1249', C + '/20261101_124912/crudo_doble_dato_20261101_124912/1101_124926', None),
        ('1354', SP + '/fr135438', V1),
        ('1409', SP + '/fr140905', None)]
def tramos(D):
    r = list(csv.DictReader(open(os.path.join(D, 'cuadros.csv'))))
    t = [float(x['t']) for x in r]; ini = 0; out = []
    for k in range(len(r)):
        if k == len(r) - 1 or t[k + 1] - t[k] > 0.5:
            if k - ini >= 30: out.append((int(r[ini]['n']), int(r[k]['n'])))
            ini = k + 1
    return out
trabajos = []
for nombre, D, vid in RUNS:
    for a, b in tramos(D):
        for var in os.environ.get('VARS', 'B,C').split(','):
            O = os.path.join(SP, 'tr_' + var); os.makedirs(O, exist_ok=True)
            trabajos.append((var, nombre, D, vid, a, b, os.path.join(O, '%s_%06d.csv' % (nombre, a))))
def correr(j):
    var, nombre, D, vid, a, b, salida = j
    env = dict(os.environ)
    if vid: env['SIM_VIDEO'] = vid
    if var == 'C0': env['PLATEADO_RECTA'] = '0'
    with open(salida[:-4] + '.txt', 'w') as f:
        subprocess.run([sys.executable, '-I', 'simular.py', D, salida, str(a), str(b)], cwd=os.path.join(SP, 'sim' + var[0]), env=env, stdout=f, stderr=subprocess.STDOUT)
print('simulaciones:', len(trabajos), flush=True)
with ThreadPoolExecutor(22) as ex:
    list(ex.map(correr, trabajos))
open(os.path.join(SP, 'tr_LISTO'), 'w').write('listo')
print('listo')

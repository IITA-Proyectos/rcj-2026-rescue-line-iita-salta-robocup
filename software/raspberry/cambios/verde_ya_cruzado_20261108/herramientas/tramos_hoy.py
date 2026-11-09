# La corrida de hoy (8-nov 10:30), que NO se uso para armar la regla: simE (Pi actual) contra simF (con la regla).
import csv, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
SP = os.path.dirname(os.path.abspath(__file__))
OLD = 'C:/Users/villa/AppData/Local/Temp/claude/274c7b50715ed49f/854db1e8-8208-468d-aedc-be6567aabe63/scratchpad'
D = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas/20261108_103028/crudo_prueba_103028/1108_103036'
r = list(csv.DictReader(open(D + '/cuadros.csv'))); t = [float(x['t']) for x in r]; ini = 0; T = []
for k in range(len(r)):
    if k == len(r) - 1 or t[k + 1] - t[k] > 0.5:
        if k - ini >= 30: T.append((int(r[ini]['n']), int(r[k]['n'])))
        ini = k + 1
J = []
for var, carpeta in (('E', OLD + '/simE'), ('F', SP + '/simF')):
    O = os.path.join(SP, 'hoy_' + var); os.makedirs(O, exist_ok=True)
    J += [(carpeta, a, b, os.path.join(O, '0811_%06d.csv' % a)) for a, b in T]
def correr(j):
    c, a, b, s = j
    with open(s[:-4] + '.txt', 'w') as f:
        subprocess.run([sys.executable, '-I', '-B', 'simular.py', D, s, str(a), str(b)], cwd=c, stdout=f, stderr=subprocess.STDOUT)
print('tramos', len(T), flush=True)
with ThreadPoolExecutor(20) as ex: list(ex.map(correr, J))
print('listo')

# Todas las recuperaciones (GS4) de las corridas: cuadros despues del retroceso (ventana de decision) y como terminaron.
import csv, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inventario_bajadas import RUNS
BASE = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas'
def mmss(n): return '%d:%05.2f' % (n / 20 // 60, n / 20 % 60)
eps = []
for nombre, run, cr, vid in RUNS:
    d = os.path.join(BASE, run, cr); r = list(csv.DictReader(open(os.path.join(d, 'cuadros.csv')))); N = len(r)
    tn = [float(x['t']) for x in r]
    i = 1
    while i < N:
        if r[i]['green_state'] == '4' and r[i - 1]['green_state'] != '4':
            # fin del retroceso: ultimo 'recup-espera-retro-ack' del episodio
            j = i
            while j < N - 1 and tn[j] - tn[i] < 4.0 and r[j]['quien'] != 'recup-espera-retro-ack': j += 1
            while j < N - 1 and r[j + 1]['quien'] == 'recup-espera-retro-ack': j += 1
            ini = j + 1
            post = [k for k in range(ini, N) if tn[k] - tn[ini] <= 1.2]
            dec = next((r[k]['quien'] for k in range(ini, min(N, ini + 60)) if r[k]['quien'] in ('recup-CURVA', 'gap-inicio', 'recup-AMBIGUA')), '-')
            dec2 = next((r[k]['quien'] for k in range(ini, min(N, ini + 60)) if r[k]['quien'] in ('recup-CURVA', 'gap-inicio')), '-')
            fin = '-'
            for k in range(ini, min(N, ini + 200)):
                if k + 1 < N and tn[k + 1] - tn[k] > 1.0:
                    fin = 'hueco %.0f s' % (tn[k + 1] - tn[k]); break
                if r[k]['green_state'] == '19': fin = 'PARADA'; break
            eps.append(dict(corrida=nombre, run=run, cr=cr, vid=vid, n_gs4=int(r[i]['n']), video=mmss(int(r[i]['n'])),
                            post=[int(r[k]['n']) for k in post], decision=dec2 if dec2 != '-' else dec, fin=fin))
            i = j + 1
        else:
            i += 1
json.dump(eps, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'episodios.json'), 'w'))
import collections
print('episodios:', len(eps), collections.Counter(e['corrida'] for e in eps))
print(collections.Counter(e['decision'] for e in eps))

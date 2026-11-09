# Compara simD (Pi del 7-nov) con simE (+ doble de ChatGPT) tramo por tramo.
import csv, glob, os, re, collections
SP = os.path.dirname(os.path.abspath(__file__))
leer = lambda p: list(csv.DictReader(open(p)))
tot = 0; dif = []; igual_robot = collections.Counter(); cuadros = collections.Counter()
ev = {'D': collections.Counter(), 'E': collections.Counter()}
for pd in sorted(glob.glob(SP + '/tr_D/*.csv')):
    if pd.endswith('_clasif.csv'): continue
    pe = pd.replace('tr_D', 'tr_E'); nom = os.path.basename(pd)[:-4]; corrida = nom.split('_')[0]
    a, b = leer(pd), leer(pe)
    assert [x['n'] for x in a] == [x['n'] for x in b], nom
    tot += len(a)
    for x in a:
        cuadros[corrida] += 1; igual_robot[corrida] += x['quien'] == x['quien_robot']
    d = [(x, y) for x, y in zip(a, b) if (x['quien'], x['angle'], x['green_state']) != (y['quien'], y['angle'], y['green_state'])]
    if d:
        x, y = d[0]
        dif.append((nom, len(a), len(d), x, y))
    for var, p in (('D', pd), ('E', pe)):
        for l in open(p[:-4] + '.log', encoding='utf-8', errors='replace'):
            if '[VERDE-CRESTA] verde' in l and 'subiendo' in l: ev[var]['cresta armada'] += 1
            elif '[VERDE-CRESTA] suelta: cinta' in l: ev[var]['cresta conecta'] += 1
            elif '[VERDE-CRESTA] suelta por tope' in l: ev[var]['cresta tope'] += 1
            elif '[BAJADA] cinta perdida' in l: ev[var]['bajada recupera'] += 1
            elif re.search(r'\[PLATEADO\] \S+ CURVA IZQ .*-> RECTA', l): ev[var]['plateado RECTA'] += 1
print('cuadros comparados:', tot, '| tramos con diferencias:', len(dif))
for nom, n, k, x, y in dif:
    print('  %-14s primer cuadro distinto n=%s: D %s %s gs%s | E %s %s gs%s | robot %s gs%s  (%d de %d distintos)' % (
        nom, x['n'], x['quien'][:18], x['angle'], x['green_state'], y['quien'][:18], y['angle'], y['green_state'],
        x['quien_robot'][:18], x['gs_robot'], k, n))
print('\neventos en el log  D:', dict(ev['D']), '\n                   E:', dict(ev['E']))
print('\netiqueta igual a la del robot (D):', ', '.join('%s %.0f%%' % (c, 100.0 * igual_robot[c] / cuadros[c]) for c in sorted(cuadros)))

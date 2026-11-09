# Compara simE (lo que corre hoy en la Pi) con simF (+ regla del verde ya cruzado), tramo por tramo.
import csv, glob, os, re, collections, sys
SP = os.path.dirname(os.path.abspath(__file__))
E = 'C:/Users/villa/AppData/Local/Temp/claude/274c7b50715ed49f/854db1e8-8208-468d-aedc-be6567aabe63/scratchpad/tr_E'
F = sys.argv[1] if len(sys.argv) > 1 else SP + '/tr_F'
leer = lambda p: list(csv.DictReader(open(p)))
tot = 0; dif = []; faltan = []; ev = {'E': collections.Counter(), 'F': collections.Counter()}; ignorados = []
cuadros = collections.Counter()
for pf in sorted(glob.glob(F + '/*.csv')):
    if pf.endswith('_clasif.csv'): continue
    nom = os.path.basename(pf)[:-4]
    pe = os.path.join(E, nom + '.csv')
    if not os.path.exists(pe): faltan.append(nom); continue
    a, b = leer(pe), leer(pf)
    assert [x['n'] for x in a] == [x['n'] for x in b], nom
    tot += len(a); cuadros[nom.split('_')[0]] += len(a)
    d = [(x, y) for x, y in zip(a, b) if (x['quien'], x['angle'], x['green_state']) != (y['quien'], y['angle'], y['green_state'])]
    if d: dif.append((nom, len(a), d))
    for var, p in (('E', pe), ('F', pf)):
        for l in open(p[:-4] + '.log', encoding='utf-8', errors='replace'):
            if '[VERDE-SOMBRA] gs=' in l: ev[var]['sombra decide'] += 1
            elif '[VERDE-SOMBRA] ignorado' in l:
                ev[var]['sombra ignora'] += 1
                if var == 'F': ignorados.append((nom, l.strip()))
            elif '[VERDE-CRESTA] verde' in l and 'subiendo' in l: ev[var]['cresta armada'] += 1
            elif '[VERDE-CRESTA] suelta: cinta' in l: ev[var]['cresta conecta'] += 1
            elif '[BAJADA] cinta perdida' in l: ev[var]['bajada recupera'] += 1
            elif re.search(r'\[PLATEADO\] \S+ CURVA IZQ .*-> RECTA', l): ev[var]['plateado RECTA'] += 1
print('cuadros comparados: %d en %d tramos | tramos con diferencias: %d | sin par: %d' % (tot, sum(1 for p in glob.glob(F + '/*.csv') if not p.endswith('_clasif.csv')), len(dif), len(faltan)))
print('por corrida:', dict(cuadros))
for nom, n, d in dif:
    print('\n== %s (%d de %d cuadros distintos)' % (nom, len(d), n))
    for x, y in d[:14]:
        print('   n=%s  antes %s ang %s gs%s | ahora %s ang %s gs%s | robot real %s gs%s' % (x['n'], x['quien'][:20], x['angle'], x['green_state'], y['quien'][:20], y['angle'], y['green_state'], x['quien_robot'][:18], x['gs_robot']))
print('\neventos en el log  antes:', dict(ev['E']), '\n                   ahora:', dict(ev['F']))
print('\nveces que actuo la regla:', len(ignorados))
for nom, l in ignorados: print('  ', nom, l)

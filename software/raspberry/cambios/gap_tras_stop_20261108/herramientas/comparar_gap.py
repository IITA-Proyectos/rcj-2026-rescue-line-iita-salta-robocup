# Compara F (lo instalado hoy: verde ya cruzado) con G (+ GUARD_STOP_GAP). Todo primer cuadro distinto tiene que ser el STOP del guard.
import csv, glob, os, collections
leer = lambda p: list(csv.DictReader(open(p)))
tot = 0; ok = []; malos = []; iguales = 0; antes = 0
for pg in sorted(glob.glob('tr_G/*.csv')):
    if pg.endswith('_clasif.csv'): continue
    nom = os.path.basename(pg)[:-4]
    pf = ('hoy_F/' if nom.startswith('0811') else 'tr_F/') + nom + '.csv'
    if not os.path.exists(pf): print('sin par', nom); continue
    a, b = leer(pf), leer(pg)
    assert [x['n'] for x in a] == [x['n'] for x in b], nom
    tot += len(a)
    k = next((i for i, (x, y) in enumerate(zip(a, b)) if (x['quien'], x['angle'], x['green_state']) != (y['quien'], y['angle'], y['green_state'])), None)
    if k is None: iguales += 1; continue
    antes += k
    x, y = a[k], b[k]
    fila = (nom, x['n'], x['quien'], x['green_state'], y['quien'], y['green_state'], len(a) - k, x['quien_robot'][:22], x['gs_robot'])
    (ok if x['quien'] == 'recup-guard-stop' and x['green_state'] == '19' and y['quien'] == 'recup-guard-gap' and y['green_state'] == '18' else malos).append(fila)
print('cuadros comparados', tot, '| tramos identicos', iguales, '| tramos con diferencia', len(ok) + len(malos))
print('primer cuadro distinto = STOP del guard convertido en GAP:', len(ok))
print('primer cuadro distinto en OTRA cosa:', len(malos))
for f in malos[:30]: print('   ', f)
print('por corrida:', dict(collections.Counter(f[0].split('_')[0] for f in ok)))
reales = [f for f in ok if f[8] == '19']
print('de esos, con el robot real en GS19 en ese cuadro:', len(reales))

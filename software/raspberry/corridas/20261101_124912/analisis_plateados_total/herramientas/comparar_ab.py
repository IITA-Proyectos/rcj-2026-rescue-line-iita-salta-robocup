import csv, sys
a = list(csv.DictReader(open(sys.argv[1]))); b = list(csv.DictReader(open(sys.argv[2])))
assert [x['n'] for x in a] == [x['n'] for x in b]
dif = [(x, y) for x, y in zip(a, b) if (x['quien'], x['angle'], x['green_state']) != (y['quien'], y['angle'], y['green_state'])]
print('cuadros distintos: %d de %d' % (len(dif), len(a)))
tr = []; cur = None
for x, y in dif:
    n = int(x['n'])
    if cur and n <= cur[1] + 3: cur[1] = n; cur[2].append((x, y))
    else: cur = [n, n, [(x, y)]]; tr.append(cur)
for s, e, l in tr:
    q0 = sorted({x['quien'] for x, _ in l}); q1 = sorted({y['quien'] for _, y in l})
    print('  %5d-%5d (%3d) VC0 %s\n               -> VC1 %s' % (s, e, len(l), q0[:5], q1[:5]))

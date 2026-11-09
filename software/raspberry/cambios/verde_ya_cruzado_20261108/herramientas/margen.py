import csv, sys
sys.dont_write_bytecode = True
sys.path.insert(0, 'C:/Users/villa/AppData/Local/Temp/claude/274c7b50715ed49f/2a6124af-dd8b-472c-b95b-351384f76cc1/scratchpad')
from regla_candidata import medir
from concurrent.futures import ProcessPoolExecutor
if __name__ == '__main__':
    r = [x for x in csv.DictReader(open('barrido_sombra.csv')) if x['run'] != '1354']
    with ProcessPoolExecutor(12) as ex: b = list(ex.map(medir, r, chunksize=20))
    m = list(zip(b, r))
    print('poco negro arriba (<0.20), ordenados por negro abajo:')
    for (ar, ab), x in sorted([t for t in m if 0 <= t[0][0] < .20], key=lambda t: -t[0][1])[:16]:
        print(' ', x['run'], x['n'], 'gs', x['gs'], 'rob', x['robot'], 'arriba %.3f abajo %.3f' % (ar, ab))

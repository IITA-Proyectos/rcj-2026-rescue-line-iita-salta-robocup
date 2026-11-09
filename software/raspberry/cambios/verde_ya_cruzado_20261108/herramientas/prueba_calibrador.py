# El calibrador de ChatGPT sigue entendiendo verde_oscuro.py con el cambio? Y la version calibrada conserva la regla?
import importlib.util, shutil, sys, tempfile
from pathlib import Path
import cv2, numpy as np
sys.dont_write_bytecode = True
SP = Path(__file__).resolve().parent
CAL = Path('C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/cambios/calibrador_verdes_express_20261102')
sys.path.insert(0, str(CAL))
spec = importlib.util.spec_from_file_location('tool', CAL / 'calibrador_verdes_express.py'); tool = importlib.util.module_from_spec(spec); sys.modules['tool'] = tool; spec.loader.exec_module(tool)
C = 'C:/Users/villa/rcj-2026-rescue-line-iita-salta-robocup-priority-fixes/software/raspberry/corridas/20261107_190335/crudo_prueba_190335/1107_190339'
LG, UG = np.array([120, 90, 110]), np.array([198, 109, 134])
with tempfile.TemporaryDirectory() as t:
    root = Path(t)
    for f in (SP / 'simF').glob('*.py'):
        if f.name not in ('simular.py',): shutil.copy2(f, root / f.name)
    d = tool.Detector(root / 'main.py')
    print('Detector construido. Archivos con huella:', sorted(d.paths))
    print('piso de sombra leido:', d.base_shadow_floor)
    for piso in (d.base_shadow_floor, 45):
        d.shadow_floor = piso
        fn = d.shadow_function(True)
        for n in (9507, 9508, 9795, 9509):
            im = cv2.imread('%s/f_%06d.png' % (C, n)); lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)
            neg = cv2.inRange(im, np.zeros(3, np.uint8), np.array([90, 90, 90], np.uint8)); neg[:60] = 0
            print('  piso', piso, 'cuadro', n, '-> gs', fn(lab, neg, LG, UG, 200, 1.0)[0])

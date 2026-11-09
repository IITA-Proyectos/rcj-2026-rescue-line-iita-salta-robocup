from pathlib import Path
import ast,hashlib,json,os,py_compile,shutil,datetime
import numpy as np
D=Path('/home/iita/Desktop');S=D/'.rampa_transicion_1';expected='991df6bf36ce29d61457df8e46a9a67e6ab7b96c9f3d911a3d1dd6051f20e098';rh='c3333b7e51f479cea041c656402438dc6a818f5d34ec4971f93ce0d910c9f52f'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(D/'main.py')==expected
assert sha(D/'recuperacion_guard.py')==rh
for name in ['main.py','rampa_transicion.py']:
 ast.parse((S/name).read_text());py_compile.compile(str(S/name),doraise=True)
ns={};exec(compile((S/'rampa_transicion.py').read_text(),'helper','exec'),ns);g=ns['RampTransition']();m=np.zeros((120,160),np.uint8);m[60:,75:85]=255
for i in range(20):assert g.step(True,'rampa-recta',m,i*.03) is None
assert abs(g.step(True,'rampa-linea',m,.65)['angle'])<=15
assert g.step(True,'rampa-cresta-recto',m,.69) is None
assert g.step(False,'centroide',m,.72) is None
backup=D/('respaldo_rampa_transicion_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));backup.mkdir()
for name in ['main.py','recuperacion_guard.py','rampa_transicion.py']:
 if (D/name).exists():shutil.copy2(D/name,backup/name)
assert sha(D/'main.py')==expected
os.replace(S/'rampa_transicion.py',D/'rampa_transicion.py');os.replace(S/'main.py',D/'main.py')
assert sha(D/'recuperacion_guard.py')==rh
result=dict(backup=str(backup),main=sha(D/'main.py'),rampa=sha(D/'rampa_transicion.py'),recuperacion=sha(D/'recuperacion_guard.py'))
(backup/'despliegue.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

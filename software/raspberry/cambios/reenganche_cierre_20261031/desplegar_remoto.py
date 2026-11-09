from pathlib import Path
import ast,hashlib,json,os,py_compile,shutil,datetime,sys
D=Path('/home/iita/Desktop');S=D/'.reenganche_3';expected={'main.py':'991df6bf36ce29d61457df8e46a9a67e6ab7b96c9f3d911a3d1dd6051f20e098','recuperacion_guard.py':'7beb66b2a11786f20fba0ab512f9ccae0149d2bda1cddb3e77d982b4cefc0845'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name,old in expected.items():
 assert sha(D/name)==old, 'El archivo cambio: '+name
 ast.parse((S/name).read_text());py_compile.compile(str(S/name),doraise=True)
sys.path.insert(0,str(D))
ns={};exec(compile((S/'recuperacion_guard.py').read_text(),'helper','exec'),ns)
import numpy as np
g=ns['RecoveryGuard']();g.evidence=dict(side=1,left=0,right=20);m=np.zeros((120,160),np.uint8);m[60:76,5:20]=255;e=np.zeros_like(m)
g.remember_fragment(m,10);g.begin_finish(1,10);g.finish(10,e,e,0)
assert g.finish(10.36,e,e,0)==dict(action='SEARCH',angle=85.0)
assert g.finish(11.37,e,e,0)['action']=='STOP'
backup=D/('respaldo_reenganche_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));backup.mkdir()
for name in expected:shutil.copy2(D/name,backup/name)
for name,old in expected.items():assert sha(D/name)==old
for name in ['recuperacion_guard.py','main.py']:os.replace(S/name,D/name)
result={name:sha(D/name) for name in expected};result['backup']=str(backup)
(backup/'despliegue.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

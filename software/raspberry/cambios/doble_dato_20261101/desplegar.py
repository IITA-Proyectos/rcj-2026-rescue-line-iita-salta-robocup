from pathlib import Path
import ast,hashlib,json,os,py_compile,shutil,datetime
import numpy as np
D=Path('/home/iita/Desktop');S=D/'.doble_dato_1';expected='ecdeaa4d6b2c5f8da832b19b9d5f8c5b7357e3333541db13e280c656fb825186';keep={'verde_oscuro.py':'5bdded29693df6ef2f9eda3765edfd6f1f6382c032a7bc2f98c3c4a55f611da7','rampa_transicion.py':'ed46092fd1854b5c3c5e6251f58ad8c059e3839d4fdff581efc832a47ca580d0','recuperacion_guard.py':'c3333b7e51f479cea041c656402438dc6a818f5d34ec4971f93ce0d910c9f52f'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(D/'main.py')==expected
for n,h in keep.items():assert sha(D/n)==h,n
for n in ['main.py','doble_dato.py']:ast.parse((S/n).read_text());py_compile.compile(str(S/n),doraise=True)
ns={};exec(compile((S/'doble_dato.py').read_text(),'helper','exec'),ns)
lab=np.full((120,160,3),[240,128,128],dtype=np.uint8);black=np.zeros((120,160),np.uint8);black[90:,75:85]=255;lab[70:115,110:150]=[70,105,128];black[60:70,110:150]=255;lab[70:79,30:65]=[70,105,128];black[60:70,30:65]=255
g=ns['DoubleData']();assert g.step(2,lab,black,10)==3
assert g.step(1,lab,black,10.04)==3
assert g.step(0,None,None,10.3)==0
backup=D/('respaldo_doble_dato_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));backup.mkdir()
for n in ['main.py','doble_dato.py',*keep]:
 if (D/n).exists():shutil.copy2(D/n,backup/n)
assert sha(D/'main.py')==expected
os.replace(S/'doble_dato.py',D/'doble_dato.py');os.replace(S/'main.py',D/'main.py')
for n,h in keep.items():assert sha(D/n)==h
result={n:sha(D/n) for n in ['main.py','doble_dato.py',*keep]};result['backup']=str(backup);(backup/'despliegue.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

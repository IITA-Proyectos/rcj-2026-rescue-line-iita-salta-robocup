from pathlib import Path
import ast,hashlib,json,os,py_compile,shutil,datetime
import numpy as np
D=Path('/home/iita/Desktop');S=D/'.verde_sombra_1';expected={'main.py':'eeb98adf876ff7fdc3545e22336fcd0576b3e7c16893a1f05d93726b8c4392cf','verde_oscuro.py':'1ee07fc3041add7146bd9ae38fd45741bbc9dbde998dde9acc61205695fce7c8'};keep={'rampa_transicion.py':'ed46092fd1854b5c3c5e6251f58ad8c059e3839d4fdff581efc832a47ca580d0','recuperacion_guard.py':'c3333b7e51f479cea041c656402438dc6a818f5d34ec4971f93ce0d910c9f52f'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for n,h in {**expected,**keep}.items():assert sha(D/n)==h,'Archivo cambiado: '+n
for n in expected:ast.parse((S/n).read_text());py_compile.compile(str(S/n),doraise=True)
ns={};exec(compile((S/'verde_oscuro.py').read_text(),'helper','exec'),ns)
lab=np.empty((120,160,3),np.uint8);lab[:]=[240,128,128];lab[80:,10:50]=[70,105,128];black=np.zeros((120,160),np.uint8);black[60:90,10:50]=255;black[90:,75:85]=255
assert ns['detectar_verde_sombra'](lab,black,np.array([120,90,110]),np.array([198,109,134]),200,1.)[0]==1
backup=D/('respaldo_verde_sombra_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'));backup.mkdir()
for n in {**expected,**keep}:shutil.copy2(D/n,backup/n)
for n,h in expected.items():assert sha(D/n)==h
for n in ['verde_oscuro.py','main.py']:os.replace(S/n,D/n)
for n,h in keep.items():assert sha(D/n)==h
result={n:sha(D/n) for n in {**expected,**keep}};result['backup']=str(backup);(backup/'despliegue.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

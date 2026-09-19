# -*- coding: utf-8 -*-
"""La integracion tiene que producir EXACTAMENTE el angulo del banco."""
import os, subprocess, sys, json
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__))

def por_banco(modo):
    """Angulos segun el banco, en un proceso limpio."""
    code = '''
import os,sys,importlib.util,numpy as np,cv2
AQUI=%r; sys.path.insert(0,AQUI)
import camino_principal as CP
v4,v2=CP.cargar(); SB=CP.hacer_sinbranch(v4)
cfg=dict(camino=%s,mono=%s); CP.instalar(v2,cfg)
cap=cv2.VideoCapture(os.path.join(AQUI,"hist.avi")); tr=SB(100.0/3.0); out=[]; i=0
while i<400:
    ok,fr=cap.read()
    if not ok: break
    r=tr.step(v2.frame_pi(fr)); t=r.get("target")
    out.append(None if t is None else round(float(np.clip(-90.0*(t[0]-v2.CENTER)/(v2.W/2.),-90,90)),6))
    i+=1
cap.release()
import json; print("JSON"+json.dumps(out))
''' % (AQUI, modo=="camino", modo=="camino")
    r=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True)
    for ln in r.stdout.splitlines():
        if ln.startswith("JSON"): return json.loads(ln[4:])
    print(r.stdout[-800:], r.stderr[-800:]); return None

def por_integracion(modo):
    code = '''
import os,sys,numpy as np,cv2
AQUI=%r; sys.path.insert(0,AQUI); os.environ["VISION_LINEA"]=%r
import vision_linea as V
cap=cv2.VideoCapture(os.path.join(AQUI,"hist.avi")); out=[]; i=0
while i<400:
    ok,fr=cap.read()
    if not ok: break
    g=cv2.resize(cv2.rotate(fr,cv2.ROTATE_180),(160,120),interpolation=cv2.INTER_NEAREST) \
        if not (fr.shape[0]==240 and fr.shape[1]>=640) else fr[:,:320][1::2,1::2]
    a=V.angulo(g)
    out.append(None if a is None else round(float(a),6)); i+=1
cap.release()
import json; print("JSON"+json.dumps(out))
''' % (AQUI, modo)
    r=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True)
    for ln in r.stdout.splitlines():
        if ln.startswith("JSON"): return json.loads(ln[4:])
    print(r.stdout[-800:], r.stderr[-800:]); return None

print("")
print("="*74)
print("  EQUIVALENCIA BANCO <-> INTEGRACION EN Main.py   (400 frames de hist)")
print("="*74)
ok_all=True
for modo in ("base","camino"):
    a=por_banco(modo); b=por_integracion(modo)
    if a is None or b is None:
        print("  %-8s *** no se pudo medir"%modo); ok_all=False; continue
    n=min(len(a),len(b))
    ig=sum(1 for x,y in zip(a[:n],b[:n]) if x==y)
    print("  %-8s %d/%d angulos identicos   %s"%(modo,ig,n,"OK" if ig==n else "*** DIFIEREN"))
    if ig!=n:
        ok_all=False
        for k,(x,y) in enumerate(zip(a[:n],b[:n])):
            if x!=y: print("      primer distinto f%d: banco %s  integracion %s"%(k,x,y)); break
print("")
print("  RESULTADO:", "INTEGRACION FIEL" if ok_all else "*** LA INTEGRACION NO REPRODUCE EL BANCO")
print("="*74)

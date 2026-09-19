# -*- coding: utf-8 -*-
"""Que velocidad emitiria de verdad sobre los videos. No valida trayectoria
-frenar cambia lo que la camara ve- pero si que el comando sea sano."""
import os,subprocess,sys,json
AQUI=os.path.dirname(os.path.abspath(__file__))
code='''
import os,sys,numpy as np,cv2
AQUI=%r; sys.path.insert(0,AQUI); os.environ["VISION_LINEA"]="camino"
import vision_linea as V, ab_v2_v3_v4 as AB
vels=[]; kap=[]
for vid in AB.AUTONOMOS:
    ru=os.path.join(AQUI,vid)
    if not os.path.exists(ru): continue
    cap=cv2.VideoCapture(ru)
    while True:
        ok,fr=cap.read()
        if not ok: break
        g=fr[:,:320][1::2,1::2] if (fr.shape[0]==240 and fr.shape[1]>=640) else \
          cv2.resize(cv2.rotate(fr,cv2.ROTATE_180),(160,120),interpolation=cv2.INTER_NEAREST)
        V.angulo(g)
        v=V.velocidad(40)
        vels.append(40 if v is None else v)
        u=V.ultimo().get("kappa")
        if u: kap.append(u)
    cap.release()
import json; print("JSON"+json.dumps({"v":vels,"k":kap}))
''' % AQUI
r=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True)
d=None
for ln in r.stdout.splitlines():
    if ln.startswith("JSON"): d=json.loads(ln[4:])
if d is None:
    print(r.stdout[-1500:]); print(r.stderr[-1500:]); sys.exit(1)
import numpy as np
v=np.array(d["v"])
print("")
print("="*76)
print("  QUE VELOCIDAD MANDARIA  (base 40, sobre %d frames)"%len(v))
print("="*76)
print("")
print("  velocidad plena (40)      %6d frames   %5.1f %%"%((v==40).sum(),100*(v==40).mean()))
print("  frenado                   %6d frames   %5.1f %%"%((v<40).sum(),100*(v<40).mean()))
print("  distribucion cuando frena: p50 %.0f  p25 %.0f  min %.0f"
      %(np.percentile(v[v<40],50) if (v<40).any() else 0,
        np.percentile(v[v<40],25) if (v<40).any() else 0, v.min()))
print("")
# oscilacion del comando de velocidad: cuantas veces cambia de valor
cambios=int((np.diff(v)!=0).sum())
print("  cambios de valor de speed  %d en %d frames = %.1f %% de los frames"
      %(cambios,len(v),100.0*cambios/len(v)))
print("  rango                      [%d, %d]"%(v.min(),v.max()))
print("")
print("  SANIDAD: nunca por debajo del piso (%d)  ->  %s"
      %(int(40*0.55), "OK" if v.min()>=int(40*0.55) else "*** FALLA"))
print("="*76)

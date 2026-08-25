# -*- coding: utf-8 -*-
"""Los controles positivos, son curvas de UN SOLO SENTIDO?

Si lo son, exigir cero inversiones de signo adentro es legitimo.
Si el robot hace una S, las inversiones son correctas y mi gate esta mal.

El yaw se mide por correlacion de fase sobre el fondo lejano: no depende de
ninguna vision candidata.
"""
import os, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__))
TRAMOS=[("hist_exito","hist.avi",580,679),("lineal_positivo","lineal.avi",800,872),
        ("hist_falla","hist.avi",1354,1490)]
GPP=60.0/320.0
for nom,vid,d,h in TRAMOS:
    ru=os.path.join(AQUI,vid)
    if not os.path.exists(ru): continue
    cap=cv2.VideoCapture(ru); prev=None; han=None; acum=[0.0]; i=0
    while True:
        ok,fr=cap.read()
        if not ok or i>h: break
        if i>=d-1:
            half=fr[:,:320] if fr.shape[1]>=640 else fr
            g=cv2.cvtColor(cv2.rotate(half,cv2.ROTATE_180),cv2.COLOR_BGR2GRAY)
            b=g[5:45,:].astype(np.float32)
            if han is None: han=np.hanning(b.shape[0])[:,None]*np.hanning(b.shape[1])[None,:]
            b=(b-b.mean())*han
            if prev is not None:
                (dx,_dy),resp=cv2.phaseCorrelate(prev,b)
                acum.append(acum[-1]+(-dx*GPP if resp>0.03 else 0.0))
            prev=b
        i+=1
    cap.release()
    a=np.array(acum)
    if len(a)<5: continue
    # giro neto y cuantas veces cambia de sentido la DERIVADA suavizada
    W=8
    der=np.array([a[min(k+W,len(a)-1)]-a[k] for k in range(len(a)-1)])
    sg=[1 if x>1.0 else (-1 if x<-1.0 else 0) for x in der]
    sg=[x for x in sg if x!=0]
    cambios=sum(1 for x,y in zip(sg,sg[1:]) if x!=y)
    print("  %-18s giro neto %+7.1f deg   |giro| bruto %6.1f   cambios de sentido: %d  -> %s"
          %(nom, a[-1]-a[0], np.abs(np.diff(a)).sum(), cambios,
            "UN SOLO SENTIDO" if cambios<=1 else "HACE S: las inversiones son legitimas"))

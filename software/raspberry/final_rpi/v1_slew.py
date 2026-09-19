# -*- coding: utf-8 -*-
"""V1 + limitador de velocidad de comando. A/B preregistrado sobre una banda."""
import importlib.util, math, os, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,AQUI)
import ab_v2_v3_v4 as AB
sp=importlib.util.spec_from_file_location("v1", os.path.join(AQUI,"airborne_v1_adaptado.py"))
V1=importlib.util.module_from_spec(sp); sp.loader.exec_module(V1)
FPS=100.0/3.0
# banda PREREGISTRADA de grados por segundo. 500 es lo que ya usa ControlPreview
# de nuevo_code_v3.py; se barre alrededor.
BANDA=[None, 1500, 1000, 700, 500, 350]

def serie(slew_dps, ruta, fps, desde=0, hasta=10**9):
    cap=cv2.VideoCapture(ruta); tr=V1.AirborneV1(fps); out=[]; i=0
    ang=0.0; maxd=None if slew_dps is None else slew_dps/fps
    while True:
        ok,fr=cap.read()
        if not ok or i>hasta: break
        r=tr.paso(V1.frame_de_la_pi(fr)); t=r.get("target"); a=r.get("angle_target")
        s=None if (t is None or a is None or not np.isfinite(a)) else float(a)
        if s is None:
            ang=0.0
        elif maxd is None:
            ang=s
        else:
            ang=ang+float(np.clip(s-ang,-maxd,maxd))
        if i>=desde:
            out.append((t, None if s is None else ang, r.get("estado")))
        i+=1
    cap.release(); return out

print("")
print("="*100)
print("  V1 + LIMITADOR DE VELOCIDAD DE COMANDO")
print("  banda preregistrada de grados/s. El target NO se toca: solo el comando.")
print("="*100)
print("")
print("  %-10s %9s %9s %9s %11s %10s %11s"%("slew","disp %","huecos","saltos>24","inversiones","suav","|ds| max"))
base=None
for sl in BANDA:
    tot=dict(n=0,con=0,huecos=0,s_gt=0,inv=0,suav=[]); dmax=0.0
    for vid in AB.AUTONOMOS:
        ru=os.path.join(AQUI,vid)
        if not os.path.exists(ru): continue
        S=serie(sl,ru,FPS); m=AB.metricas(S)
        for k in ("n","con","huecos","s_gt","inv"): tot[k]+=m[k]
        tot["suav"].append(m["suav"])
        st=[s for _t,s,_e in S if s is not None]
        for a,b in zip(st,st[1:]): dmax=max(dmax,abs(b-a))
    d=100.0*tot["con"]/max(tot["n"],1); sv=float(np.mean(tot["suav"]))
    if base is None: base=(d,tot["huecos"],tot["s_gt"],tot["inv"])
    print("  %-10s %9.2f %9d %9d %11d %10.2f %11.2f"
          %("sin" if sl is None else "%d d/s"%sl, d, tot["huecos"], tot["s_gt"], tot["inv"], sv, dmax))
print("")
print("  CONTROLES POSITIVOS")
for sl in BANDA:
    linea=[]; ok=True
    for cn,vid,fps,dd,hh,ex in AB.CONTROLES:
        ru=os.path.join(AQUI,vid)
        if not os.path.exists(ru) or not ex: continue
        S=serie(sl,ru,fps,dd,hh); m=AB.metricas(S)
        st=[s for _t,s,_e in S if s is not None]
        linea.append("%s %d/%d"%(cn,m["con"],ex)); ok&=(m["con"]>=ex)
        if cn=="lineal_positivo": linea.append("smax %+.0f"%(max(st) if st else 0))
    print("  %-10s %-8s %s"%("sin" if sl is None else "%d d/s"%sl,"PASA" if ok else "*** FALLA","   ".join(linea)))
print("="*100)

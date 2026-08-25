# -*- coding: utf-8 -*-
"""La metrica s_gt mide distancia EUCLIDEA del target. Pero steer depende SOLO
de la columna. Se recompara midiendo lo que de verdad llega a los motores."""
import importlib.util, math, os, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,AQUI)
import ab_v2_v3_v4 as AB
sp=importlib.util.spec_from_file_location("nuevo_code_v4", os.path.join(AQUI,"nuevo_code_v4.py"))
v4=importlib.util.module_from_spec(sp); sp.loader.exec_module(v4); v2=v4.v3.v2
sp1=importlib.util.spec_from_file_location("v1", os.path.join(AQUI,"airborne_v1_adaptado.py"))
V1=importlib.util.module_from_spec(sp1); sp1.loader.exec_module(V1)
class _N:
    def step(self,p,s): return p,"PASA"
class SB(v4.NuevoCodeV4):
    def __init__(self,f): v4.NuevoCodeV4.__init__(self,f); self.branch_guard=_N()

def serie(kind, ruta):
    cap=cv2.VideoCapture(ruta); out=[]
    tr = SB(100.0/3.0) if kind=="cand" else V1.AirborneV1(100.0/3.0)
    while True:
        ok,fr=cap.read()
        if not ok: break
        if kind=="cand":
            r=tr.step(v2.frame_pi(fr)); t=r.get("target")
            s=None if t is None else float(np.clip(-90.0*(t[0]-v2.CENTER)/(v2.W/2.0),-90,90))
        else:
            r=tr.paso(V1.frame_de_la_pi(fr)); t=r.get("target"); a=r.get("angle_target")
            s=None if (t is None or a is None or not np.isfinite(a)) else float(a)
        out.append((t,s))
    cap.release(); return out

print("")
print("="*94)
print("  LO QUE DE VERDAD LLEGA A LOS MOTORES")
print("  steer = -90*(x - centro)/(ancho/2)  ->  la FILA del target no entra")
print("="*94)
print("")
print("  %-12s %10s %10s %10s %12s %10s"%("version","salto EUCL","salto en X","salto STEER","|dsteer| p90","|dsteer| max"))
for kind,nom in (("cand","CANDIDATA"),("v1","V1")):
    eu=xx=st=0; ds=[]
    for vid in AB.AUTONOMOS:
        ru=os.path.join(AQUI,vid)
        if not os.path.exists(ru): continue
        S=serie(kind,ru); ult=None; ults=None
        for t,s in S:
            if t is None: ult=None; ults=None; continue
            if ult is not None:
                if math.hypot(t[0]-ult[0],t[1]-ult[1])>24: eu+=1
                if abs(t[0]-ult[0])>24: xx+=1
            if s is not None and ults is not None:
                d=abs(s-ults); ds.append(d)
                if d>27.0: st+=1        # 24 px de columna = 27 grados
            ult=t; ults=s if s is not None else ults
    ds=np.array(ds)
    print("  %-12s %10d %10d %10d %12.2f %10.2f"%(nom,eu,xx,st,np.percentile(ds,90),ds.max()))
print("")
print("  24 px de columna equivalen a 27 grados de steer (90/80 grados por px).")
print("="*94)

# -*- coding: utf-8 -*-
"""ARQUITECTURA MINIMA: V2 + guard espacial, SIN el branch guard de V3.
El A/B dijo que V3 cuesta +43 huecos y +26 frames sin autoridad para ganar 20
inversiones, y que sus saltos >24 px no bajan (+4). Si sacarlo no empeora nada,
la candidata minima es V2+spatial y V3 se elimina en vez de reemplazarse."""
import os, math, importlib.util, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,AQUI)
sp=importlib.util.spec_from_file_location("nuevo_code_v4", os.path.join(AQUI,"nuevo_code_v4.py"))
v4=importlib.util.module_from_spec(sp); sp.loader.exec_module(v4); v3=v4.v3; v2=v3.v2
from ab_v2_v3_v4 import metricas, AUTONOMOS, CONTROLES, FPS, fila, CAB

class SinBranch(v4.NuevoCodeV4):
    """V4 con el branch guard neutralizado: pasa el target sin tocarlo.
    NO se modifica ningun archivo; se sustituye el objeto."""
    class _Nulo(object):
        def step(self, proposed, skel):
            return proposed, "PASA"
    def __init__(self, fps):
        v4.NuevoCodeV4.__init__(self, fps)
        self.branch_guard = SinBranch._Nulo()

class SoloV2(object):
    """V2 crudo con el mismo envoltorio, para tenerlo en la misma tabla."""
    def __init__(self, fps): self.per=v2.NuevoCodeV2(fps)
    def step(self,g): return self.per.step(g)

def corrida(cls, ruta, fps, desde=0, hasta=10**9):
    cap=cv2.VideoCapture(ruta); tr=cls(fps); out=[]; i=0; off=0; nt=0
    W,C=v2.W,v2.CENTER
    while True:
        ok,fr=cap.read()
        if not ok or i>hasta: break
        g=v2.frame_pi(fr); r=tr.step(g)
        if i>=desde:
            t=r.get("target")
            s=None if t is None else float(np.clip(-90.0*(t[0]-C)/(W/2.0),-90,90))
            out.append((t,s,r.get("state")))
            if t is not None:
                nt+=1; sk=r.get("skel")
                x,y=int(round(t[0])),int(round(t[1]))
                if sk is None or not (0<=x<W and 0<=y<v2.H and sk[y,x]): off+=1
        i+=1
    cap.release(); return out,off,nt

VARIANTES=[("V2",SoloV2),("V4",v4.NuevoCodeV4),("V2+SP",SinBranch)]
print("")
print("  ARQUITECTURA MINIMA: V2 solo / V4 completo / V2+spatial sin branch")
print(CAB)
TOT={}
for et,cls in VARIANTES:
    t=dict(n=0,con=0,sin_aut=0,huecos=0,s_gt=0,inv=0,s_max=0.0,sp=[],su=[]); OFF=[0,0]
    for vid in AUTONOMOS:
        r=os.path.join(AQUI,vid)
        if not os.path.exists(r): continue
        ser,off,nt=corrida(cls,r,FPS); m=metricas(ser)
        OFF[0]+=off; OFF[1]+=nt
        for k in ("n","con","sin_aut","huecos","s_gt","inv"): t[k]+=m[k]
        t["s_max"]=max(t["s_max"],m["s_max"]); t["sp"].append(m["s_p90"]); t["su"].append(m["suav"])
    t["disp"]=100.0*t["con"]/max(t["n"],1); t["s_p90"]=float(np.mean(t["sp"])); t["suav"]=float(np.mean(t["su"]))
    t["off"]=100.0*OFF[0]/max(OFF[1],1)
    TOT[et]=t
    print(fila(et,t)+"   off-path %.2f %%"%t["off"])
print("")
print("  DIFERENCIA V2+SP CONTRA V4 COMPLETO")
a,b=TOT["V2+SP"],TOT["V4"]
for k,et in (("disp","disponibilidad %"),("sin_aut","frames sin autoridad"),
             ("huecos","huecos"),("s_gt","saltos >24 px"),("inv","inversiones")):
    d=a[k]-b[k]
    print("      %-24s V4 %8.2f   V2+SP %8.2f   %+8.2f"%(et,b[k],a[k],d))
print("")
print("  CONTROLES OBLIGATORIOS")
for et,cls in VARIANTES:
    linea=[]
    ok_all=True
    for nom,vid,fps,d,h,ex in CONTROLES:
        rr=os.path.join(AQUI,vid)
        if not os.path.exists(rr) or not ex: continue
        ser,_o,_n=corrida(cls,rr,fps,d,h); m=metricas(ser)
        linea.append("%s %d/%d"%(nom,m["con"],ex)); ok_all &= (m["con"]>=ex)
    print("      %-6s %s   %s"%(et,"PASA" if ok_all else "*** FALLA ***","  ".join(linea)))

# -*- coding: utf-8 -*-
"""TERCERA VARIANTE: devolver None (admitir que no sabe) PERO NO RESETEAR.
V4 original: rechaza -> None + reset() -> el frame siguiente entra SIN limite.
V4 sostiene: nunca None -> 26,2 % de targets fantasma fuera de la centerline.
Esta: None, pero la memoria del guard sobrevive, asi que al reenganchar el
limite SI se aplica. Una sola linea de diferencia con el original."""
import os, math, importlib.util, sys, collections
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,AQUI)
sp=importlib.util.spec_from_file_location("nuevo_code_v4", os.path.join(AQUI,"nuevo_code_v4.py"))
v4=importlib.util.module_from_spec(sp); sp.loader.exec_module(v4); v2=v4.v3.v2
from ab_v2_v3_v4 import metricas, AUTONOMOS, CONTROLES, FPS, fila, CAB

class GuardMemoria(v4.SpatialTargetGuard):
    """Identico al original salvo que NO llama a reset(). La memoria del ultimo
    target ACEPTADO sobrevive al rechazo, asi que el reenganche pasa por el
    limite en vez de entrar libre por REACQ_ACCEPT."""
    def step(self, proposed, skel):
        if proposed is None or skel is None:
            return None, "NO_TARGET", None            # sin reset()
        proposed=(float(proposed[0]), float(proposed[1]))
        if self.previous is None:
            self.previous=proposed
            return proposed, "REACQ_ACCEPT", None
        jump=math.hypot(proposed[0]-self.previous[0], proposed[1]-self.previous[1])
        if jump<=self.max_step:
            self.previous=proposed
            return proposed, "ACCEPT", jump
        ys,xs=np.nonzero(skel)
        if xs.size==0:
            return None, "NO_SKELETON", jump           # sin reset()
        dprev=np.sqrt((xs-self.previous[0])**2+(ys-self.previous[1])**2)
        reach=np.where(dprev<=self.max_step)[0]
        if reach.size==0:
            return None, "REACQ_PENDING", jump         # sin reset()
        dgoal=(xs[reach]-proposed[0])**2+(ys[reach]-proposed[1])**2
        j=reach[int(np.argmin(dgoal))]
        acc=(float(xs[j]), float(ys[j]))
        self.previous=acc
        return acc, "SPATIAL_LIMIT", jump

class V4Mem(v4.NuevoCodeV4):
    def __init__(self, fps):
        v4.NuevoCodeV4.__init__(self, fps)
        self.spatial_guard=GuardMemoria(fps)

def corrida(ruta, fps, desde=0, hasta=10**9, extra=False):
    cap=cv2.VideoCapture(ruta); tr=V4Mem(fps); out=[]; i=0; off=0; nt=0
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
    cap.release()
    return (out,off,nt) if extra else out

print("")
print("  V4-MEMORIA  (None pero sin reset; una linea de diferencia con V4)")
print(CAB)
tot=dict(n=0,con=0,sin_aut=0,huecos=0,s_gt=0,inv=0,s_max=0.0,sp=[],su=[]); OFF=[0,0]
for vid in AUTONOMOS:
    r=os.path.join(AQUI,vid)
    if not os.path.exists(r): continue
    ser,off,nt=corrida(r,FPS,extra=True); m=metricas(ser)
    OFF[0]+=off; OFF[1]+=nt
    print(fila("MEM",m)+"  "+vid.replace(".avi",""))
    for k in ("n","con","sin_aut","huecos","s_gt","inv"): tot[k]+=m[k]
    tot["s_max"]=max(tot["s_max"],m["s_max"]); tot["sp"].append(m["s_p90"]); tot["su"].append(m["suav"])
tot["disp"]=100.0*tot["con"]/max(tot["n"],1); tot["s_p90"]=float(np.mean(tot["sp"])); tot["suav"]=float(np.mean(tot["su"]))
print("")
print("  TOTAL"); print(CAB); print(fila("MEM",tot))
print("  target fuera de la centerline: %d de %d (%.2f %%)"%(OFF[0],OFF[1],100.0*OFF[0]/max(OFF[1],1)))
print("")
print("  CONTROLES")
for nom,vid,fps,d,h,ex in CONTROLES:
    rr=os.path.join(AQUI,vid)
    if not os.path.exists(rr): continue
    m=metricas(corrida(rr,fps,d,h))
    ok="" if not ex else ("  PASA" if m["con"]>=ex else "  *** FALLA ***")
    print("      %-16s n=%4d targets %4d  disp %6.2f %%  huecos %2d  >24px %2d  inv %2d%s"
          %(nom,m["n"],m["con"],m["disp"],m["huecos"],m["s_gt"],m["inv"],ok))

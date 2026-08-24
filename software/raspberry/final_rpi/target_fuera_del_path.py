# -*- coding: utf-8 -*-
"""La cruz no esta sobre la linea azul. Cuanto y por que."""
import importlib.util, math, os, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,AQUI)
sp=importlib.util.spec_from_file_location("nuevo_code_v4", os.path.join(AQUI,"nuevo_code_v4.py"))
v4=importlib.util.module_from_spec(sp); sp.loader.exec_module(v4); v2=v4.v3.v2
class _N:
    def step(self,p,s): return p,"PASA"
class SB(v4.NuevoCodeV4):
    def __init__(self,f): v4.NuevoCodeV4.__init__(self,f); self.branch_guard=_N()

def dmin(t, path):
    if t is None or not path: return None
    P=np.asarray(path,float)
    return float(np.min(np.hypot(P[:,0]-t[0], P[:,1]-t[1])))

print("=== CASO PUNTUAL: rumbo f637 ===")
cap=cv2.VideoCapture(os.path.join(AQUI,"rumbo.avi")); tr=SB(100.0/3.0)
for i in range(638):
    ok,fr=cap.read()
    if not ok: break
    r=tr.step(v2.frame_pi(fr))
    if i==637:
        t=r["target"]; p=r["path"]
        print("  start        ", r["start"])
        print("  target FINAL ", t, "  reason:", r.get("reason"), " spatial:", r.get("spatial_guard"))
        print("  target_geom  ", r.get("target_geometric"))
        print("  path: %d puntos, de %s a %s"%(len(p), p[0], p[-1]))
        print("  distancia del target FINAL al path: %.2f px"%dmin(t,p))
        print("  distancia del target GEOMETRICO al path: %.2f px"%dmin(r.get("target_geometric"),p))
cap.release()

print("")
print("=== SOBRE LOS 10 AUTONOMOS ===")
AUT=["hist.avi","lineal.avi","lineal70.avi","como_esta.avi","seguir.avi",
     "rumbo.avi","a.avi","roi_auto.avi","con_planner.avi","con_planner2.avi"]
D=[]; DG=[]; raz={}
for vid in AUT:
    ru=os.path.join(AQUI,vid)
    if not os.path.exists(ru): continue
    cap=cv2.VideoCapture(ru); tr=SB(100.0/3.0)
    while True:
        ok,fr=cap.read()
        if not ok: break
        r=tr.step(v2.frame_pi(fr))
        d=dmin(r.get("target"), r.get("path"))
        if d is None: continue
        D.append(d); DG.append(dmin(r.get("target_geometric"), r.get("path")) or 0.0)
        if d>2.0:
            k=(r.get("reason") or "-")+" | "+(r.get("spatial_guard") or "-")
            raz[k]=raz.get(k,0)+1
    cap.release()
D=np.array(D); DG=np.array(DG)
print("  frames con target y path: %d"%len(D))
print("")
print("  DISTANCIA DEL TARGET FINAL AL PATH DIBUJADO (px)")
print("    exactamente 0 (sobre el path)   %6d   %5.1f %%"%((D<1e-6).sum(),100*(D<1e-6).mean()))
print("    <= 1 px                         %6d   %5.1f %%"%((D<=1).sum(),100*(D<=1).mean()))
print("    >  2 px  (visiblemente afuera)  %6d   %5.1f %%"%((D>2).sum(),100*(D>2).mean()))
print("    >  5 px                         %6d   %5.1f %%"%((D>5).sum(),100*(D>5).mean()))
print("    > 10 px                         %6d   %5.1f %%"%((D>10).sum(),100*(D>10).mean()))
print("    p50 %.2f  p90 %.2f  p99 %.2f  max %.2f"%(np.percentile(D,50),np.percentile(D,90),np.percentile(D,99),D.max()))
print("")
print("  QUIEN LO SACA DEL PATH  (frames con desvio > 2 px)")
for k,c in sorted(raz.items(), key=lambda z:-z[1])[:8]:
    print("    %-46s %6d"%(k,c))

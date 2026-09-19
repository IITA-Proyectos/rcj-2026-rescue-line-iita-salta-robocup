# -*- coding: utf-8 -*-
"""V4 SIN RESET: una sola variable cambiada. NO se toca nuevo_code_v4.py.
El A/B mostro que V4 compra -89 saltos >24 px al precio de +200 huecos y +192
frames sin autoridad. La pregunta es si ese trade-off es NECESARIO o si lo causa
el `reset()` de nuevo_code_v4.py:75,97,108, que convierte un rechazo en un frame
sin orden y ademas desarma el limite para el frame siguiente.
Variante: cuando no hay punto alcanzable, en vez de devolver None SOSTENER el
target anterior. No inventa posicion: repite la ultima aceptada."""
import os, math, importlib.util, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,AQUI)
sp=importlib.util.spec_from_file_location("nuevo_code_v4", os.path.join(AQUI,"nuevo_code_v4.py"))
v4=importlib.util.module_from_spec(sp); sp.loader.exec_module(v4); v3=v4.v3; v2=v3.v2
from ab_v2_v3_v4 import metricas, correr, AUTONOMOS, CONTROLES, FPS, fila, CAB

class GuardSostiene(v4.SpatialTargetGuard):
    """Igual que el original salvo: no resetea y sostiene el ultimo target."""
    def step(self, proposed, skel):
        if proposed is None or skel is None:
            if self.previous is not None:
                return self.previous, "SOSTIENE_SIN_PROPUESTA", None
            return None, "NO_TARGET", None
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
            return self.previous, "SOSTIENE_SIN_SKELETON", jump
        dprev=np.sqrt((xs-self.previous[0])**2+(ys-self.previous[1])**2)
        reach=np.where(dprev<=self.max_step)[0]
        if reach.size==0:
            # ANTES: reset() + None. AHORA: sostiene.
            return self.previous, "SOSTIENE", jump
        dgoal=(xs[reach]-proposed[0])**2+(ys[reach]-proposed[1])**2
        j=reach[int(np.argmin(dgoal))]
        acc=(float(xs[j]), float(ys[j]))
        self.previous=acc
        return acc, "SPATIAL_LIMIT", jump

class V4SinReset(v4.NuevoCodeV4):
    def __init__(self, fps):
        v4.NuevoCodeV4.__init__(self, fps)
        self.spatial_guard=GuardSostiene(fps)

def corrida(ruta, fps, desde=0, hasta=10**9):
    cap=cv2.VideoCapture(ruta); tr=V4SinReset(fps); out=[]; i=0
    W,C=v2.W,v2.CENTER
    while True:
        ok,fr=cap.read()
        if not ok or i>hasta: break
        g=v2.frame_pi(fr); r=tr.step(g)
        if i>=desde:
            t=r.get("target")
            s=None if t is None else float(np.clip(-90.0*(t[0]-C)/(W/2.0),-90,90))
            out.append((t,s,r.get("state")))
        i+=1
    cap.release(); return out

print("")
print("  V4-SIN-RESET  (una sola variable: el guard sostiene en vez de resetear)")
print(CAB)
tot=dict(n=0,con=0,sin_aut=0,huecos=0,s_gt=0,inv=0,s_max=0.0,sp=[],su=[])
for vid in AUTONOMOS:
    r=os.path.join(AQUI,vid)
    if not os.path.exists(r): continue
    m=metricas(corrida(r,FPS))
    print(fila("SR",m).replace("SR  ","SR ")+"   "+vid.replace(".avi",""))
    for k in ("n","con","sin_aut","huecos","s_gt","inv"): tot[k]+=m[k]
    tot["s_max"]=max(tot["s_max"],m["s_max"]); tot["sp"].append(m["s_p90"]); tot["su"].append(m["suav"])
tot["disp"]=100.0*tot["con"]/max(tot["n"],1); tot["s_p90"]=float(np.mean(tot["sp"])); tot["suav"]=float(np.mean(tot["su"]))
print("")
print("  TOTAL")
print(CAB); print(fila("SR",tot))
print("")
print("  CONTROLES OBLIGATORIOS")
for nom,vid,fps,d,h,ex in CONTROLES:
    rr=os.path.join(AQUI,vid)
    if not os.path.exists(rr): continue
    m=metricas(corrida(rr,fps,d,h))
    ok="" if not ex else ("  PASA" if m["con"]>=ex else "  *** FALLA ***")
    print("      %-16s n=%4d  targets %4d  disp %6.2f %%  huecos %2d  >24px %2d  inv %2d%s"
          %(nom,m["n"],m["con"],m["disp"],m["huecos"],m["s_gt"],m["inv"],ok))

# ---------------------------------------------------------------------------
#  BUSCAR EL CONTRAEJEMPLO. "0 huecos" y "0 saltos >24" son TAUTOLOGICOS:
#  el guard limita a 24 px por construccion y ahora nunca devuelve None.
#  Lo que NO es tautologico y decide si esto sirve:
#    A  cuantos frames seguidos SOSTIENE un target viejo
#    B  el target sostenido, sigue estando sobre la centerline?
#  Si sostiene 200 frames o si el target queda fuera de la linea, la mejora es
#  cosmetica y peor que el hueco.
# ---------------------------------------------------------------------------
print("")
print("  CONTRAEJEMPLO: cuanto sostiene, y sigue sobre la linea?")
print("  %-14s %7s %8s %8s %8s %9s %9s"
      % ("video","frames","rachas","p50","p90","MAX","off-path %"))
import collections
TOT=collections.Counter(); rachas_all=[]; off_all=[0,0]
for vid in AUTONOMOS:
    r=os.path.join(AQUI,vid)
    if not os.path.exists(r): continue
    cap=cv2.VideoCapture(r); tr=V4SinReset(FPS); i=0
    racha=0; rr=[]; off=0; n_t=0
    while True:
        ok,fr=cap.read()
        if not ok: break
        g=v2.frame_pi(fr); res=tr.step(g)
        sg=res.get("spatial_guard","")
        if sg.startswith("SOSTIENE"):
            racha+=1
        else:
            if racha: rr.append(racha)
            racha=0
        t=res.get("target"); sk=res.get("skel")
        if t is not None:
            n_t+=1
            if sk is not None:
                x,y=int(round(t[0])),int(round(t[1]))
                if not (0<=x<v2.W and 0<=y<v2.H and sk[y,x]): off+=1
            else:
                off+=1
        i+=1
    if racha: rr.append(racha)
    cap.release()
    rachas_all+=rr; off_all[0]+=off; off_all[1]+=n_t
    a=np.array(rr) if rr else np.array([0])
    print("  %-14s %7d %8d %8.0f %8.0f %9d %8.1f %%"
          %(vid.replace(".avi",""),i,len(rr),np.median(a),np.percentile(a,90),a.max(),
            100.0*off/max(n_t,1)))
a=np.array(rachas_all) if rachas_all else np.array([0])
print("")
print("  TOTAL: %d rachas de sostenimiento; p50 %.0f  p90 %.0f  MAX %d frames (%.0f ms)"
      %(len(a),np.median(a),np.percentile(a,90),a.max(),1000.0*a.max()/FPS))
print("  frames sostenidos en total: %d de 13900 (%.1f %%)"%(a.sum(),100.0*a.sum()/13900))
print("  TARGET FUERA DE LA CENTERLINE: %d de %d (%.2f %%)"
      %(off_all[0],off_all[1],100.0*off_all[0]/max(off_all[1],1)))
print("")
print("  (en V4 original off_path es tautologicamente 0 porque el guard elige")
print("   entre pixeles del skeleton; aca SI puede fallar, y por eso mide algo)")

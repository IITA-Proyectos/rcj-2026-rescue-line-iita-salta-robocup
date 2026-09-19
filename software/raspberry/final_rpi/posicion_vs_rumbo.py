# -*- coding: utf-8 -*-
"""C) LA VISION MEZCLA POSICION Y RUMBO.

El equipo ya habia anotado esto el 2026-08-23 y despues la investigacion se fue
a H9/H10. Aca se mide.

    steer = -90 * (x_target - CENTRO) / (W/2)

x_target se corre por DOS causas fisicamente distintas:

  e_lat   el robot esta corrido de la linea            -> error de POSICION
  psi     la linea DOBLA adelante                      -> error de RUMBO

Un seguidor de trayectoria serio los trata por separado y con ganancias
distintas (Stanley: delta = psi + atan(k*e/v)). Aca los dos entran por el mismo
numero y con la misma ganancia. Si domina el rumbo, el robot corrige como si
estuviera corrido cuando en realidad esta centrado y la pista dobla.
"""
import importlib.util, os, sys
import numpy as np, cv2
AQUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, AQUI)
sp = importlib.util.spec_from_file_location("nuevo_code_v4", os.path.join(AQUI,"nuevo_code_v4.py"))
v4 = importlib.util.module_from_spec(sp); sp.loader.exec_module(v4); v2 = v4.v3.v2
class _N:
    def step(self,p,s): return p,"PASA"
class SB(v4.NuevoCodeV4):
    def __init__(self,f): v4.NuevoCodeV4.__init__(self,f); self.branch_guard=_N()
AUT=["hist.avi","lineal.avi","lineal70.avi","como_esta.avi","seguir.avi",
     "rumbo.avi","a.avi","roi_auto.avi","con_planner.avi","con_planner2.avi"]
E=[];P=[];S=[]
for vid in AUT:
    r_=os.path.join(AQUI,vid)
    if not os.path.exists(r_): continue
    cap=cv2.VideoCapture(r_); tr=SB(100.0/3.0)
    while True:
        ok,fr=cap.read()
        if not ok: break
        r=tr.step(v2.frame_pi(fr))
        t=r.get("target"); st=r.get("start"); h=r.get("heading")
        if t is None or st is None or h is None: continue
        E.append(st[0]-v2.CENTER); P.append(h)
        S.append(float(np.clip(-90.0*(t[0]-v2.CENTER)/(v2.W/2.0),-90,90)))
E=np.array(E);P=np.array(P);S=np.array(S);n=len(S)
print("");print("="*100)
print("  C) LA VISION MEZCLA POSICION Y RUMBO   (n=%d frames)"%n)
print("="*100);print("")
print("  e_lat = columna de ENTRADA menos el centro   -> error de POSICION (px)")
print("  psi   = rumbo de la centerline en el start   -> error de RUMBO (grados)")
print("  steer = comando que sale                     -> grados")
print("")
print("  correlacion de steer con e_lat   %+.3f"%np.corrcoef(S,E)[0,1])
print("  correlacion de steer con psi     %+.3f"%np.corrcoef(S,P)[0,1])
A=np.column_stack([E,P,np.ones(n)])
c,_,_,_=np.linalg.lstsq(A,S,rcond=None)
pred=A@c; r2=1-((S-pred)**2).sum()/((S-S.mean())**2).sum()
print("  regresion  steer = %+.3f*e_lat %+.3f*psi %+.2f     R2 = %.3f"%(c[0],c[1],c[2],r2))
sE=np.std(E)*abs(c[0]); sP=np.std(P)*abs(c[1])
print("  contribucion a la varianza:  posicion %.1f %%   rumbo %.1f %%"
      %(100*sE/(sE+sP),100*sP/(sE+sP)))
print("")
m=np.abs(E)<3.0
print("  ROBOT CENTRADO  (|e_lat| < 3 px):  %d frames (%.1f %%)"%(m.sum(),100*m.mean()))
print("    |steer| que pide igual:  p50 %.1f   p90 %.1f   max %.1f grados"
      %(np.percentile(np.abs(S[m]),50),np.percentile(np.abs(S[m]),90),np.abs(S[m]).max()))
print("    -> con el robot SOBRE la linea, el comando lo genera la CURVATURA")
q=np.abs(P)<5.0
print("")
print("  LINEA RECTA ADELANTE  (|psi| < 5 grados):  %d frames (%.1f %%)"%(q.sum(),100*q.mean()))
print("    |steer|:  p50 %.1f   p90 %.1f   max %.1f grados"
      %(np.percentile(np.abs(S[q]),50),np.percentile(np.abs(S[q]),90),np.abs(S[q]).max()))
print("")
gr=np.abs(S)>45.0
print("  COMANDOS FUERTES  (|steer| > 45 grados): %d frames (%.1f %%)"%(gr.sum(),100*gr.mean()))
print("    de esos, con el robot CENTRADO (|e_lat|<5 px):  %d  (%.1f %%)"
      %((gr&(np.abs(E)<5)).sum(),100*(gr&(np.abs(E)<5)).sum()/max(gr.sum(),1)))
print("    o sea: giros fuertes pedidos SIN error de posicion.")
print("="*100)

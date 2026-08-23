# -*- coding: utf-8 -*-
"""Distribucion de LONGITUD DE RAMA del esqueleto. Decide si la poda es segura.
La literatura de skeleton pruning (DSE, Latecki PAMI 2007; barbs por umbral de
longitud aguas abajo, arXiv 2010.14440) usa la LONGITUD de la rama como
discriminante entre ruido y topologia real. Si en nuestros esqueletos la
distribucion es bimodal, la poda separa; si es continua, podar es adivinar.

RESULTADO: NO es bimodal. Continua de 0 a 362 px, con 41,2 % de las ramas por
encima de 64 px y sin ningun valle. No existe un umbral natural, asi que podar
por longitud es elegir un numero a mano. H7 queda comprometida antes de
escribir una sola linea de la poda.

Es lo que pide el protocolo del issue #138: una tecnica externa -DSE, Latecki
PAMI 2007; poda de barbs por longitud aguas abajo, arXiv 2010.14440- se
convirtio en hipotesis falsable contra nuestros datos y NO entro por parecido.
"""
import os, math, importlib.util, collections
import numpy as np, cv2
AQUI = os.path.dirname(os.path.abspath(__file__))
sp=importlib.util.spec_from_file_location("nuevo_code_v4", os.path.join(AQUI,"nuevo_code_v4.py"))
v4=importlib.util.module_from_spec(sp); sp.loader.exec_module(v4); v2=v4.v3.v2
AUT=["hist.avi","lineal.avi","lineal70.avi","como_esta.avi","seguir.avi",
     "rumbo.avi","a.avi","roi_auto.avi","con_planner.avi","con_planner2.avi"]

def ramas(sk):
    """Largo geodesico de cada hoja hasta la bifurcacion mas cercana."""
    pts,adj,deg=v2.graph_from_skeleton(sk)
    if len(pts)<3: return []
    hojas=[i for i in range(len(pts)) if deg[i]==1]
    bif=set(i for i in range(len(pts)) if deg[i]>=3)
    out=[]
    for h in hojas:
        # caminar desde la hoja hasta encontrar una bifurcacion o agotar
        prev=-1; cur=h; L=0.0; pasos=0
        while pasos<400:
            vec=[(j,w) for j,w in adj[cur] if j!=prev]
            if len(vec)!=1: break
            j,w=vec[0]; L+=w; prev=cur; cur=j; pasos+=1
            if cur in bif: break
        out.append(L)
    return out

todo=[]
for vid in AUT:
    r=os.path.join(AQUI,vid)
    if not os.path.exists(r): continue
    cap=cv2.VideoCapture(r); tr=v4.NuevoCodeV4(100.0/3.0); n=0
    while True:
        ok,fr=cap.read()
        if not ok: break
        g=v2.frame_pi(fr); res=tr.step(g)
        comp=res.get("comp")
        if comp is not None:
            from skimage.morphology import skeletonize
            sk=skeletonize(comp>0)
            todo+=ramas(sk)
        n+=1
    cap.release()
a=np.array([x for x in todo if x>0])
print("")
print("  LONGITUD DE RAMA (hoja -> bifurcacion), %d ramas en 10 videos autonomos"%len(a))
print("  p10 %.1f  p25 %.1f  p50 %.1f  p75 %.1f  p90 %.1f  MAX %.1f px"
      %(np.percentile(a,10),np.percentile(a,25),np.median(a),np.percentile(a,75),np.percentile(a,90),a.max()))
print("")
print("  HISTOGRAMA  (si es bimodal, la poda por umbral separa ruido de topologia)")
bordes=[0,2,4,6,8,12,16,24,32,48,64,1e9]
tot=len(a)
for lo,hi in zip(bordes,bordes[1:]):
    n=((a>=lo)&(a<hi)).sum()
    if n==0: continue
    barra="#"*int(60.0*n/tot)
    print("      %5.0f-%-6s %7d %5.1f %% %s"%(lo,("%.0f"%hi) if hi<1e9 else "inf",n,100.0*n/tot,barra))
print("")
for u in (4,6,8,10,12,16):
    print("      con umbral %2d px se podarian %6d ramas (%.1f %%)"%(u,(a<u).sum(),100.0*(a<u).mean()))

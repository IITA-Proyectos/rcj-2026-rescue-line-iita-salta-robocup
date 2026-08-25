# -*- coding: utf-8 -*-
"""LA ESTRELLA. El esqueleto de una mancha ANCHA no es una linea: es una arania.

Benjamin, mirando el video: "toma un ruido de ahi y queda como una estrella y
elige un camino erroneo".

H6/H6b preguntaron si las ramas eran ruido de MASCARA y las refutaron: son
reales. Nadie pregunto si son ramas del EJE MEDIAL de una mancha ancha, que es
otra cosa y no se arregla con la mascara: es intrinseco a skeletonize.

Una linea limpia tiene 2 extremos (grado 1) y 0 bifurcaciones (grado >=3).
Una estrella tiene muchos de los dos.
"""
import importlib.util, math, os, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,AQUI)
import ab_v2_v3_v4 as AB
sp=importlib.util.spec_from_file_location("nuevo_code_v4",os.path.join(AQUI,"nuevo_code_v4.py"))
v4=importlib.util.module_from_spec(sp); sp.loader.exec_module(v4); v2=v4.v3.v2
class _N:
    def step(self,p,s): return p,"PASA"
class SB(v4.NuevoCodeV4):
    def __init__(self,f): v4.NuevoCodeV4.__init__(self,f); self.branch_guard=_N()

def grados(sk):
    s=(sk>0).astype(np.uint8)
    k=np.ones((3,3),np.uint8); k[1,1]=0
    vec=cv2.filter2D(s,-1,k,borderType=cv2.BORDER_CONSTANT)
    ext=int(((s==1)&(vec==1)).sum())
    bif=int(((s==1)&(vec>=3)).sum())
    return ext,bif,int(s.sum())

EXT=[];BIF=[];ANCHO=[];N=0
por_ancho={}
for vid in AB.AUTONOMOS:
    ru=os.path.join(AQUI,vid)
    if not os.path.exists(ru): continue
    cap=cv2.VideoCapture(ru); tr=SB(100.0/3.0)
    while True:
        ok,fr=cap.read()
        if not ok: break
        r=tr.step(v2.frame_pi(fr))
        sk=r.get("skel"); comp=r.get("comp")
        if sk is None or comp is None: continue
        e,b,n=grados(sk)
        if n<5: continue
        ys,xs=np.nonzero(comp>0)
        if not len(xs): continue
        # ancho tipico de la mancha: mediana del ancho por fila ocupada
        anchos=[]
        for y in np.unique(ys)[::3]:
            xr=xs[ys==y]
            if len(xr): anchos.append(xr.max()-xr.min()+1)
        w=float(np.median(anchos)) if anchos else 0.0
        EXT.append(e); BIF.append(b); ANCHO.append(w); N+=1
        k=min(int(w//10)*10,80)
        por_ancho.setdefault(k,[]).append((e,b))
EXT=np.array(EXT);BIF=np.array(BIF);ANCHO=np.array(ANCHO)
print("")
print("="*86)
print("  LA ESTRELLA: topologia del esqueleto  (n = %d frames)"%N)
print("  Una linea limpia = 2 extremos, 0 bifurcaciones.")
print("="*86)
print("")
print("  EXTREMOS (grado 1)      p50 %d   p90 %d   max %d"%(np.percentile(EXT,50),np.percentile(EXT,90),EXT.max()))
print("  BIFURCACIONES (>=3)     p50 %d   p90 %d   max %d"%(np.percentile(BIF,50),np.percentile(BIF,90),BIF.max()))
print("")
print("  frames con exactamente 2 extremos (linea limpia):  %5d  %5.1f %%"%((EXT==2).sum(),100*(EXT==2).mean()))
print("  frames con 3 o mas extremos:                       %5d  %5.1f %%"%((EXT>=3).sum(),100*(EXT>=3).mean()))
print("  frames con 5 o mas extremos (estrella):            %5d  %5.1f %%"%((EXT>=5).sum(),100*(EXT>=5).mean()))
print("  frames con alguna bifurcacion:                     %5d  %5.1f %%"%((BIF>0).sum(),100*(BIF>0).mean()))
print("")
print("  ANCHO DE LA MANCHA contra TOPOLOGIA DEL ESQUELETO")
print("  %-14s %8s %12s %12s %12s"%("ancho mediano","frames","extremos p50","bifurc p50","% con >=5 ext"))
for k in sorted(por_ancho):
    v=np.array(por_ancho[k])
    print("  %-14s %8d %12.0f %12.0f %11.1f %%"
          %("%d-%d px"%(k,k+9),len(v),np.percentile(v[:,0],50),np.percentile(v[:,1],50),100*(v[:,0]>=5).mean()))
print("")
c=np.corrcoef(ANCHO,EXT)[0,1]
print("  correlacion ancho de mancha <-> numero de extremos:  %+.3f"%c)
print("")
print("  LECTURA: si los extremos crecen con el ancho, la estrella NO es ruido")
print("  de mascara -eso ya lo refuto H6b-: es el eje medial de una mancha")
print("  ancha, y es intrinseco a skeletonize. No se arregla con morfologia.")
print("="*86)

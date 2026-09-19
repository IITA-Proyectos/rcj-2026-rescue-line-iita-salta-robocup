# -*- coding: utf-8 -*-
"""De donde salen los 928 saltos >24 px de V1. Atribucion por rama de POI."""
import importlib.util, math, os, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,AQUI)
import ab_v2_v3_v4 as AB
sp=importlib.util.spec_from_file_location("v1", os.path.join(AQUI,"airborne_v1_adaptado.py"))
v1=importlib.util.module_from_spec(sp); sp.loader.exec_module(v1)

trans={}; por_rama={}; saltos=[]; total=0; conteo_rama={}
dx_only=0; dy_grande=0
for vid in AB.AUTONOMOS:
    r_=os.path.join(AQUI,vid)
    if not os.path.exists(r_): continue
    cap=cv2.VideoCapture(r_); tr=v1.AirborneV1(100.0/3.0)
    ult=None; ult_m=None
    while True:
        ok,fr=cap.read()
        if not ok: break
        r=tr.paso(v1.frame_de_la_pi(fr))
        t=r.get("target"); m=r.get("motivo_target")
        if t is None: ult=None; ult_m=None; continue
        conteo_rama[m]=conteo_rama.get(m,0)+1
        if ult is not None:
            d=math.hypot(t[0]-ult[0], t[1]-ult[1])
            total+=1
            if d>24.0:
                saltos.append(d)
                k=(ult_m,m)
                trans[k]=trans.get(k,0)+1
                por_rama[m]=por_rama.get(m,0)+1
                if abs(t[1]-ult[1])>24: dy_grande+=1
                elif abs(t[0]-ult[0])>24: dx_only+=1
        ult=t; ult_m=m
    cap.release()

S=np.array(saltos)
print("")
print("="*88)
print("  DE DONDE SALEN LOS SALTOS >24 px DE V1")
print("="*88)
print("")
print("  saltos: %d sobre %d transiciones con target (%.1f %%)"%(len(S),total,100*len(S)/max(total,1)))
print("  magnitud: p50 %.1f  p90 %.1f  max %.1f px"%(np.percentile(S,50),np.percentile(S,90),S.max()))
print("  por eje: %d son salto de FILA (>24 en y), %d solo de COLUMNA"%(dy_grande,dx_only))
print("")
print("  RAMA A LA QUE SE LLEGA cuando hay salto")
for k,c in sorted(por_rama.items(), key=lambda z:-z[1]):
    base=conteo_rama.get(k,0)
    print("    %-32s %5d saltos   de %5d frames en esa rama = %5.1f %%"%(k,c,base,100.0*c/max(base,1)))
print("")
print("  TRANSICIONES QUE MAS SALTOS PRODUCEN")
for (a,b),c in sorted(trans.items(), key=lambda z:-z[1])[:12]:
    print("    %-30s -> %-30s %5d"%(a,b,c))
print("")
print("  CUANTAS VECES SE USA CADA RAMA EN TOTAL")
for k,c in sorted(conteo_rama.items(), key=lambda z:-z[1]):
    print("    %-32s %6d  (%5.1f %%)"%(k,c,100.0*c/max(sum(conteo_rama.values()),1)))
print("="*88)

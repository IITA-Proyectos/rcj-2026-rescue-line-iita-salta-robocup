# -*- coding: utf-8 -*-
"""BASE contra CAMINO+MONO. Se ve el esqueleto entero en ambar oscuro y el
CAMINO PRINCIPAL encima en verde brillante: es la diferencia entre la estrella
y la linea."""
import argparse, importlib.util, math, os, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,AQUI)
import ab_v2_v3_v4 as AB, camino_principal as CP
FPS=100.0/3.0; E=4; FT=cv2.FONT_HERSHEY_SIMPLEX
AVISO="OPEN-LOOP REPLAY - NOT PHYSICAL/CLOSED-LOOP PROOF"
C_BASE=(0,120,255); C_NEW=(120,255,120)
TRAMOS=[("hist.avi",1354,1470,"la falla historica"),
        ("seguir.avi",1160,1205,"el enganche en la cinta ya recorrida"),
        ("rumbo.avi",620,700,"curva con recodo: aca aparece la estrella"),
        ("hist.avi",580,660,"CONTROL hist_exito: 100/100 en las dos"),
        ("lineal.avi",800,872,"CONTROL lineal_positivo: el +89 intacto")]

def txt(i,x,y,s,c=(210,210,210),e=.5,g=1): cv2.putText(i,s,(x,y),FT,e,c,g,cv2.LINE_AA)

def panel(v2,r,col,etq,cadena=None,pts=None):
    vis=np.zeros((v2.H,v2.W,3),np.uint8)
    if r.get("mask") is not None: vis[r["mask"]>0]=(45,45,45)
    if r.get("comp") is not None: vis[r["comp"]>0]=(35,95,35)
    if r.get("skel") is not None: vis[r["skel"]>0]=(0,95,120)      # ambar oscuro
    if cadena and pts is not None:
        for i in cadena:
            y,x=pts[i]
            if 0<=x<v2.W and 0<=y<v2.H: vis[y,x]=(120,255,120)     # camino principal
    if r.get("path"):
        q=np.asarray([(int(round(x)),int(round(y))) for x,y in r["path"]],np.int32)
        if len(q)>=2: cv2.polylines(vis,[q],False,(255,170,60),1)
    big=cv2.resize(vis,(v2.W*E,v2.H*E),interpolation=cv2.INTER_NEAREST)
    cv2.line(big,(int(round(v2.CENTER))*E,0),(int(round(v2.CENTER))*E,v2.H*E-1),(95,95,95),1)
    t=r.get("target")
    if t is not None:
        cv2.drawMarker(big,(int(t[0]*E+E//2),int(t[1]*E+E//2)),col,cv2.MARKER_TILTED_CROSS,8*E,2)
    cv2.rectangle(big,(0,0),(v2.W*E,28),(0,0,0),-1); txt(big,8,20,etq,col,.6,2)
    return big

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--salida",default="REGISTRO_CAMINO.mp4"); a=ap.parse_args()
    v4,v2=CP.cargar(); SB=CP.hacer_sinbranch(v4)
    W,H=v2.W*E*2, v2.H*E+170
    vw=cv2.VideoWriter(os.path.join(AQUI,a.salida),cv2.VideoWriter_fourcc(*"mp4v"),FPS,(W,H)); n=0
    def placa(lin,seg):
        img=np.zeros((H,W,3),np.uint8); y=int(H*.24)
        for s,e,g,c in lin:
            (tw,_),_=cv2.getTextSize(s,FT,e,g); txt(img,(W-tw)//2,y,s,c,e,g); y+=int(38*e+24)
        txt(img,W-460,H-12,AVISO,(110,110,110),.45); return [img]*int(round(seg*FPS))
    for f in placa([("EL ESQUELETO TIENE QUE SER UNA LINEA",1.05,3,(255,255,255)),
                    ("no una estrella",.8,2,(200,200,200)),
                    ("3+ extremos en el 55,7 % de los frames (13.242 medidos)",.6,1,(0,165,255)),
                    ("verde brillante = CAMINO PRINCIPAL, la cadena start -> nodo mas lejano",.58,1,(120,255,120)),
                    ("ambar oscuro = el resto del esqueleto, las costillas que se descartan",.58,1,(0,150,190)),
                    ("CAMINO+MONO mejora LAS CINCO metricas y no rompe ningun control",.68,2,(120,255,120))],6.0):
        vw.write(f); n+=1
    cfg={"camino":False,"mono":False}
    CP.instalar(v2,cfg)
    for vid,d,h,nota in TRAMOS:
        ru=os.path.join(AQUI,vid)
        if not os.path.exists(ru): continue
        for f in placa([("%s   f%d-%d"%(vid.replace(".avi",""),d,h),1.0,2,(90,230,255)),
                        (nota,.62,1,(200,200,200))],0.9):
            vw.write(f); n+=1
        cap=cv2.VideoCapture(ru); tb=SB(FPS); tn=SB(FPS); i=0
        while True:
            ok,fr=cap.read()
            if not ok or i>h: break
            g=v2.frame_pi(fr)
            cfg["camino"]=False; cfg["mono"]=False; rb=tb.step(g)
            cfg["camino"]=True; cfg["mono"]=True; rn=tn.step(g)
            cad=None; pts=None
            if "dist" in CP.CAP:
                pts=CP.CAP["pts"]; dist=CP.CAP["dist"]; prev=CP.CAP["prev"]; si=CP.CAP["si"]
                fin=np.where(np.isfinite(dist))[0]
                if len(fin):
                    F=int(fin[int(np.argmax(dist[fin]))])
                    cad=v2.reconstruct(prev,si,F) or None
            cfg["camino"]=False; cfg["mono"]=False
            if i>=d:
                out=np.zeros((H,W,3),np.uint8); w=v2.W*E
                out[:v2.H*E,:w]=panel(v2,rb,C_BASE,"BASE  esqueleto entero")
                out[:v2.H*E,w:2*w]=panel(v2,rn,C_NEW,"CAMINO+MONO",cad,pts)
                y0=v2.H*E+32
                txt(out,12,y0,"%s   f%d"%(vid.replace(".avi",""),i),(90,230,255),.85,2)
                tb_,tn_=rb.get("target"),rn.get("target")
                sb=None if tb_ is None else float(np.clip(-90.0*(tb_[0]-v2.CENTER)/(v2.W/2.),-90,90))
                sn=None if tn_ is None else float(np.clip(-90.0*(tn_[0]-v2.CENTER)/(v2.W/2.),-90,90))
                if tb_ is None: txt(out,430,y0,"BASE SIN TARGET",(120,120,255),.7,2)
                txt(out,12,y0+38,"BASE         target %s   steer %s   [%s]"
                    %("--" if tb_ is None else "(%3.0f,%3.0f)"%tb_,"--" if sb is None else "%+6.1f"%sb,rb.get("state","")),C_BASE,.58,2)
                txt(out,12,y0+70,"CAMINO+MONO  target %s   steer %s   [%s]"
                    %("--" if tn_ is None else "(%3.0f,%3.0f)"%tn_,"--" if sn is None else "%+6.1f"%sn,rn.get("state","")),C_NEW,.58,2)
                if tb_ is not None and tn_ is not None and (abs(tb_[0]-tn_[0])>0.5 or abs(tb_[1]-tn_[1])>0.5):
                    txt(out,700,y0+70,"ELIGEN DISTINTO",(255,255,255),.6,2)
                txt(out,12,y0+102,"verde brillante = camino principal   ambar = costillas descartadas",(140,140,140),.5)
                txt(out,W-460,H-12,AVISO,(110,110,110),.45)
                vw.write(out); n+=1
            i+=1
        cap.release()
    vw.release(); p=os.path.join(AQUI,a.salida)
    print("  %s  %d frames  %.1f s  %.1f MB"%(a.salida,n,n/FPS,os.path.getsize(p)/1e6))

if __name__=="__main__":
    main()

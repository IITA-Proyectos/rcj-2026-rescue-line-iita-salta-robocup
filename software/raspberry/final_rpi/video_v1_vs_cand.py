# -*- coding: utf-8 -*-
"""CANDIDATA (skeleton+Dijkstra) contra V1 (POI, la de los campeones), lado a lado.

Las dos ven exactamente los mismos frames. Replay OPEN-LOOP: muestra que ELIGE
cada una, no que trayectoria haria.
"""
import argparse, importlib.util, os, sys
import numpy as np, cv2
AQUI=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,AQUI)
import ab_v2_v3_v4 as AB
FPS=100.0/3.0; E=3; FT=cv2.FONT_HERSHEY_SIMPLEX
AVISO="OPEN-LOOP REPLAY - NOT PHYSICAL/CLOSED-LOOP PROOF"
C_MASK,C_COMP,C_SKEL,C_PATH=(45,45,45),(35,95,35),(0,150,190),(255,170,60)
C_CAND,C_V1=(0,120,255),(120,255,120)
C_EST={"HIGH":(70,220,70),"MEDIUM":(80,210,220),"LOW":(0,160,255),
       "LOW_FORWARD":(0,190,255),"SIN_CERCA":(255,180,60),"PERDIDA":(80,80,255)}
TRAMOS=[("hist.avi",1354,1490,"la falla historica"),
        ("hist.avi",580,679,"CONTROL: hist_exito, 100/100 en las dos"),
        ("lineal.avi",795,875,"CONTROL: el +87 correcto, no se puede romper"),
        ("seguir.avi",1160,1210,"donde la candidata se engancha en la cinta ya recorrida"),
        ("rumbo.avi",600,700,"curva"),("como_esta.avi",300,420,"tramo con huecos")]

def cargar():
    sp=importlib.util.spec_from_file_location("nuevo_code_v4",os.path.join(AQUI,"nuevo_code_v4.py"))
    v4=importlib.util.module_from_spec(sp); sp.loader.exec_module(v4)
    s1=importlib.util.spec_from_file_location("v1",os.path.join(AQUI,"airborne_v1_adaptado.py"))
    v1=importlib.util.module_from_spec(s1); s1.loader.exec_module(v1)
    return v4, v4.v3.v2, v1

def txt(i,x,y,s,c=(210,210,210),e=.5,g=1): cv2.putText(i,s,(x,y),FT,e,c,g,cv2.LINE_AA)

def panel_cand(v2,r):
    vis=np.zeros((v2.H,v2.W,3),np.uint8)
    if r.get("mask") is not None: vis[r["mask"]>0]=C_MASK
    if r.get("comp") is not None: vis[r["comp"]>0]=C_COMP
    if r.get("skel") is not None: vis[r["skel"]>0]=C_SKEL
    if r.get("path"):
        q=np.asarray([(int(round(x)),int(round(y))) for x,y in r["path"]],np.int32)
        if len(q)>=2: cv2.polylines(vis,[q],False,C_PATH,1)
    return vis

def panel_v1(v1m,r):
    vis=np.zeros((v1m.H,v1m.W,3),np.uint8)
    if r.get("mask") is not None: vis[r["mask"]>0]=C_MASK
    if r.get("contour") is not None:
        cv2.drawContours(vis,[r["contour"]],-1,(35,120,35),-1)
        cv2.drawContours(vis,[r["contour"]],-1,(0,200,140),1)
    for k,col in (("top",(60,60,255)),("bottom",(0,255,255)),
                  ("left",(255,120,60)),("right",(255,120,60))):
        p=r.get(k)
        if p is not None: cv2.circle(vis,(int(round(p[0])),int(round(p[1]))),2,col,-1)
    return vis

def rematar(vis,v2,t,col,etq):
    big=cv2.resize(vis,(v2.W*E,v2.H*E),interpolation=cv2.INTER_NEAREST)
    cv2.line(big,(int(round(v2.CENTER))*E,0),(int(round(v2.CENTER))*E,v2.H*E-1),(95,95,95),1)
    if t is not None:
        cv2.drawMarker(big,(int(t[0]*E+E//2),int(t[1]*E+E//2)),col,cv2.MARKER_TILTED_CROSS,9*E,2)
    cv2.rectangle(big,(0,0),(v2.W*E,26),(0,0,0),-1); txt(big,8,19,etq,col,.55,2)
    return big

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--salida",default="REGISTRO_V1_vs_CAND.mp4")
    a=ap.parse_args()
    v4,v2,v1m=cargar()
    class _N:
        def step(self,p,s): return p,"PASA"
    class SB(v4.NuevoCodeV4):
        def __init__(self,f): v4.NuevoCodeV4.__init__(self,f); self.branch_guard=_N()
    W,H=v2.W*E*3, v2.H*E+150
    vw=cv2.VideoWriter(os.path.join(AQUI,a.salida),cv2.VideoWriter_fourcc(*"mp4v"),FPS,(W,H))
    n=0
    def placa(lin,seg):
        img=np.zeros((H,W,3),np.uint8); y=int(H*.26)
        for s,e,g,c in lin:
            (tw,_),_=cv2.getTextSize(s,FT,e,g); txt(img,(W-tw)//2,y,s,c,e,g); y+=int(38*e+24)
        txt(img,W-470,H-12,AVISO,(110,110,110),.46); return [img]*int(round(seg*FPS))
    for f in placa([("CANDIDATA  contra  V1",1.15,3,(255,255,255)),
                    ("naranja: SinBranch = skeleton + grafo + Dijkstra + lookahead 70px",.6,1,(0,120,255)),
                    ("verde: V1 = POI sobre contorno, la arquitectura de los campeones",.6,1,(120,255,120)),
                    ("V1 gana 4 de 5 metricas: disp +1,83  huecos -204  sin_aut -254  inv -47",.66,2,(120,255,120)),
                    ("pierde solo en saltos >24 px, y el 54% de esos son de FILA,",.6,1,(0,165,255)),
                    ("que no entran en el steer",.6,1,(0,165,255))],5.0):
        vw.write(f); n+=1
    for vid,d,h,nota in TRAMOS:
        ru=os.path.join(AQUI,vid)
        if not os.path.exists(ru): continue
        fps=FPS
        for f in placa([("%s   f%d-%d"%(vid.replace(".avi",""),d,h),1.0,2,(90,230,255)),
                        (nota,.62,1,(200,200,200))],0.8):
            vw.write(f); n+=1
        cap=cv2.VideoCapture(ru); tc=SB(fps); tv=v1m.AirborneV1(fps); i=0
        while True:
            ok,fr=cap.read()
            if not ok or i>h: break
            g=v2.frame_pi(fr); rc=tc.step(g); rv=tv.paso(g)
            if i>=d:
                out=np.zeros((H,W,3),np.uint8); w=v2.W*E
                out[:v2.H*E,:w]=cv2.resize(g,(w,v2.H*E),interpolation=cv2.INTER_NEAREST)
                out[:v2.H*E,w:2*w]=rematar(panel_cand(v2,rc),v2,rc.get("target"),C_CAND,"CANDIDATA")
                out[:v2.H*E,2*w:3*w]=rematar(panel_v1(v1m,rv),v2,rv.get("target"),C_V1,"V1  POI")
                cv2.rectangle(out,(0,0),(w,26),(0,0,0),-1); txt(out,8,19,"CAMARA",(230,230,230),.55,2)
                y0=v2.H*E+30
                txt(out,12,y0,"%s   f%d"%(vid.replace(".avi",""),i),(90,230,255),.8,2)
                tc_,tv_=rc.get("target"),rv.get("target")
                sc=None if tc_ is None else float(np.clip(-90.0*(tc_[0]-v2.CENTER)/(v2.W/2.),-90,90))
                sv=rv.get("angle_target"); sv=None if (sv is None or not np.isfinite(sv)) else float(sv)
                if tc_ is None:
                    cv2.rectangle(out,(560,y0-22),(560+250,y0+8),(0,0,110),-1)
                    txt(out,570,y0,"CANDIDATA SIN TARGET",(255,180,180),.6,2)
                txt(out,12,y0+34,"CANDIDATA  target %s  steer %s  [%s]"
                    %("--" if tc_ is None else "(%3.0f,%3.0f)"%tc_,
                      "--" if sc is None else "%+6.1f"%sc, rc.get("state","")),C_CAND,.55,2)
                txt(out,12,y0+64,"V1         target %s  steer %s  [%s]"
                    %("--" if tv_ is None else "(%3.0f,%3.0f)"%tv_,
                      "--" if sv is None else "%+6.1f"%sv, rv.get("estado","")),C_V1,.55,2)
                txt(out,12,y0+94,"V1 POI: %s"%(rv.get("motivo_target") or "-"),(150,150,150),.48)
                txt(out,W-470,H-12,AVISO,(110,110,110),.46)
                vw.write(out); n+=1
            i+=1
        cap.release()
    vw.release()
    p=os.path.join(AQUI,a.salida)
    print("  %s  %d frames  %.1f s  %.1f MB"%(a.salida,n,n/FPS,os.path.getsize(p)/1e6))


if __name__ == "__main__":
    main()

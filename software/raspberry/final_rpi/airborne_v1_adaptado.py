# -*- coding: utf-8 -*-
"""
AIRBORNE V1 ADAPTADO AL ROBOT RCJ 2026

Shadow/replay de PERCEPCION. No es simulacion fisica y no mueve el robot.

Idea:
  frame -> mascara negra -> contornos -> seleccionar UNA trayectoria por
  continuidad -> POI TOP/LEFT/RIGHT/BOTTOM -> target X suavizado.

Uso:
  python airborne_v1_adaptado.py hist.avi --desde 1354 --hasta 1490 --fps 33.3 --tag hist_falla
  python airborne_v1_adaptado.py hist.avi --desde 580 --hasta 679 --fps 33.3 --tag hist_exito
  python airborne_v1_adaptado.py lineal.avi --desde 800 --hasta 872 --fps 33.3 --tag lineal_positivo
  python airborne_v1_adaptado.py video_4.avi --desde 0 --hasta 641 --fps 20 --tag video4_manual
"""
import argparse, csv, math, os
from collections import deque
import cv2
import numpy as np

W,H=160,120
CENTER=(W-1)/2.0
LO=np.array([0,0,0],np.uint8)
HI=np.array([90,90,90],np.uint8)
NEAR=(110,119); MID=(95,105); FAR=(75,85)
PIX_MIN_BAND=8
FLOOR_TOP=35
LINE_CROP=0.50
MIN_CONTOUR_AREA=8
MIN_VISIBLE_BOTTOM_Y=45
SIDE_HOLD_S=0.60
MULTI_BOTTOM_HOLD_S=0.60
TARGET_AVG_S=0.15
BOTTOM_AVG_S=0.15

COLORS={
    'HIGH':(80,220,80),'MEDIUM':(80,210,220),'LOW':(0,160,255),
    'SIN_CERCA':(255,180,60),'PERDIDA':(80,80,255)
}

def frame_de_la_pi(frame):
    if frame.shape[0]==240 and frame.shape[1]>=640:
        return frame[:,:320][1::2,1::2]
    g=cv2.rotate(frame,cv2.ROTATE_180)
    return cv2.resize(g,(W,H),interpolation=cv2.INTER_NEAREST)

def atan2_actual(g):
    m=cv2.inRange(g,LO,HI); m[:60,:]=0
    if m.sum()<1:return 0.0
    ys,xs=np.nonzero(m)
    xc=(xs-(W/2-1))/(W/2)
    yc=((H-1)-ys)/H
    xb=np.mean(xc*(1-yc)); yb=np.mean(yc)
    return (math.atan2(yb,xb)/math.pi*180.0)-90.0

class Promedio:
    def __init__(self,n): self.q=deque(maxlen=max(1,int(round(n))))
    @property
    def valor(self): return float(np.mean(self.q)) if self.q else None
    def agregar(self,x):
        if x is not None and np.isfinite(x): self.q.append(float(x))
        return self.valor

def separar_runs(vals,max_gap=1):
    vals=np.sort(np.unique(np.asarray(vals,dtype=np.int32)))
    if vals.size==0:return []
    out=[]; s=p=int(vals[0])
    for x in vals[1:]:
        x=int(x)
        if x-p<=max_gap+1:p=x
        else: out.append((s,p)); s=p=x
    out.append((s,p)); return out

def centro_run(r): return (r[0]+r[1])/2.0

class AirborneV1:
    def __init__(self,fps):
        self.fps=float(fps); self.x_last=CENTER; self.y_last=H/2.0
        self.avg_target=Promedio(TARGET_AVG_S*fps)
        self.avg_bottom=Promedio(BOTTOM_AVG_S*fps)
        self.frame_local=-1
        self.side_hold=None; self.side_hold_until=-1
        self.multi_hold=None; self.multi_hold_until=-1

    def mascara(self,g):
        m=cv2.inRange(g,LO,HI); m[:FLOOR_TOP,:]=0
        htri=int(H*.15); wtri=int(W*.25)
        tl=np.array([[0,FLOOR_TOP],[wtri,FLOOR_TOP],[0,min(H-1,FLOOR_TOP+htri)]],np.int32)
        tr=np.array([[W-1,FLOOR_TOP],[W-1-wtri,FLOOR_TOP],[W-1,min(H-1,FLOOR_TOP+htri)]],np.int32)
        cv2.fillPoly(m,[tl],0); cv2.fillPoly(m,[tr],0)
        return m

    def seleccionar_contorno(self,m):
        # RETR_EXTERNAL y no RETR_LIST: `RETR_LIST` devuelve tambien los
        # AGUJEROS, y un reflejo blanco adentro de la cinta negra es un
        # agujero. Pasaba el filtro de area, pasaba el de borde inferior y
        # competia por continuidad como si fuera la trayectoria.
        # Medido sobre los 13.900 frames de los 10 autonomos: el contorno
        # elegido ERA un agujero en 295 frames (2,12 %), con la traza del
        # traspaso reproducida en hist.avi f626-627. Con EXTERNAL cambian 687
        # frames (4,94 %), los saltos>24 px bajan de 928 a 910, ninguna de las
        # cinco metricas empeora y el gate queda identico.  (ab_retr_external.py)
        contours,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
        cand=[]
        for c in contours:
            if len(c)<2:continue
            area=float(cv2.contourArea(c))
            if area<MIN_CONTOUR_AREA:continue
            box=cv2.boxPoints(cv2.minAreaRect(c)); by=float(np.max(box[:,1]))
            if by<MIN_VISIBLE_BOTTOM_Y:continue
            xm=float(np.mean(np.clip(box[:,0],0,W-1)))
            ym=float(np.mean(np.clip(box[:,1],0,H-1)))
            d=abs(self.x_last-xm)+abs(self.y_last-ym)
            cand.append(dict(c=c,area=area,by=by,xm=xm,ym=ym,d=d))
        if not cand:return None,'sin_contorno'
        abajo=[x for x in cand if x['by']>=H*.75]
        if len(abajo)>=2:
            e=min(abajo,key=lambda x:x['d']); reason='continuidad_multi_abajo'
        elif len(abajo)==1:
            e=abajo[0]; reason='unico_abajo'
        else:
            e=min(cand,key=lambda x:(x['d'],-x['by'])); reason='continuidad_adelante'
        self.x_last=e['xm']; self.y_last=e['ym']
        return e['c'],reason

    def puntos_interes(self,c):
        pts=c[:,0,:]
        ref=self.avg_target.valor if self.avg_target.valor is not None else self.x_last
        bref=self.avg_bottom.valor if self.avg_bottom.valor is not None else CENTER
        yt=int(pts[:,1].min()); xt=pts[pts[:,1]==yt][:,0]; rr=separar_runs(xt)
        top=((centro_run(min(rr,key=lambda r:abs(centro_run(r)-ref))) if rr else float(np.mean(xt))),float(yt))
        yb=int(pts[:,1].max()); xb=pts[pts[:,1]==yb][:,0]; br=separar_runs(xb)
        bottoms=[(centro_run(r),float(yb)) for r in br]
        bottom=min(bottoms,key=lambda p:abs(p[0]-bref)) if bottoms else (float(np.mean(xb)),float(yb))
        other=None
        if len(bottoms)>=2:
            oo=[p for p in bottoms if abs(p[0]-bottom[0])>1]
            if oo:other=max(oo,key=lambda p:abs(p[0]-bottom[0]))
        xl=int(pts[:,0].min()); yl=pts[pts[:,0]==xl][:,1]
        xr=int(pts[:,0].max()); yr=pts[pts[:,0]==xr][:,1]
        full=dict(top=top,bottom=bottom,other_bottom=other,
                  left=(float(xl),float(np.mean(yl))),right=(float(xr),float(np.mean(yr))))
        cp=pts[pts[:,1]>H*LINE_CROP]; crop=None
        if len(cp)>=2:
            cyt=int(cp[:,1].min()); cxt=cp[cp[:,1]==cyt][:,0]; crr=separar_runs(cxt)
            ctop=((centro_run(min(crr,key=lambda r:abs(centro_run(r)-ref))) if crr else float(np.mean(cxt))),float(cyt))
            cxl=int(cp[:,0].min()); cyl=cp[cp[:,0]==cxl][:,1]
            cxr=int(cp[:,0].max()); cyr=cp[cp[:,0]==cxr][:,1]
            crop=dict(top=ctop,left=(float(cxl),float(np.mean(cyl))),right=(float(cxr),float(np.mean(cyr))),
                      max_black_top=bool(np.ptp(cxt)>W*.30 if cxt.size else False))
        return full,crop

    def confianza(self,c):
        if c is None:return 'PERDIDA'
        mm=np.zeros((H,W),np.uint8); cv2.drawContours(mm,[c],-1,255,-1)
        def band(ab):
            a,b=ab; return int((mm[a:b+1]>0).sum())>=PIX_MIN_BAND
        near,mid,far=band(NEAR),band(MID),band(FAR)
        if not near:return 'SIN_CERCA'
        if mid and far:return 'HIGH'
        if mid:return 'MEDIUM'
        return 'LOW'

    @staticmethod
    def avgp(a,b):return ((a[0]+b[0])/2.0,(a[1]+b[1])/2.0)

    def interpretar(self,full,crop,estado):
        top,bottom,left,right=full['top'],full['bottom'],full['left'],full['right']
        ref=self.avg_target.valor if self.avg_target.valor is not None else CENTER
        if estado=='SIN_CERCA':return bottom,'sin_cerca_bottom_visible'
        if estado=='PERDIDA':return None,'perdida_sin_target'
        iscrop=crop is not None; black_top=top[1]<50
        black_l_high=left[1]<H*.50; black_r_high=right[1]<H*.50
        multi=full['other_bottom'] is not None and abs(full['other_bottom'][0]-bottom[0])>W*.18
        if black_top:
            target=crop['top'] if iscrop and not crop['max_black_top'] else top
            why='top_continuacion'
            side_low=((left[0]<W*.05 and left[1]>H*.45) or (right[0]>W*.95 and right[1]>H*.45))
            if side_low and (black_l_high or black_r_high):
                ops=[]
                if black_l_high:ops.append(left)
                if black_r_high:ops.append(right)
                if ops:
                    p=min(ops,key=lambda q:abs(q[0]-ref))
                    if abs(p[0]-ref)<abs(target[0]-ref):target=p; why='top_lateral_continuidad'
            return target,why
        target=crop['top'] if iscrop else top; why='top_crop'
        both=left[0]<W*.03 and right[0]>W*.97
        if both and iscrop and crop['max_black_top']:
            return min([crop['top'],top],key=lambda p:abs(p[0]-ref)),'cruce_ancho_continuidad'
        if self.side_hold is not None and self.frame_local<=self.side_hold_until:
            p=crop[self.side_hold] if iscrop else full[self.side_hold]
            if iscrop:p=self.avgp(p,full[self.side_hold])
            return p,'lateral_persistente_'+self.side_hold
        if both:
            self.side_hold='right' if ref>=CENTER else 'left'
            self.side_hold_until=self.frame_local+int(round(SIDE_HOLD_S*self.fps))
            p=crop[self.side_hold] if iscrop else full[self.side_hold]
            if iscrop:p=self.avgp(p,full[self.side_hold])
            return p,'doble_borde_'+self.side_hold
        if left[0]<=1 and left[1]>H*.45:
            p=crop['left'] if iscrop else left
            return (self.avgp(p,left) if iscrop else p),'sale_izquierda'
        if right[0]>=W-2 and right[1]>H*.45:
            p=crop['right'] if iscrop else right
            return (self.avgp(p,right) if iscrop else p),'sale_derecha'
        if multi and self.frame_local>self.multi_hold_until:
            other=full['other_bottom']; side=0.0 if other[0]<bottom[0] else float(W-1)
            self.multi_hold=side; self.multi_hold_until=self.frame_local+int(round(MULTI_BOTTOM_HOLD_S*self.fps))
            return (side,float(H-1)),'multi_bottom'
        if self.multi_hold is not None and self.frame_local<=self.multi_hold_until:
            return (self.multi_hold,float(H-1)),'multi_bottom_hold'
        return target,why

    def paso(self,g):
        self.frame_local+=1; m=self.mascara(g); c,ms=self.seleccionar_contorno(m)
        if c is None:
            return dict(mask=m,contour=None,estado='PERDIDA',target=None,top=None,bottom=None,left=None,right=None,
                        angle_target=float('nan'),motivo_sel=ms,motivo_target='perdida_sin_target')
        estado=self.confianza(c); full,crop=self.puntos_interes(c); raw,mt=self.interpretar(full,crop,estado)
        if raw is None:
            return dict(mask=m,contour=c,estado=estado,target=None,top=full['top'],bottom=full['bottom'],left=full['left'],right=full['right'],
                        angle_target=float('nan'),motivo_sel=ms,motivo_target=mt)
        tx=self.avg_target.agregar(raw[0]); bx=self.avg_bottom.agregar(full['bottom'][0])
        ang=float(np.clip(-90.0*(tx-CENTER)/(W/2.0),-90,90))
        return dict(mask=m,contour=c,estado=estado,target=(tx,raw[1]),top=full['top'],
                    bottom=(bx if bx is not None else full['bottom'][0],full['bottom'][1]),left=full['left'],right=full['right'],
                    angle_target=ang,motivo_sel=ms,motivo_target=mt)

def pi(p):return None if p is None else (int(round(p[0])),int(round(p[1])))

def draw_panel(r):
    vis=np.zeros((H,W,3),np.uint8); vis[r['mask']>0]=(50,50,50)
    if r['contour'] is not None:cv2.drawContours(vis,[r['contour']],-1,COLORS.get(r['estado'],(220,220,220)),1)
    for lab,key,col in [('T','top',(60,60,255)),('B','bottom',(0,255,255)),('L','left',(255,120,60)),('R','right',(255,120,60))]:
        p=r[key]
        if p is not None:
            q=pi(p); cv2.circle(vis,q,3,col,-1); cv2.putText(vis,lab,(q[0]+3,max(10,q[1]-3)),cv2.FONT_HERSHEY_SIMPLEX,.3,col,1,cv2.LINE_AA)
    if r['target'] is not None:
        t=pi(r['target']); cv2.drawMarker(vis,t,(255,255,255),cv2.MARKER_TILTED_CROSS,10,1)
        if r['bottom'] is not None:cv2.line(vis,pi(r['bottom']),t,(255,255,255),1)
    cv2.line(vis,(int(round(CENTER)),0),(int(round(CENTER)),H-1),(80,80,80),1)
    return vis

def fmt(v):
    try:return '' if v is None or not np.isfinite(v) else f'{float(v):.3f}'
    except:return ''

def correr(ruta,desde,hasta,fps,tag,salida_dir):
    cap=cv2.VideoCapture(ruta)
    if not cap.isOpened():raise RuntimeError('No se pudo abrir '+ruta)
    tracker=AirborneV1(fps); E=4; CW,CH=W*E,H*E; OW,OH=CW*2,CH+175
    avi=os.path.join(salida_dir,f'airborne_v1_{tag}.avi'); csvp=os.path.join(salida_dir,f'airborne_v1_{tag}.csv')
    vw=cv2.VideoWriter(avi,cv2.VideoWriter_fourcc(*'MJPG'),fps,(OW,OH))
    fc=open(csvp,'w',newline='',encoding='utf-8'); wr=csv.writer(fc)
    wr.writerow(['source_frame','source_time_s','estado','angle_actual','target_x','target_y','angle_target_shadow',
                 'top_x','top_y','bottom_x','bottom_y','left_x','left_y','right_x','right_y','seleccion_contorno','motivo_target'])
    i=0
    while True:
        ok,fr=cap.read()
        if not ok:break
        g=frame_de_la_pi(fr); r=tracker.paso(g)
        if i<desde:i+=1; continue
        if i>hasta:break
        a=atan2_actual(g)
        def xy(k,j):
            p=r[k]; return fmt(p[j]) if p is not None else ''
        wr.writerow([i,f'{i/fps:.3f}',r['estado'],f'{a:.3f}',xy('target',0),xy('target',1),fmt(r['angle_target']),
                     xy('top',0),xy('top',1),xy('bottom',0),xy('bottom',1),xy('left',0),xy('left',1),xy('right',0),xy('right',1),
                     r['motivo_sel'],r['motivo_target']])
        cam=cv2.resize(g,(CW,CH),interpolation=cv2.INTER_NEAREST)
        tra=cv2.resize(draw_panel(r),(CW,CH),interpolation=cv2.INTER_NEAREST)
        out=np.zeros((OH,OW,3),np.uint8); out[:CH,:CW]=cam; out[:CH,CW:]=tra
        cv2.putText(out,'CAMARA QUE VIO LA PI',(10,24),cv2.FONT_HERSHEY_SIMPLEX,.6,(235,235,235),1,cv2.LINE_AA)
        cv2.putText(out,'AIRBORNE V1 ADAPTADO',(CW+10,24),cv2.FONT_HERSHEY_SIMPLEX,.6,(235,235,235),1,cv2.LINE_AA)
        y=CH+28; col=COLORS.get(r['estado'],(235,235,235))
        cv2.putText(out,f"frame {i} t={i/fps:.2f}s ESTADO {r['estado']}",(10,y),cv2.FONT_HERSHEY_SIMPLEX,.58,col,1,cv2.LINE_AA)
        cv2.putText(out,f'atan2 ACTUAL {a:+6.1f} deg',(10,y+30),cv2.FONT_HERSHEY_SIMPLEX,.55,(100,100,255),1,cv2.LINE_AA)
        tx='--' if r['target'] is None else f"{r['target'][0]:.1f}"
        cv2.putText(out,f"TARGET X {tx} px | shadow {fmt(r['angle_target'])} deg",(10,y+60),cv2.FONT_HERSHEY_SIMPLEX,.55,(120,230,120),1,cv2.LINE_AA)
        cv2.putText(out,f"contorno: {r['motivo_sel']} POI: {r['motivo_target']}",(10,y+90),cv2.FONT_HERSHEY_SIMPLEX,.48,(190,190,190),1,cv2.LINE_AA)
        cv2.putText(out,'SHADOW DE PERCEPCION - NO SIMULA EL MOVIMIENTO FUTURO',(10,y+125),cv2.FONT_HERSHEY_SIMPLEX,.50,(0,210,255),1,cv2.LINE_AA)
        vw.write(out); i+=1
    cap.release(); vw.release(); fc.close(); return avi,csvp

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--desde',type=int,default=0); ap.add_argument('--hasta',type=int,default=10**9)
    ap.add_argument('--fps',type=float,default=33.3); ap.add_argument('--tag',default='salida'); ap.add_argument('--salida-dir',default='.')
    a=ap.parse_args(); avi,csvp=correr(a.video,a.desde,a.hasta,a.fps,a.tag,a.salida_dir); print(avi); print(csvp)
if __name__=='__main__':main()

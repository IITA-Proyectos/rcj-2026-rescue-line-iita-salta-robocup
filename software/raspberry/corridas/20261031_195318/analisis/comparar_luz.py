from pathlib import Path
import cv2,numpy as np,pandas as pd
D=Path(__file__).resolve().parents[1]/'crudo_20261031_195318/1031_195426'
def detect(im,L):
 lab=cv2.cvtColor(im,cv2.COLOR_BGR2LAB);g=cv2.inRange(lab,np.array([L,90,110]),np.array([198,109,134]));g[:80]=0;b=cv2.inRange(im,np.array([0,0,0]),np.array([90,90,90]));b[:60]=0;area=np.count_nonzero(g)
 if area<=600:return area,0,0
 xs=np.flatnonzero(g.max(axis=0));l,r=xs[0],xs[-1];occ=np.count_nonzero(b[60:90,l:r+1])/(30*max(1,r-l));m=cv2.moments(b[90:]);cx=m['m10']/m['m00'] if m['m00'] else None
 if cx is None or occ<=.32:return area,round(occ,3),0
 cs,_=cv2.findContours(cv2.dilate(cv2.erode(g,np.ones((3,3),np.uint8)),np.ones((3,3),np.uint8),iterations=2),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
 gs=3 if len(cs)>1 and l<cx<r else 1 if (l+r)/2<cx else 2
 return area,round(occ,3),gs
if __name__=='__main__':
 for n in [274,277,281,1132,1133,1134,1135,1136,1137,1143,1259,1260,1261,1262,1263,1264,1265,1266,1267]:
  im=cv2.imread(str(D/f'f_{n:06d}.png'));print(n,{L:detect(im,L) for L in [120,110,100,95,90]})

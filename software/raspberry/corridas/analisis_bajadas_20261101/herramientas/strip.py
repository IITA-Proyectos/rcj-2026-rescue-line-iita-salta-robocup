import cv2,numpy as np,sys,csv
S,video,cuad,name=sys.argv[1:5]; frames=[int(v) for v in sys.argv[5].split(',')] if ',' in sys.argv[5] else list(range(*map(int,sys.argv[5].split(':'))))
cols=int(sys.argv[6]) if len(sys.argv)>6 else 4
c=cv2.VideoCapture(video)
r={int(x['n']):x for x in csv.DictReader(open(cuad))}
want=set(frames);fr={};n=0
while len(fr)<len(want):
    ok,im=c.read(); n+=1
    if not ok: break
    if n in want: fr[n]=im
ims=[]
for f in frames:
    im=fr[f]; L=cv2.resize(im[:,:320],(400,300)); M=cv2.resize(im[:,320:],(200,150))
    canvas=np.zeros((300,600,3),np.uint8); canvas[:,:400]=L; canvas[:150,400:]=M
    x=r.get(f,{})
    for i,t in enumerate(['n=%d  %d:%05.2f'%(f,f/20//60,f/20%60),'t=%s'%x.get('t'),'manda %s'%x.get('angle'),'gs %s rampa %s'%(x.get('green_state'),x.get('rampa')),x.get('quien','')[:22],'negro %s'%x.get('negro_px')]):
        cv2.putText(canvas,t,(405,170+i*22),0,0.5,(0,255,255),1)
    ims.append(canvas)
while len(ims)%cols: ims.append(ims[0]*0)
cv2.imwrite(S+'/'+name,np.vstack([np.hstack(ims[i:i+cols]) for i in range(0,len(ims),cols)]))

from pathlib import Path
import json,csv,ast
import cv2,numpy as np
D=Path('/home/iita/crudo_recuperacion_corregida_20261031_213650/1031_213701');O=Path('/tmp/revision_213650');O.mkdir(exist_ok=True)
rows={int(r['n']):r for r in csv.DictReader((D/'cuadros.csv').open())};cards=json.loads(Path('/tmp/tarjetas_213650.json').read_text())
env=dict(cv2=cv2,np=np,AREA_MIN_LINEA=200)
for node in ast.parse(Path('/home/iita/Desktop/main.py').read_text()).body:
 if isinstance(node,ast.FunctionDef) and node.name=='_solo_mi_linea':exec(compile(ast.Module(body=[node],type_ignores=[]),'analisis','exec'),env)
shapes=[]
for page in range((len(cards)+6)//7):
 chunk=cards[page*7:page*7+7];canvas=np.full((len(chunk)*180,1200,3),245,dtype=np.uint8)
 for i,card in enumerate(chunk):
  for j,n in enumerate(card['frames']):
   r=rows[n];im=cv2.imread(str(D/f'f_{n:06d}.png'));full=cv2.inRange(im,np.array([0,0,0]),np.array([90,90,90]));full[:60]=0;mm=env['_solo_mi_linea'](full)
   x=j*200;y=i*180;canvas[y:y+150,x:x+200]=cv2.resize(im,(200,150));title=f"E{card['id']} f{n} {(n-1)/20:.1f}s GS{r['green_state']}"
   cv2.putText(canvas,title,(x+2,y+162),cv2.FONT_HERSHEY_SIMPLEX,.31,(0,0,0),1)
   cv2.putText(canvas,f"a{float(r['angle']):.0f} {r['quien'][:22]}",(x+2,y+175),cv2.FONT_HERSHEY_SIMPLEX,.31,(0,0,0),1)
   shapes.append((card['id'],n,int(np.count_nonzero(mm)),int(np.count_nonzero(full))))
 cv2.imwrite(str(O/f'todas_{page+1:02d}.jpg'),canvas,[cv2.IMWRITE_JPEG_QUALITY,92])
with (O/'conexion_tarjetas.csv').open('w',newline='') as out:
 w=csv.writer(out);w.writerow(['episode','frame','connected_px','black_px']);w.writerows(shapes)
print('atlas',len(cards))

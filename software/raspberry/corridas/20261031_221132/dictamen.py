from pathlib import Path
import pandas as pd,numpy as np,cv2
B=Path('raspberry/corridas/20261031_221132');O=B/'analisis_exhaustivo';D=B/'crudo_reenganche_20261031_221132/1031_221136';f=pd.read_csv(B/'cuadros.csv').set_index('n');m=pd.read_csv(O/'metricas_todos_cuadros.csv').drop_duplicates('n').set_index('n');e=pd.read_csv(B/'analisis/episodios_69.csv');s=pd.read_csv(O/'todas_acciones.csv')
notes={
1:('Reenganche con oscilacion','El pivote derecho pierde conexion; 0,33 s de busqueda izquierda recuperan cinta. Alterna +54/-65 antes de estabilizar y continuar.'),
2:('Recupera y continua','Izquierda; vuelve a cinta y sigue la curva con correcciones alternantes. No interviene la busqueda nueva.'),
3:('Recupera; encadena GAP','Derecha; cinta transversal al salir. COMPLETAR_GIRO manda -85 y vuelve al seguidor; despues llega al GAP 4.'),
4:('GAP cruzado; salida fragil','GS18 recto cruza y declara recuperado en f803. La curva inmediata se pierde y dispara 5 en f843.'),
5:('STOP sin reenganche','Izquierda +36,8. Cinta queda hacia el borde derecho; complemento +85 la pierde. Evidencia izquierda 9 no alcanza 12: no hay busqueda hacia fragmento.'),
6:('Recupera; encadena GAP','Derecha -59,3; COMPLETAR_GIRO breve -85. Cinta vuelve y sigue al GAP 7.'),
7:('GAP cruzado; salida fragil','GS18 recto recupera en f1227; la curva inmediata se pierde y dispara 8 en f1261.'),
8:('Recaptura; otra perdida despues','Izquierda +64,3; entrega al centroide con -64,2. Vuelve a seguir, pero pierde el siguiente codo y dispara 9.'),
9:('Decision tardia; recupera','AMBIGUA unos 0,95 s; rama previa fuerza derecha -35. Luego aparece cooldown recto con linea transversal; finalmente recaptura.'),
10:('Recupera y continua','Rama previa confirma derecha -57,9 tras ambiguedad; recaptura con cambios de signo y continua el zigzag.'),
11:('Recupera con complemento','Derecha -70,4; COMPLETAR_GIRO -85 sostenido y oscilacion al volver al seguidor; sigue con linea visible.'),
12:('Reengancha pero STOP indebido','Derecha -47; busqueda +85 recupera cinta en f2157. El limite de un segundo termina en GS19 f2172 con 3258 px conectados.'),
13:('Recaptura; otra perdida despues','Rama previa cambia el lado y manda derecha -12; tras cooldown vuelve a cinta. Mas tarde pierde siguiente codo izquierdo y dispara 14.'),
14:('Recupera y continua','Izquierda +64,7; tras tramo recto de cooldown vuelve al seguidor y continua curva.'),
15:('Recupera; encadena GAP','Derecha -59,8; COMPLETAR_GIRO -85 y varias inversiones de signo antes del GAP 16.'),
16:('GAP cruzado; salida fragil','GS18 recto recupera en f3003; se pierde la curva inmediata y dispara 17 en f3039.'),
17:('Recaptura; otra perdida despues','Izquierda +46,5; entrega al centroide -65,1, oscila, sigue la cinta y pierde siguiente codo derecho en 18.'),
18:('Recupera y continua','Derecha -58,4; pasa por cooldown recto con cinta transversal. Luego recaptura y continua el zigzag.'),
19:('Recupera y continua','Derecha -73; vuelve al centroide con +57 y cambios de signo; mantiene cinta en la salida revisada.'),
20:('Recupera con complemento','Rama previa derecha -43,2; COMPLETAR_GIRO -85. Vuelve al seguidor y continua.'),
21:('GAP cruzado y salida seguida','GAP recto del puente; recupera en f3849 y mantiene cinta. Hay confirmaciones de perdida breves sin nuevo GS4.'),
22:('Recupera y entra a rampa','Derecha -59,6; devuelve al seguidor, corrige fuerte y mantiene linea al entrar en rampa.'),
23:('GAP cruzado y salida seguida','GAP recto despues de rampa; recupera en f4745 y sigue linea hacia descenso.'),
24:('Recupera; verde posterior','Izquierda +66,7; complemento guard +85 de dos cuadros. Sigue hasta verde derecho GS2; tras verde hay mascara vacia temporal, separado del cierre de recuperacion.'),
25:('Reenganche con oscilacion','Derecha -65,5; complemento -85 no recaptura, busqueda +85 de 0,70 s lo logra. Vuelve a oscilar y continua hasta otro codo.'),
26:('Recupera con complemento breve','Izquierda +67,7; complemento guard +85 dos cuadros. Sigue la curva; mas adelante aparece otra perdida (27), fuera de la ventana principal de cinco segundos.'),
27:('Sin cinta util; STOP','Entrada con orden +65 y cinta baja ya casi fuera. Tras retroceso se ve mayormente piso. Rama previa manda izquierda +35 tarde; no hay fragmento fresco y termina STOP.'),
28:('Recupera; encadena GAP','Derecha -71,3; COMPLETAR_GIRO -85. Vuelve a cinta, atraviesa hacia GAP y se pierde la siguiente curva en 29.'),
29:('STOP sin reenganche','Repite 5: izquierda +41,4, complemento +85, cinta se aleja al borde derecho. Solo 9 observaciones izquierdas: no se habilita busqueda hacia fragmento.')}
rows=[]
for r in e.itertuples():
 z=s[s.id.eq(r.id)];res,obs=notes[r.id];mins=int(r.avi_s//60);secs=r.avi_s%60
 rows.append(dict(id=r.id,avi=f'{mins:02d}:{secs:05.2f}',frame=r.start,decision='GAP' if r.kind=='GAP' else 'Derecha' if r.angle<0 else 'Izquierda',angle=r.angle,CG_frames=sum(z[z.quien.eq('recup-completa-giro')].end-z[z.quien.eq('recup-completa-giro')].start+1),guard_frames=sum(z[z.quien.eq('recup-guard-completa')].end-z[z.quien.eq('recup-guard-completa')].start+1),search_frames=sum(z[z.quien.eq('recup-guard-reenganche')].end-z[z.quien.eq('recup-guard-reenganche')].start+1),result=res,observation=obs))
pd.DataFrame(rows).to_csv(O/'dictamen_29.csv',index=False)
# Comparacion puntual de los dos patrones repetidos.
cards=[(1,[187,202,208,219,229,234,240,258]),(12,[2111,2126,2133,2144,2156,2163,2169,2172]),(25,[6382,6397,6402,6413,6427,6449,6453,6461]),(5,[843,860,875,880,891,899,904,905]),(17,[3039,3056,3071,3075,3083,3100,3130,3165]),(29,[7262,7278,7293,7298,7309,7317,7322,7323])]
canvas=np.full((len(cards)*180,1600,3),245,np.uint8)
for i,(ident,ns) in enumerate(cards):
 for j,n in enumerate(ns):
  r=f.loc[n];im=cv2.imread(str(D/f'f_{n:06d}.png'));x=j*200;y=i*180;canvas[y:y+150,x:x+200]=cv2.resize(im,(200,150),interpolation=cv2.INTER_NEAREST)
  cv2.putText(canvas,f'E{ident} f{n} {(n-1)/20:.2f}s G{r.green_state}',(x+2,y+162),0,.31,(0,0,0),1)
  cv2.putText(canvas,f'{r.angle:+.0f} '+r.quien.replace('recup-','r-')[:23],(x+2,y+176),0,.31,(0,0,0),1)
cv2.imwrite(str(O/'comparacion_patrones.jpg'),canvas,[cv2.IMWRITE_JPEG_QUALITY,94])
print(pd.DataFrame(rows)[['id','avi','decision','CG_frames','guard_frames','search_frames','result']].to_string(index=False))

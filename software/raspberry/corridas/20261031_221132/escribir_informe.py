from pathlib import Path
import pandas as pd,html,json
B=Path('raspberry/corridas/20261031_221132');O=B/'analisis_exhaustivo';q=pd.read_csv(O/'dictamen_29.csv');inv=pd.read_csv(O/'inventario.csv');s=pd.read_csv(O/'todas_acciones.csv')
intro='''# Revision visual y cruce de las 29 recuperaciones

Esta revision reemplaza la interpretacion rapida anterior: recapturar cinta no significa terminar estable una recuperacion ni superar la curva siguiente. No se atribuyen todas las fallas a una misma causa.

## Archivos y versiones corroboradas

- Video revisado: pista_reenganche_20261031_221132.avi, 31/10 a las 22:11, 7420 cuadros, con crudo y registro de ordenes. main SHA256 991df6bf36ce29d61457df8e46a9a67e6ab7b96c9f3d911a3d1dd6051f20e098; helper SHA256 7beb66b2a11786f20fba0ab512f9ccae0149d2bda1cddb3e77d982b4cefc0845. Corresponde a RECUP-REENGANCHE-2.
- La corrida posterior iniciada por servicio a las 22:19 tambien declara RECUP-REENGANCHE-2. Su log dice Video y Crudo vacios: no hay imagenes de esa corrida para contrastar su movimiento visualmente. El nombre de version coincide; ese log por si solo no acredita todos los archivos o el firmware compilado.
- El video anterior de las 21:36 con 69 episodios corresponde a RECUP-GEOMETRIA-1, main SHA256 62a01b4bbc9b8cc82e6fd2abc548f8826e774b58d14942ccbc16e12602c2ee53: entre esos dos videos SI cambio el programa.
- RECUP-REENGANCHE-3 esta preparado localmente; el intento de transferencia fallo y no se lo cuenta como instalado.
- No hay CSV de ruedas/encoders/yaw de esta prueba. La tabla de ordenes acredita lo que registro el envio de Raspberry; no acredita recepcion de cada trama ni giro real de las ruedas. La Raspberry actualmente no responde en la IP conocida, por lo que no se verificaron archivos nuevos posteriores a los descargados.

## Alcance real de la revision

Se revisaron visualmente 50 laminas temporales, con 2287 posiciones de imagen (puede haber repetidas entre ventanas), muestreando un cuadro de cada dos y agregando cambios de accion. Se midieron todos los cuadros de esas ventanas: 4282 registros, 4162 cuadros distintos. Las ventanas incluyen aproximacion, todo GS4 y hasta cinco segundos reales despues, limitadas por el siguiente episodio o cambio de sesion. En las laminas se ven las ordenes GS/angulo/quien y el numero de cuadro.

Esto es una revision de las 29 secuencias con todas sus transiciones de accion, no una afirmacion de haber inspeccionado visualmente los 7420 cuadros uno por uno. Tampoco una recaptura en cinco segundos certifica toda la pista. Los tiempos de esta tabla son del AVI, a 20 FPS. Las duraciones fisicas aproximadas se calculan por t de cuadros.csv; no hay que usar la escala temporal del AVI como reloj del robot.

## Hallazgos principales

### 1. El reenganche nuevo actua solo en tres episodios; no explica por si solo todas las salidas

En esta grabacion aparece recup-guard-reenganche en 1,12,25. El 1 gira hacia el fragmento izquierdo durante 11 cuadros, unos 0,33 s entre primer y ultimo envio, y vuelve al seguidor. El 25 primero agota el complemento derecho y luego invierte hacia el fragmento izquierdo durante 23 cuadros, unos 0,70 s, y vuelve al seguidor. En ambos hay oscilacion visible al devolver el control. El 12 tambien devuelve cinta, pero se detiene por el cierre temporal explicado abajo.

Las otras 26 recuperaciones no reciben la orden SEARCH nueva. Sus diferencias de resultado no pueden atribuirse directamente a un giro SEARCH que no se envio. Eso no demuestra ausencia de cualquier efecto indirecto o diferencia fisica: las entradas, posiciones y luminosidad no son identicas y no hay medicion de ruedas.

### 2. Mismo codo izquierdo: episodios 5 y 29, 00:42,10 y 06:03,05

Ambos llegan despues de cruzar GAP y perder la curva inmediata. Eligen izquierda (+36,8 y +41,4 de protocolo), retroceden y pivotan. Al soltar GS4 no hay componente conectada; la cinta queda al borde derecho y se aleja durante el complemento izquierdo +85. Se termina en STOP f905 y f7323.

En los dos la historia congelada es exactamente side=0,left=9,right=0. El minimo de rama persistente es 12 observaciones. Por eso el reintento hacia el fragmento NO se habilita, aunque el lado elegido por el clasificador sea izquierda. Es un bloqueo logico verificable; no es evidencia de que el robot hubiera girado una cantidad concreta de grados.

El episodio 17 es un control util: tambien sale del mismo tipo de GAP y elige izquierda. Su historia tiene left=13,right=0 y al soltar GS4 ya vuelve a haber cinta conectada, por lo que el seguidor puede continuar. Segun el ultimo fuente Teensy disponible, los objetivos iniciales de 5,17,29 quedan todos en aproximadamente 35 grados por el minimo impuesto. Un objetivo teorico igual no da una pose final igual; esto no justifica aumentar globalmente el giro.

### 3. STOP con cinta recuperada: episodio 12, 01:48,55

La busqueda izquierda empieza en f2144 y vuelve al seguidor en f2157. Desde ahi hay linea conectada, pero el reloj de un segundo sigue corriendo. En f2172 vence y envia GS19.

| Cuadro | Cinta conectada px | Error cercano | Diferencia lejana-cercana | Orden registrada |
|---:|---:|---:|---:|---:|
| 2170 | 3065 | +0,506 | -0,600 | -48,4 |
| 2171 | 3312 | +0,331 | -0,550 | -30,3 |
| 2172 | 3258 | +0,175 | -0,519 | 0, GS19 |

El error cercano mejora, pero la condicion de orientacion <=0,50 no se cumple y no se acumulan tres cuadros centrados. Se esta confundiendo cinta todavia en acomodo con cinta perdida. La revision 3 preparada modifica este caso: al vencer el plazo permite entregar al seguidor si hay tres cuadros seguidos observables con tolerancia de seguimiento. Su replay cambia solo f2172 del episodio 12 en las ventanas de esta prueba. Eso demuestra seleccion del caso, no prueba la trayectoria fisica futura.

### 4. GAP correcto con mala transicion a la curva

Los cinco GAP de esta grabacion cruzan y vuelven al seguimiento: episodios 4,7,16,21,23. En tres, la curva inmediatamente posterior vuelve a perderse:

| GAP | Recupera en cuadro | Nueva perdida | Tiempo real hasta nueva perdida |
|---:|---:|---:|---:|
| 4 | 803 | 843, episodio 5 | 1,520 s |
| 7 | 1227 | 1261, episodio 8 | 1,269 s |
| 16 | 3003 | 3039, episodio 17 | 1,379 s |

No son tres decisiones GAP incorrectas. Se vuelve al control por centroide y se llega a la curva con desplazamiento y ordenes grandes. Se observan magnitudes de 80-88 antes de perder la conexion. Otros encadenamientos tambien obligan a distinguir recaptura de salida estable: 8 ->9, 13 ->14 y 17 ->18. En 28 se recupera el codo, se atraviesa la zona de GAP por seguimiento y se termina perdiendo la curva que dispara 29; alli no se envia GS18 entre los dos episodios.

### 5. Los complementos y el seguidor explican parte de la oscilacion

Hay tres fuentes diferentes que pueden terminar imponiendo un giro: el pivote de GS4 en Teensy; COMPLETAR_GIRO ante cinta transversal conectada; y RecoveryGuard ante falta de recaptura. No deben confundirse en el inventario.

COMPLETAR_GIRO actua en 3,6,11,15,20,28 con orden -85. El complemento de RecoveryGuard actua en 5,24,25,26,29; en 24 y26 dura solo dos cuadros. La busqueda nueva actua solo en 1,12,25 y manda +85 en los tres.

El programa conserva el seguidor por centroide (CTRL por defecto atan2), no un PID nuevo. Tras recaptura aparecen inversiones rapidas, por ejemplo en 12: +48 al volver la cinta, luego -67, -30 y STOP. En 1 y25 tambien aparece el cambio de + a - durante el acomodo. El criterio de dos formas A/D del cierre anterior no mide centrado: una A puede quedar muy lateral. El seguidor normal usa informacion distinta a la geometria de dos bandas que la proteccion usa para aprobar el cierre.

En el ultimo fuente Teensy disponible, un GS0 con +/-85 normaliza steer a aproximadamente +/-0,944 y alcanza el umbral de pivote 0,92. Ademas entra en la rama de curvas cerradas LINE_FRENO_STEER=0,70, con LINE_FRENO_VEL=55; el pivote inicial GS4 usa RECUP_GIRO_VEL=35. Son objetivos del fuente disponible, no RPM medidas de esta corrida ni prueba del binario cargado. Una orden de Raspberry de 85 NO significa 85 grados de yaw. Reducir solamente speed en la trama Pi tampoco regula la velocidad normal de linea: esa rama calcula su propia velocidad en Teensy.

### 6. El episodio 27 no es el mismo fallo de un codo bien visible

A 05:40,75 queda muy poca cinta util; tras retroceder la imagen muestra principalmente piso. La historia izquierda hace que al agotarse la ambiguedad se mande izquierda +35. No aparece fragmento reciente suficiente para el reenganche y la proteccion detiene. Hay que revisar la salida anterior y la validez temporal de la memoria, no habilitar un giro indefinido sobre piso sin linea. El video no permite excluir toda manipulacion externa en la entrada; no se afirma que la causa mecanica este demostrada.

## Inventario de las 29 recuperaciones

En todos los casos se revisaron aproximacion, espera del retroceso, decision y salida. Las observaciones detallan lo que se ve dentro de la ventana y el encadenamiento inmediato. Los angulos son de protocolo, con negativo derecha y positivo izquierda; no son yaw medido.

| Episodio | Inicio AVI | Decision | Angulo | Resultado observado | Detalle |
|---:|---|---|---:|---|---|
'''
lines=[]
for r in q.itertuples():lines.append(f'| {r.id} | {r.avi} | {r.decision} | {r.angle:+.1f} | {r.result} | {r.observation} |')
tail='''

## Resolucion que se desprende de esta evidencia

1. Corregir el STOP con seguimiento ya recuperado (caso 12). La version 3 preparada tiene ese alcance; NO se la presenta como solucion de los otros tres STOP o de todas las oscilaciones.
2. Tratar 5 y29 como un patron separado de 1/12/25: rama izquierda coherente pero historia de nueve cuadros y fragmento posterior al lado contrario. Evaluar una autorizacion acotada con evidencia post-retroceso y fragmento reciente. Bajar globalmente 12 a9 cambiaria tambien otras decisiones y requiere validacion; no esta justificado hacerlo a ciegas.
3. En GAP -> curva y entrega del pivote al seguidor, validar posicion cercana, orientacion y continuidad, no solo negro conectado o dos A/D. :codex-annotation{index="1"} La observacion previa del usuario sobre plateado que puede aparecer negro sigue siendo relevante: ese criterio debe limitarse al cierre de linea y respetar la prioridad del sensor de plateado de Teensy; estas pruebas no validan una entrada a rescate ni un cambio del detector de plateado.
4. Coordinar los complementos dentro de una misma fase de cierre, con el ACK de fin de pivote como evidencia fisica disponible y objetivos de seguimiento explicitos. No aumentar todos los angulos ni retocar todo el seguidor para resolver estos casos aislados.
5. Para atribuir sobre/subgiro a motores, registrar CSV de Teensy sincronizado en la siguiente prueba y comparar el mismo codo con entrada similar. La oscilacion visual y la alternancia de ordenes si estan demostradas; patinamiento, bateria y yaw real no estan medidos aqui.

No se cambio ni se subio codigo al hacer esta revision. Los resultados favorables del replay anterior eran preservacion de comandos sobre imagenes grabadas; no demostraban que la nueva maniobra fisica terminaria bien. Esta distincion corrige el alcance de lo afirmado antes.

## Evidencias para revisar juntos

- [Galeria temporal de los 29 episodios](galeria.html): las 50 laminas, con GS/angulo/accion por imagen.
- [Comparacion de los dos patrones repetidos](comparacion_patrones.jpg).
- [Todas las transiciones de accion](todas_acciones.csv).
- [Mediciones por cuadro](metricas_todos_cuadros.csv).
- [Dictamen por episodio](dictamen_29.csv).
- [Video original](../pista_reenganche_20261031_221132.avi).
'''
(O/'INFORME_29_VISUAL.md').write_text(intro+'\n'.join(lines)+tail,encoding='utf-8')
parts=['<!doctype html><meta charset="utf-8"><title>29 recuperaciones — evidencia visual</title><style>body{font:16px system-ui;margin:24px auto;max-width:1350px;background:#17191e;color:#eee}a{color:#8bc6ff}summary{padding:14px;background:#292d35;cursor:pointer}details{margin:10px 0}img{width:100%;height:auto}p{line-height:1.5}table{border-collapse:collapse;font-size:13px}td,th{padding:5px;border:1px solid #666}</style><h1>29 recuperaciones</h1><p>Secuencias de aproximación, GS4 y hasta cinco segundos reales posteriores; se cortan ante siguiente episodio o cambio de sesión. Un cuadro de cada dos más transiciones. Las etiquetas de tiempo son del AVI a 20 FPS, no el reloj real.</p><p><a href="INFORME_29_VISUAL.md">Informe</a> · <a href="../pista_reenganche_20261031_221132.avi">Video</a> · <a href="todas_acciones.csv">Todas las acciones</a></p>']
for r in q.itertuples():
 parts.append(f'<details id="E{r.id}"><summary>{r.id:02d} · {r.avi} · {html.escape(r.result)}</summary><p>{html.escape(r.observation)}</p>')
 z=s[s.id.eq(r.id)][['start','end','gs','quien','angle_first','angle_last','duration']];parts.append(z.to_html(index=False))
 n=int(inv[inv.id.eq(r.id)].pages.iloc[0])
 for p in range(1,n+1):parts.append(f'<img loading="lazy" src="E{r.id:02d}_{p}.jpg" alt="Episodio {r.id}, secuencia {p}">')
 parts.append('</details>')
(O/'galeria.html').write_text('\n'.join(parts),encoding='utf-8')
print('Informe y galeria guardados; 29 episodios, 50 laminas.')

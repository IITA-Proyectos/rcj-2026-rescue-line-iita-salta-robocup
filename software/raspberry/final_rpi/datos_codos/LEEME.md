# Datos de codos marcados a mano

## `2026-08-26_marcado_a_mano.csv`

**9 969 frames, 400,5 s, 35 marcas humanas.** Benjamin paseando el robot A MANO
por la pista con `codo_vivo.py`, marcando con ESPACIO cada codo que veia.

Columnas: `t, frame, ang, npts, res_c, res_l, dispara, marca_humana`

### QUE DIO, y por que NO es un veredicto sobre el detector

```
                    en las MARCAS      lejos de las marcas
ang     (p50)          56,8                 73,6      <- MAS ALTO donde NO hay codo
res_c   (p50)           3,4                  3,6      <- igual
npts    (p50)           124                  113      <- igual
```

Ninguna variable separa, y el angulo va al reves. Pero **el experimento tiene un
confusor que lo invalida como veredicto**: paseado A MANO el robot queda pegado
a la cinta, que ocupa media pantalla. El pipeline de CAMINO esta hecho para la
vista de MARCHA -cinta angosta, lejana, horizonte arriba-. Con la camara encima
de la cinta la mascara es un manchon y el esqueleto se va por cualquier lado.
Se ve en los PNG: la cadena amarilla no sigue la cinta, va por el borde.

Por eso `ang` da 73 grados de mediana en TODOS lados: no esta midiendo el codo,
esta midiendo como serpentea una mancha grande.

**Estos datos NO refutan el detector de vertice. Refutan MEDIRLO ASI.**

### PARA QUE SIRVEN IGUAL

1. Son el banco de prueba de cualquier detector futuro EN ESTA CONDICION.
2. Muestran que `res <= 2,0` era un filtro mal calibrado: el residuo real es
   3,4-3,6 px. Eso vale para cualquier version.
3. Y dejan escrito el protocolo que NO hay que repetir.

### EL EXPERIMENTO QUE SI VALE, pendiente

Grabar con el robot ANDANDO y marcar despues sobre el video:

    GRABAR=/home/iita/codos.avi python3 main.py

Eso graba la vista de marcha -la misma condicion que `hist.avi`, donde el
detector daba 8 de 8- pero de la pista de hoy. Marcar sobre el video
reproducido, sin apuro y pudiendo retroceder.

**Ojo con el 8 de 8 de hist.avi**: eran 8 casos, elegidos entre eventos que el
propio detector propuso, con umbrales ajustados mirando el resultado. Sigue en
pie, pero necesita una replica independiente antes de creerle.

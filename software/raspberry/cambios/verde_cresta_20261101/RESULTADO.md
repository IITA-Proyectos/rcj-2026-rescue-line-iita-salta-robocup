# VERDE-CRESTA-1: el verde que aparece subiendo lo completa la Pi

Corridas analizadas (1-nov-2026): `corridas/20261101_124912` (12:49), `corridas/20261101_135438` (13:54) y
`corridas/20261101_140905` (14:09, 3 intentos con verde a la derecha y 2 a la izquierda en el cruce de la cresta).

## Qué pasa en cada intento

Giro medido con flujo óptico sobre el fondo (validado: en el piso la maniobra de la Teensy midió 39°, lo que
pide `runAngle`). La "ley normal" es la del piso recalculada desde el video (coincide con lo que mandó el robot
en 4303 cuadros `centroide`, diferencia mediana 0,0–0,1°).

| Corrida | Momento | Lado | Giro de la Teensy | Después | Resultado |
|---|---|---|---|---|---|
| 13:54 | 5:01.60 (Teensy en LLANO) | DER | 39° | la Pi manda −89 a un pedacito de 9 px y completa: 78° en total | **bien** |
| 12:49 | 19:07.5 | DER | — | la Pi manda −88 … −47 sin cortes | **bien** |
| 12:49 | 18:58.3 | DER | — | la Pi encuentra la rama (−89, −87, −86) pero `rampa-cresta-recto` manda 0 entre medio y 45 cuadros seguidos desde 19:00.45 | se perdió (lo reubicaron) |
| 14:09 | 0:12 / 0:28 / 0:47 | DER | 39,5 / 40,7 / 39,5° | `cresta-recto` y `sin-recup` mandan 0 por 2,4–2,6 s. En 0:12 la rama aparece (ley normal −90) y se tira | se fue derecho |
| 14:09 | 1:02 / 1:21 | IZQ | **51,6 / 60°** (pide 39) | la rama izquierda queda cruzada en diagonal, sin tocar abajo: la Pi manda 0 y la ley normal −43 (lado contrario) | zigzag, se fue |
| 13:54 | 4:24.75 / 4:44 | DER | ~50° | zigzag hasta −66/−75 y **el mismo cuadrado se vuelve a ver** (4:26.15, 4:29.65 / 4:45.25, 4:48.70): segunda maniobra, −110/−112° | perdió la línea |
| 13:54 | 5:17.45 | DER | — | 0 por 2,6 s | se fue derecho |
| 12:49 | 20:07 | DER | — | verde repetido en 20:08.40 y 20:11.95 | — |

## Causa

1. El cruce necesita ~78° a la derecha y ~85–90° a la izquierda. La maniobra fija de la Teensy (800 ms + 39°)
   hace la mitad; el resto lo completa la Pi siguiendo la rama. En el piso funciona.
2. Subiendo (o hasta 1,5 s después), los modos de la rampa (`cresta-recto`, `sin-recup`, corte de cresta)
   asumen una cresta recta: tiran el pedacito de rama y mandan 0.
3. A la izquierda la Teensy gira de más (52–60°) y la rama queda en diagonal: la ley normal apunta al lado
   contrario.
4. Después del giro el mismo cuadrado se vuelve a ver y la Teensy repite la maniobra.

### Por qué falla la mayoría y por qué 19:07 sí

Subiendo, la Pi solo sigue cinta **conectada** a la parte de abajo de la imagen; un pedazo suelto lo toma como
"la cinta se metió bajo la trompa en la cresta" y manda 0. Entonces todo depende de si la rama ya está
conectada cuando la Teensy termina su giro. Giro total (flujo óptico) en el que la rama derecha aparece conectada:

| Intento | Rama conectada a los | Resultado |
|---|---|---|
| 12:49 19:07.5 | **36°** (antes de terminar los 39 de la Teensy) | completó y bajó |
| 12:49 18:58.3 | **39–44°**, aparece y desaparece (224, 125, 306, 1 px) | la perdió |
| 13:54 5:01.60 (piso) | **~50°** (pedazo suelto desde los 39°; en el piso la Pi lo sigue) | completó |
| 14:09 derecha ×3 | el robot llegó a **42–46°** sin ver la rama | se fue derecho |

Le falta girar, pero lo que falta cambia según cómo llega el robot. Con 45° fijos se salvaba 18:58 y no los
de las 14:09. A la izquierda la Teensy ya gira 52–60°.

Sobre `RAMPA-TRANSICION-2` (`tras_giro`, instalado antes en la Pi): en 14:09 se activa en la subida, ~3,5 s
antes de cada verde de la derecha (cuadros 166, 492 y 872), porque el travesaño del cruce entra por un
costado. No es lo que hace fallar el verde, pero desde ahí se pierde el suavizado de la subida y aparece el
zigzag de ±50° al acercarse al cruce. A vigilar; este cambio no depende de él.

## Cambio (solo Pi; `verde_cresta.py` + 4 lugares de `main.py`)

Solo si el verde 1 o 2 aparece con la Teensy en SUBE:
1. Se manda ese verde igual que siempre (la Teensy hace su maniobra).
2. Durante 5 s: no se manda otro verde (ni doble) y no se usan el corte de cresta, `cresta-recto`, RECTA ni
   la transición. `RAMPA_SIN_RECUP` queda igual: subiendo nunca se retrocede.
3. Desde 1,4 s (la maniobra de la Teensy termina a 1,45–1,67 s) se manda ±85 (pivote) hacia el lado del verde
   mientras no haya cinta conectada al robot con la ley a menos de 25° del lado contrario. Con 4 cuadros
   seguidos así, suelta y no vuelve. Tope: 0,7 s.

Verde en el piso, bajando o doble: no se arma, todo igual que hoy. `VERDE_CRESTA=1` va en
`_SERVICE_ENV_DEFAULTS`; `VERDE_CRESTA=0` en la línea de comandos lo apaga.

## Verificación

- **Replay de la lógica** (`verificar_verde_cresta.py`): se arma en 11 verdes, los primeros de cada intento
  en la cresta. No se arma en ninguno de los 67 verdes del piso o de bajada. Bloquea los 6 verdes repetidos.
  Gira hacia el lado del verde en los 11 (−85 derecha, +85 izquierda).
  En 18:58 y 19:07.5, donde el robot sí venía girando, suelta al conectarse la cinta (ley −87).
- **Simulador** (`Downloads/SIMULADOR_PI_2026-10-17`, `main.py` completo, cuadros sacados del video; sin el
  cambio repite la etiqueta del robot en el 96,8 % de los cuadros de 14:09), A/B `VERDE_CRESTA=0` contra `1`:
  - 14:09: cambian 469 de 1760 cuadros, todos dentro de las 5 ventanas.
  - 13:54: cambian 340 de 6428. Son las 3 ventanas y 2 tramos justo después de intentos que ya habían fallado
    (robot fuera de la línea, Teensy en LLANO: arranca antes la recuperación del piso porque ya no se repiten
    los verdes). Los 19 verdes del piso deciden igual.
  - 12:49, por tramos (el simulador no imita los obstáculos ni los reposicionamientos, así que cada tramo
    empieza después de uno): 7 tramos de piso, 17 299 cuadros con 42 verdes de piso, bajada y dobles,
    **0 cuadros distintos**. En los 3 tramos de la cresta cambia solo la ventana (más 14 cuadros después de que
    20:07 ya había fallado). En 19:07.5, el que salió bien, manda lo mismo que el robot: −85 donde el robot
    mandó −88 y después la ley normal idéntica (−87 … −47 … +24).
- **Casos sintéticos**: piso no arma, bloqueo de repetidos, espera de la maniobra, no suelta con la cinta del
  lado contrario, suelta con 4 cuadros, tope de 0,7 s, el doble no arma.

**Lo que no se puede probar sin pista:** el replay es a lazo abierto (los cuadros son de un robot que no giró).
Que el giro forzado encuentre la rama hay que verlo en la cresta, a los dos lados. A la izquierda, además,
la Teensy queda en SUBE: vigilar que el pivote no lo corra rampa abajo (HISTORICO_EXPERIMENTOS: "girar en el
lugar lo corre rampa abajo").

Herramientas (en `herramientas/`): `simular_video.py` (el simulador con `SIM_VIDEO=<video>`),
`comparar_ab.py` (dos simulaciones cuadro a cuadro), `giro_lk.py` (giro medido con flujo óptico).

```bash
cd <carpeta con main.py, verde_cresta.py y los módulos de la Pi>
SIM_VIDEO=pista_cresta_verde_20261101_140905.avi VERDE_CRESTA=0 python simular_video.py <carpeta con cuadros.csv> vc0.csv
SIM_VIDEO=pista_cresta_verde_20261101_140905.avi VERDE_CRESTA=1 python simular_video.py <carpeta con cuadros.csv> vc1.csv
python comparar_ab.py vc0.csv vc1.csv
```

## Probar

```bash
sudo systemctl stop iita-robot.service
cd /home/iita/Desktop
N="verde_cresta_$(date +%Y%m%d_%H%M%S)"
GRABAR_CRUDO="/home/iita/crudo_$N" GRABAR="/home/iita/pista_$N.avi" LOG_FILE="/home/iita/pista_$N.log" python3 -u main.py
```

En el log: `[VERDE-CRESTA] VERDE-CRESTA-1 VERDE_CRESTA=1` al arrancar; en cada verde de la cresta
`verde N subiendo: completa la Pi`, y `suelta: cinta conectada (...)`. Si dice `suelta por tope`, no encontró
la rama en 0,7 s. Para comparar en el mismo lugar: `VERDE_CRESTA=0` adelante del `python3`.

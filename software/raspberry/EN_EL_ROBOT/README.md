# EN_EL_ROBOT — volcado literal del Desktop de la Raspberry

**Copiado el 26-ago-2026 de `iita@10.59.132.189:/home/iita/Desktop/*.py`.**

## Qué es esto y qué NO es

Esto es **evidencia**, no código de trabajo. Es lo que estaba corriendo en el
robot ese día, byte por byte. **No editar acá.** Si hay que cambiar algo del
robot, se cambia en `final_rpi/` y se copia a la Pi.

## Por qué existe

Porque el código que corre el robot **no es el del repo**, y nadie lo había
verificado. Al 26-ago:

| archivo | robot | repo (`final_rpi/`) | |
|---|---|---|---|
| `main.py` | 47 442 B | 42 440 B (`Main.py`) | **500 lineas distintas** |
| `parche_planner.py` | 22 753 B | 31 158 B | **1194 lineas distintas** |
| `camthreader.py` | 1 932 B | 3 710 B | 39 lineas — el robot tiene la vieja |
| `trazador.py` | 7 032 B | **no existe** | no estaba versionado en ningun lado |
| `calibrador_verde.py`, `medir_camara.py`, `probar_planner.py`, `seguidor_linea.py` | | | identicos |

El `main.py` del robot es del **22-ago 22:45**; el `Main.py` del repo se toco por
ultima vez el **25-ago**. Divergieron, y el del robot es el mas viejo.

## Lo que esto corrige del traspaso del 26-ago

El traspaso dice que la vision nueva se activa con `VISION_LINEA` y cita
`Main.py:41-44` y `Main.py:887`. **En el robot eso no existe.** El robot no
tiene `vision_linea.py`, ni `camino_principal.py`, ni `nuevo_code_v2.py`, ni
`telemetria_vision.py`.

Son **dos arquitecturas distintas**:

* **repo** → `vision_linea` + `camino_principal` + `nuevo_code_v2` (CAMINO/MONO),
  gate `VISION_LINEA`
* **robot** → `seguidor_linea.Seguidor` + el parche integrado en `main.py`,
  gate `PLANNER`

La **conclusion** del traspaso sigue en pie —hoy corre el `atan2`— pero la
evidencia que citaba era de otro archivo. El `atan2` real esta en
`main.py:1019` (y `:1035`).

## Con que configuracion corre

Todas las palancas estan **apagadas por defecto** (`main.py:15-34`):

```
PLANNER=0      CTRL=atan2     ROI=60        RECUP=0
RETROCEDER=0   GRABAR=""      K_CERCA=40    K_LEJOS=40
RECUP_ANG=75   SATURA_DESDE=70  AREA_MIN=200
```

> **OJO: eso es lo que dice el DEFAULT del archivo.** Si el robot se lanza desde
> un script o un servicio que exporta variables, el default no aplica. **Verificar
> como se lanza `main.py` antes de interpretar cualquier corrida.**

## Palancas escritas y apagadas que el traspaso no registraba

* **`_fila_horizonte()`** — el recorte `black_mask[:60,:]=0` es fijo y, medido
  sobre las corridas del 22-ago, tira 17-20 filas de pista: "casi un tercio del
  ROI utilizable, y justamente las mas lejanas, las unicas que sirven para
  anticipar". Se enciende con `ROI` != `60`.
* **`RETROCEDER`** — al perder la linea, retroceder un paso corto en vez de girar
  a ciegas (`green_state = 4`). Apagado.

Ninguna esta probada en robot. **No encender ninguna sin linea base primero.**

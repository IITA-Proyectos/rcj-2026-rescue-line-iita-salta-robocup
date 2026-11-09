# Verde ya cruzado — 8-nov-2026

**Estado:** instalado en la Pi el 8-nov (`verde_oscuro.py` `107d2f028342f96f…`). **Falta probarlo en pista.**

## Qué pasaba

Un verde a la izquierda de la línea con el travesaño negro **abajo** (el robot ya cruzó) tiene que ignorarse, y el robot giraba a la izquierda.

- La decisión la toma el respaldo `detectar_verde_sombra`, durante 1 a 3 cuadros, cuando el verde entra en la imagen. Alcanza con eso porque la Teensy ejecuta el primer verde que recibe.
- Ese detector exige "negro arriba" (ocupación > 0,32 en las filas 60–90). De lejos, la parte alta del cuadrado se ve tan oscura que entra en la máscara de negro: **el propio cuadrado cuenta como cinta**. Ver `que_veia_el_detector.jpg` (en rojo lo que contó como negro).

## Qué cambia

Solo `verde_oscuro.py`: la función nueva `_verde_ya_cruzado` y 3 líneas en `detectar_verde_sombra`. `main.py` no se toca.

Cuando ese detector ya iba a decidir un verde, mira justo afuera del cuadrado, sin contar lo verdoso como cinta:

- franja de 12 filas **arriba** del cuadrado: cinta < 5 %
- franja de 12 filas **abajo** del cuadrado: cinta > 80 %

Si se cumplen las dos, el verde se ignora y el log dice `[VERDE-SOMBRA] ignorado: cinta abajo y piso arriba`. Si alguna franja no entra en la imagen, la decisión queda como estaba. Ver `regla_verde_ya_cruzado.jpg`.

**Por qué no un filtro de color simple** ("lo verdoso no cuenta como negro"): cambiaría 368 de los 966 cuadros en que decide este detector. En 187 de los 257 verdes el primer cuadro se apoya en esa misma parte oscura, así que se atrasarían verdes buenos.

## Comprobación

Simulador por tramos, comparando contra lo que corre hoy en la Pi (`main.py` 9da00beb, `verde_oscuro.py` 5bdded29):

| Datos | Cuadros | Tramos | Verdes que cambian |
|---|---:|---:|---|
| 13 corridas anteriores | 156.316 | 264 | 7-nov 19:03: 9507, 9508 y 9795 (el verde pedido). 31-oct 19:53: 6573 |
| 8-nov 10:30 (no se usó para armar la regla) | 11.456 | 21 | 2221, 2449, 4985, 5070 y 5143–5145: los 5 giros falsos |

- El cuadro 6573 del 31-oct es **el mismo caso del lado derecho**: cinta abajo y piso arriba. Ver `mismo_caso_a_la_derecha_31oct.jpg`.
- Cresta, bajada y plateado dan los mismos eventos, antes y después.
- De los 37 verdes que ejecutó el robot el 8-nov, cambian solo esos 5 giros falsos (`los_5_giros_falsos_8nov.jpg`).
- Margen: los que se ignoran dan 0 % de cinta arriba y 100 % abajo. El verde bueno más parecido da 17 % y 73 %. En 1059 de 1296 combinaciones de parámetros cambian exactamente los mismos cuadros (`verdes_buenos_mas_parecidos.jpg`).
- Calibrador de ChatGPT: reconoce el archivo, cambia el piso de sombra y la versión calibrada conserva la regla. Sus 111 imágenes de protección deciden igual.

En los tramos con diferencias, los cuadros posteriores también cambian: el simulador es a lazo abierto y el video grabado sigue mostrando el giro que hizo el robot real. Por eso solo vale el primer cuadro distinto.

## Instalación

Con el programa detenido. Base esperada: `verde_oscuro.py` `5bdded29693df6ef…`. Después de instalar: `107d2f028342f96f…`.

```bash
cd /home/iita/Desktop
sha256sum verde_oscuro.py
mkdir respaldo_verde_ya_cruzado_20261108
cp -p verde_oscuro.py respaldo_verde_ya_cruzado_20261108/
```

Copiar el `verde_oscuro.py` de esta carpeta a `/home/iita/Desktop/` y comprobar el sha.

**En la sede:** instalarlo antes de calibrar los verdes, porque el calibrador rechaza un perfil si `verde_oscuro.py` cambió después de hacerlo.

**Volver atrás:**

```bash
cp -p /home/iita/Desktop/respaldo_verde_ya_cruzado_20261108/verde_oscuro.py /home/iita/Desktop/
```

## Qué mirar en pista

Pasar por ese verde varias veces. Tiene que seguir derecho, y el log tiene que mostrar la línea `ignorado` en esas pasadas y en ninguna otra.

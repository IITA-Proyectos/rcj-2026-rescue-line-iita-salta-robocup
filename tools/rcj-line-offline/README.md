# RCJ Rescue Line offline (IITA Salta)

Copia offline del **editor de mapas** y la **tablet del juez** de Rescue Line 2026 del RCJ CMS
(https://intl.rcj.cloud), más un **registro de corridas** para entrenar como si fuera oficial.
Todo corre en el navegador: no necesita servidor ni internet para puntuar.

- **Origen:** [robocup-junior/rcj-rescue-cms](https://github.com/robocup-junior/rcj-rescue-cms), rama `develop/2026`,
  commit `d805502` (licencia MIT, ver `LICENSE-rcj-rescue-cms.txt`). El puntaje, la numeración del recorrido y el
  editor usan el código oficial sin cambios.
- **Uso:** entrenamiento. Cada dispositivo (PC, celular o tablet) puede hacer todo solo: armar mapas, puntuar,
  firmar, ver ranking y estadísticas.

## Cómo abrirla

| Dónde | Cómo |
|---|---|
| **PC con Windows** | Doble clic en `RCJ-Line-Offline.exe` (se arma con `herramientas/construir_exe.py`). Abre `http://localhost:8766`. |
| **Celular / tablet, sin PC** | Abrir en Chrome `https://iita-proyectos.github.io/rcj-2026-rescue-line-iita-salta-robocup/` una vez con internet y tocar **Instalar app**. Después funciona sin internet. |
| **Celular por la WiFi de la PC** | Con el `.exe` abierto, entrar a la dirección que muestra su ventana (`http://IP-de-la-PC:8766`). Si no conecta, permitir la app en el firewall o poner la red como Privada. |
| **Desarrollo** | `python tools/rcj-line-offline/herramientas/servir.py` (sin caché vieja). |

## Flujo de un entrenamiento

1. **Mapas:** importar el JSON exportado del editor oficial (o armarlo en el editor) y marcarlo como terminado.
2. **Inicio → Corrida rápida:** elegir mapa y equipo; abre el juez.
3. **Juez:** pre-chequeo → Iniciar → tocar baldosas, LoPs, víctimas y exit bonus → **Go NEXT**.
4. **Firma:** revisar el desglose, anotar en el comentario la versión del robot/firmware y enviar.
5. **Ranking / Estadísticas / Planillas:** evolución y dónde falla el robot.

La sección **En vivo** del juez muestra el porcentaje del puntaje máximo posible del mapa.

## Datos

Los mapas y las corridas se guardan en el navegador de **cada dispositivo** (IndexedDB), por dirección:
`localhost:8766` y la página de GitHub Pages son registros distintos. No se sincronizan solos.

**Hacé un respaldo al final de cada día:** Configuración → Respaldo → Exportar (y en otro dispositivo, Importar →
Fusionar).

## Opciones (Configuración)

Por defecto la app se comporta como el CMS oficial, salvo estas ayudas para entrenar (se pueden apagar):

- **Recorrido tolerante:** si la línea apunta a una celda vacía, une el empalme para poder puntuar (el juez avisa dónde).
- **Mostrar % del máximo:** sección "En vivo" en juez, firma y vista.
- **Gestos táctiles** en el editor, **cronómetro que sobrevive a una recarga**, **audio**, **pre-chequeo sin fotos**.
- **Corregir errores visuales del CMS** y **solo firma del capitán** (apagadas por defecto).

## Mantenimiento

| Tarea | Comando / archivo |
|---|---|
| Actualizar la lista para usar sin internet (después de cualquier cambio) | `python herramientas/generar_sw.py` |
| Armar el `.exe` | `python herramientas/construir_exe.py --python .venv-exe/Scripts/python.exe` (venv con `pyinstaller`) |
| Volver a copiar archivos del CMS | `herramientas/importar_cms.py` y `herramientas/vendorizar.py` |
| Pruebas | `tests/` (páginas `*.html` para Edge headless y scripts `*-correr.py`) |
| Qué se cambió respecto del CMS y por qué | `cambios/*.md` |
| Versiones y licencias de las librerías | `components/VERSIONES.md` |

La publicación en GitHub Pages la hace `.github/workflows/pages-rcj-line-offline.yml` en cada push a `main` que toque
esta carpeta.

TRASPASO NUEVA SESIÓN — NUEVO CODE RCJ / ROBOLIGA
Fecha del traspaso: 26-ago-2026

Repositorio:  IITA-Proyectos/rcj-2026-rescue-line-iita-salta-robocup
Rama:         collab/nuevo-code
Canal:        issue #138 (Claude ↔ ChatGPT)
Segundo repo: IITA-Proyectos/roboliga-2026-rescate-iita-salta, rama main
              (ahí vive el reparto de tareas del equipo, docs/tareas/)

==========================================================
0. ARRANQUE OBLIGATORIO
==========================================================
NO confíes en memoria de sesiones anteriores.

1. git fetch && checkout collab/nuevo-code && git status
2. LEÉ COMPLETO: TRASPASO-2026-08-26.md en la raíz.
   Es la fuente de verdad del DIAGNÓSTICO y reemplaza al de la
   noche del 25. Si se contradicen, GANA EL DEL 26 — pero decilo
   en voz alta en vez de asumirlo.
3. Verificá que HEAD sea 11376ed o posterior. Si es posterior,
   leé todo lo nuevo antes de tocar nada.
4. git log --oneline c422342..HEAD  → 27 commits, y los mensajes
   son la fuente de verdad de los números.

==========================================================
1. LO PRIMERO QUE TENÉS QUE PREGUNTARLE A BENJAMÍN
==========================================================
El 26-ago a la tarde tuvo el robot. ANTES DE ANALIZAR NADA,
pedile los resultados de HOY-EN-EL-INSTITUTO.md:

  * el ÁNGULO α y el RADIO DE ACUERDO r de los codos donde se sale
  * cuánto AVANZA el robot entre que empieza y termina el codo
    (las dos marcas de cinta en el piso)
  * el HFOV medido contra una pared
  * los CSV de la línea base, y EN QUÉ SEGUNDO se salió cada pasada
  * si corrió el barrido de banco hasta 110 rpm

SIN ESOS DATOS, la sesión se va en repetir análisis que ya están
hechos. CON ellos, varias cosas se deciden en minutos.

Y OJO CON UNA TENSIÓN QUE SIGUE ABIERTA: si el robot AVANZA MUCHO
en el codo (más de 20 cm), entonces los fixes (7) y (8) —que le
dan MÁS avance— van en dirección CONTRARIA y hay que repensarlos.
Ese número decide.

==========================================================
2. LO QUE NO HAY QUE VOLVER A HACER
==========================================================
NUEVE hipótesis muertas en la sección 5 del traspaso, cada una con
el número que la mató. Las tres nuevas de esta sesión:

  * la caída de píxeles como aviso de pérdida: lift 0,03-0,37, o
    sea PEOR QUE EL AZAR. La tasa base de pérdida en 20-40 frames
    ya es 78-95 %.
  * la concentración de curvatura como detector de codo: 16-17
    eventos/min contra un límite de 6, en DOS implementaciones
    independientes.
  * subir LINE_PIVOT_SPEED para abrir la curva: es álgebra, R no
    contiene vel.

Más las trece del traspaso del 25 y las cinco de la noche.
NO las repropongas. Si creés que una merece revisión, leé primero
su commit.

==========================================================
3. LO QUE SÍ QUEDÓ EN PIE
==========================================================
CINCO FLAGS de firmware, TODOS en false y NINGUNO probado en robot.
Orden de prueba: 9 → 8 → 6 → 7, UNO POR VEZ. El (5) NO se usa.
Cada uno con su falsador escrito en priority_fix_flags.h.

LOS CINCO NÚMEROS MEDIDOS:
  diámetro efectivo de rodadura   6,88 cm
  ancho de vía efectivo b_eff    20,9 cm
  factor de apertura              1,15
  lag comando -> giro           60-70 ms
  ancho de la cinta, fila 115   71 px de 160

Y LA CINEMÁTICA, que es de donde sale todo:
  v_centro = vel*(1-rot)      -> en rot = 1 el robot NO AVANZA
  R = b_eff*(1-rot)/(2*rot)   -> el radio NO depende de la velocidad

HOY CORRE EL atan2, NO EL PLANNER. Sin la variable VISION_LINEA el
módulo nuevo no se activa (Main.py:41-44).

==========================================================
4. TU PRIMERA TAREA, según lo que traiga Benjamín
==========================================================
A. SI TRAJO LOS DATOS DEL ROBOT: cerrá con ellos las tres cosas
   que hoy están abiertas por falta de medición —el radio real de
   los codos, si el robot se pasa, y el HFOV— y recalculá las
   constantes de los flags con los números reales.

B. SI NO LOS TRAJO: la tarea que más desbloquea sin robot es
   EL DATASET DE CODOS ETIQUETADOS. Ya frenó DOS intentos y no lo
   arregla otro workflow: hace falta generar contact sheets de
   frames candidatos y que un humano marque cuáles son codos.
   Sin eso, cualquier detector mide TASA DE DISPARO y nunca
   PRECISIÓN.

C. Y LA IDEA MÁS PROMETEDORA SIN PROBAR, para cuando haya dataset:
   medir el rumbo sobre los BORDES de la cinta en vez del eje
   medial. El eje medial de una mancha de 71 px se desvía ±35 px
   sin que la cinta doble nada; los bordes son dos curvas casi
   paralelas y son mucho menos ruidosos.

==========================================================
5. LO QUE TENÉS QUE TENER EN CUENTA
==========================================================
* ANTES DE MEDIR, PREGUNTÁ QUÉ ES EL ARCHIVO QUE ESTÁS LEYENDO.
  hist.avi parecía el frame de la cámara y es un panel DOBLE de
  debug de 640x240 (izquierda cámara, derecha máscara). Medir
  sobre los dos juntos invalidó un análisis entero.

* NO EDITES EL ÁRBOL MIENTRAS HAY AGENTES TRABAJANDO EN ÉL. Un
  agente pisó un fix haciéndole checkout a main.cpp. Commitear
  enseguida lo protege.

* NO PONGAS "ANTE LA DUDA REFUTÁ, DEFAULT A NO SIRVE" en un
  refutador. Salió 9 de 9 NO SIRVE y no informó nada. Pedí "qué
  está bien, qué está mal y qué falta".

* EL REPLAY ES LAZO ABIERTO. Mide percepción, no trayectoria.
  Los CSV del Teensy SÍ son del robot.

* vision_linea NO hace `import camino_principal`: lo carga con
  spec_from_file_location. La instancia buena está en
  vision_linea._CP. Leyendo la otra, USO da todo 0 y parece que
  CAMINO no corre.

* EL HFOV NO ESTÁ CALIBRADO. Afecta a Stanley y a todo lo que
  proyecte al suelo. NO afecta al atan2 ni a la ley de CAMINO,
  que trabajan en píxeles. Hay calibrador: calibrar_camara.py.

* LA SECCIÓN 6 DEL TRASPASO LISTA OCHO ERRORES MÍOS. Leelos: son
  el catálogo de cómo se autoengaña uno midiendo.

* NUNCA uses `git add -A`.

==========================================================
6. REGLAS QUE NO SE NEGOCIAN
==========================================================
1. Falsador escrito ANTES de medir, en números.
2. Umbrales preregistrados en BANDA. Sólo hay conclusión si hay
   plateau.
3. Eventos ÚNICOS, no muestras.
4. Tasa base y placebo desplazado. Un lift sin tasa base no vale.
5. NUNCA inventes un resultado ni una cita.
6. Sanidad física antes de publicar un número.
7. Diagnóstico confirmado ≠ política adoptada.
8. NUNCA propongas limitar la magnitud del steer de la visión.
9. Lo que hoy funciona no puede dejar de funcionar.
10. Español.

Y una del equipo, con dos capturas detrás:
  EL DETECTOR NO PUEDE VOLVER A LAS BIFURCACIONES DEL ESQUELETO.
  Trabajá sobre la cadena que CAMINO ya eligió (`cad` /
  CAP["cadena_pts"]), NUNCA sobre el esqueleto crudo. El 55,9 %
  de los frames tienen bifurcaciones.
  Ver NO-ROMPER-LA-CADENA-UNICA.md.

Usá las skills del repo: seguimiento-de-trayectoria,
geometria-camara-suelo, experimento-falsable, arduino-embebido,
opencv-robotica, robocup-junior.

// ============================================================================
//  TOOLKIT DESAFÍO TÉCNICO — IITA Salta 2026
// ----------------------------------------------------------------------------
//  CÓMO USARLO:
//   - Este archivo NO se compila solo. Es un "ropero" de funciones listas.
//   - El miércoles: copiás SOLO el bloque que necesités y lo pegás en main.cpp,
//     ARRIBA de loop() (después de las variables globales). Después conectás
//     la función con 1 línea en el lugar que indica el PLAYBOOK.
//   - Todas estas funciones usan variables/funciones que YA existen en main.cpp
//     (green_state, robot, runAngle, runTime, runDistance, claw, front_distance,
//     left_distance, right_distance, RanNumber, etc.). Por eso compilan al
//     pegarlas dentro de main.cpp.
//
//  CONVENCIÓN DE GIROS (de tu propio código):
//     runAngle(vel, FORWARD, ANGULO)  ->  ANGULO negativo = IZQUIERDA
//                                          ANGULO positivo = DERECHA
//
//  green_state que manda la RPi:
//     0 = sin verde      1 = verde izq     2 = verde der     3 = doble verde
//     8 = triángulo ROJO (víctima negra/muerta)
//     9 = triángulo VERDE (víctima plateada/viva)
// ============================================================================


// ============================================================================
//  ÍNDICE RÁPIDO DE BLOQUES (Ctrl+F "BLOQUE X")
//   A   Contador de VERDES + paridad ............ Desafío 2 profe (contar verdes)
//   A-2 Contador de INTERSECCIONES + paridad .... Oficial 2024 (contar T/cruces)
//   B   Invertir verdes (izq<->der) ............. Desafío 1.1 / 2025
//   C   Acción línea roja (180/parar/giro) ...... Desafío 1.3 (variante simple)
//   D   Esquive por paridad: LADO (izq/der) ..... Desafío 2.2 / 2024
//   E   Invertir zonas de depósito .............. Desafío 2.3
//   F   Ignorar / forzar un marcador ............ Desafío 1.2 (doble verde) / genérico
//   G   Contador genérico de eventos ............ variaciones
//   H   Cambio global de velocidad .............. variaciones
//   I   Roja SIMPLE vs DOBLE (sensor color) ..... Oficial 2025
//   J   Esquive 2024: ROTAR 360 + lado .......... Oficial 2024
//   K   Reset contadores (LoP) / solo viva ...... 2024 / 2025
//   L   Flujo evacuacion 2025 (solo viva) ....... Oficial 2025
// ============================================================================


// ============================================================================
//  BLOQUE A — CONTADOR DE VERDES Y PARIDAD   (Desafío 2, puntos 1 y base de 2/3)
// ----------------------------------------------------------------------------
//  Cuenta cada marca verde UNA sola vez (por flanco), aunque la RPi mande el
//  mismo green_state muchas veces seguidas.
//  CÓMO CONECTAR: llamá actualizarContadorVerdes(); dentro del while de "linea",
//  justo después de leer_ultrasonidos();  (≈ línea 1624 de main.cpp).
// ============================================================================

// ¿Cuántos verdes suma un doble? Preguntale al árbitro. Cambiá este número.
#define DOBLE_CUENTA_COMO 2     // 2 = "son dos verdes"  |  1 = "es un evento doble"

int  verdes_total = 0;          // total acumulado de verdes vistos
bool verde_estaba = false;      // flanco: para no contar la misma marca 2 veces

bool esMarcaVerde(int gs) { return (gs == 1 || gs == 2 || gs == 3); }

void actualizarContadorVerdes()
{
    if (esMarcaVerde(green_state) && !verde_estaba)
    {
        verdes_total += (green_state == 3) ? DOBLE_CUENTA_COMO : 1;
        verde_estaba = true;
        // Aviso por buzzer para verificar en banco que contó bien:
        digitalWrite(BUZZER, HIGH); delay(40); digitalWrite(BUZZER, LOW);
        Serial.print("[VERDES] total="); Serial.println(verdes_total);
    }
    if (green_state == 0) verde_estaba = false;  // se limpió, listo para la próxima
}

bool verdesPar()  { return (verdes_total % 2) == 0; }   // true = par
bool verdesImpar(){ return (verdes_total % 2) == 1; }   // true = impar


// ============================================================================
//  BLOQUE A-2 — CONTADOR DE INTERSECCIONES (con/sin verde) + PARIDAD  (OFICIAL 2024)
// ----------------------------------------------------------------------------
//  Variante de A para el 2024: cuenta TODAS las intersecciones/dead ends, no solo
//  los verdes. Necesita que la RPi mande green_state=12 en una intersección lisa
//  (ver PLAYBOOK 0.7). Cada intersección/dead end = +1 (un dead end NO suma 2).
//  COOLDOWN: evita doble conteo si la misma intersección manda 12 y luego un verde.
//  CÓMO CONECTAR: actualizarContadorIntersecciones(); en el while "linea", después
//  de leer_ultrasonidos();  (mismo lugar que el Bloque A — usá UNO de los dos).
// ============================================================================

int  inter_total = 0;
bool inter_estaba = false;
unsigned long inter_lastCount = 0;
#define INTER_COOLDOWN_MS 1200   // 2 intersecciones no pueden estar tan cerca — TUNEAR

bool esInterseccion(int gs) { return gs == 1 || gs == 2 || gs == 3 || gs == 12; }

void actualizarContadorIntersecciones()
{
    bool ahora = esInterseccion(green_state);
    if (ahora && !inter_estaba && (millis() - inter_lastCount) > INTER_COOLDOWN_MS)
    {
        inter_total += 1;                 // toda intersección/dead end = +1
        inter_estaba = true;
        inter_lastCount = millis();
        digitalWrite(BUZZER, HIGH); delay(40); digitalWrite(BUZZER, LOW);
        Serial.print("[INTER] total="); Serial.println(inter_total);
    }
    if (green_state == 0) inter_estaba = false;
}

bool interPar()   { return (inter_total % 2) == 0; }    // true = par
bool interImpar() { return (inter_total % 2) == 1; }    // true = impar
int  ladoEsquiveInter() { return interPar() ? 1 : 2; }  // 1 = izquierda, 2 = derecha


// ============================================================================
//  BLOQUE B — INVERTIR VERDES   (Desafío 1, punto 1)
// ----------------------------------------------------------------------------
//  Devuelve el ángulo de giro para una marca verde, con opción de invertir.
//  Negativo = izquierda, positivo = derecha.
//  CÓMO CONECTAR (la forma más simple es cambiar el signo directo en case 6/5,
//  ver PLAYBOOK). Si querés una sola perilla, usá esta función en ambos case:
//      case 6:  runAngle(35, FORWARD, anguloVerde(green_state, INVERTIR_VERDES)); break;
//      case 5:  runAngle(25, FORWARD, anguloVerde(green_state, INVERTIR_VERDES)); break;
// ============================================================================

#define INVERTIR_VERDES true    // poné false para comportamiento normal

double anguloVerde(int gs, bool invertir)
{
    bool izquierda = (gs == 1);          // gs==1 es verde izquierda
    if (invertir) izquierda = !izquierda;
    return izquierda ? -60.0 : 60.0;     // ajustá la magnitud si tu giro normal es otro
}


// ============================================================================
//  BLOQUE C — ACCIÓN PARA LÍNEA / FRANJA ROJA   (Desafío 1, punto 3)
// ----------------------------------------------------------------------------
//  Reemplaza el bloque  if (color_detected == "Rojo") { ... }  del while "linea".
//  Elegí UNA de estas y llamala dentro del if del rojo (después hacé break;).
// ============================================================================

void accionRojo_giro180()
{
    runAngle(30, FORWARD, 180);
    runTime(30, FORWARD, 0, 400);   // avanza un toque para despegarse del rojo
}                                   // (si no, vuelve a detectar rojo y gira de nuevo)

void accionRojo_parar()             // comportamiento normal (meta)
{
    runTime(0, FORWARD, 0, 10000);
}

void accionRojo_giroDerecha()       // ejemplo: rojo = giro 90 a la derecha
{
    runAngle(30, FORWARD, 90);
    runTime(30, FORWARD, 0, 400);
}


// ============================================================================
//  BLOQUE D — ESQUIVE DE OBSTÁCULO SEGÚN PARIDAD   (Desafío 2, punto 2)
// ----------------------------------------------------------------------------
//  En tu case 1 (obstáculo), RanNumber==1 esquiva por izquierda y ==2 por derecha.
//  Esta función reemplaza al random:  par -> izquierda(1)  |  impar -> derecha(2).
//  CÓMO CONECTAR: en case 1, en vez de  RanNumber = random(1,3);  poné:
//      RanNumber = ladoEsquiveParidad();
// ============================================================================

int ladoEsquiveParidad()
{
    // OFICIAL 2024 (contás intersecciones, no verdes): usá ladoEsquiveInter() (Bloque A-2)
    return verdesPar() ? 1 : 2;     // 1 = izquierda, 2 = derecha
}


// ============================================================================
//  BLOQUE E — INVERTIR ZONAS DE DEPÓSITO SEGÚN PARIDAD   (Desafío 2, punto 3)
// ----------------------------------------------------------------------------
//  En el while "rescate": green_state==9 deposita en triángulo verde (víctima
//  plateada) y ==8 en triángulo rojo (víctima negra). Para invertir las zonas
//  cuando la cuenta es impar, remapeás el triángulo ANTES de los if de depósito.
//  CÓMO CONECTAR: justo antes de  if(green_state == 9)...  agregá:
//      int gs_dep = trianguloEfectivo(green_state, verdesImpar());
//  y cambiá  if(green_state == 9)  ->  if(gs_dep == 9)
//            if(green_state == 8)  ->  if(gs_dep == 8)
//  (NO toques los green_state 6/7 de recolección; solo el 8/9 de depósito.)
// ============================================================================

int trianguloEfectivo(int gs, bool invertir)
{
    if (!invertir) return gs;
    if (gs == 8) return 9;
    if (gs == 9) return 8;
    return gs;
}


// ============================================================================
//  BLOQUE F — IGNORAR / FORZAR UN MARCADOR   (genérico, varios desafíos)
// ----------------------------------------------------------------------------
//  Útil si el desafío dice "ignorá X" (ej: doble verde, Desafío 1 punto 2) o
//  "ante X hacé siempre Y". No es función: es el patrón. En el mapeo de acciones
//  del while "linea":
//
//    IGNORAR doble verde (pasar de largo):   if (green_state == 3) action = 7;
//    SIEMPRE girar derecha en intersección:  poné action = 5 fijo, etc.
//
//  Si querés un interruptor de software para ignorar cualquier valor:
// ============================================================================

bool debeIgnorar(int gs, int valorAIgnorar)
{
    return (gs == valorAIgnorar);
}


// ============================================================================
//  BLOQUE G — CONTADOR GENÉRICO DE EVENTOS   (por si piden contar otra cosa)
// ----------------------------------------------------------------------------
//  Mismo truco del flanco, pero parametrizable. Copiá y renombrá si necesitás
//  contar intersecciones, víctimas, obstáculos, etc.
//  Uso:  static bool flag=false; contarPorFlanco(condicion, mi_contador, flag);
// ============================================================================

void contarPorFlanco(bool condicionActiva, int &contador, bool &flagPrevio)
{
    if (condicionActiva && !flagPrevio) { contador++; flagPrevio = true; }
    if (!condicionActiva)               { flagPrevio = false; }
}


// ============================================================================
//  BLOQUE H — CAMBIO GLOBAL DE VELOCIDAD   (genérico)
// ----------------------------------------------------------------------------
//  Si el desafío pide ir más lento/rápido en toda la pista, no toques 20 líneas.
//  Multiplicá la velocidad en el seguidor de línea (case 7).
//  CÓMO CONECTAR: en case 7, reemplazá  robot.steer(velocidadAjustada, FORWARD, steer);
//  por  robot.steer(velocidadAjustada * FACTOR_VEL, FORWARD, steer);
// ============================================================================

#define FACTOR_VEL 1.0     // 0.5 = mitad de velocidad, 1.5 = 50% más rápido


// ============================================================================
//  BLOQUE I — LÍNEA ROJA SIMPLE vs DOBLE con SENSOR DE COLOR  (OFICIAL 2025)
// ----------------------------------------------------------------------------
//  El rojo lo hacés con el SENSOR DE COLOR de abajo (más confiable que la cámara).
//  El sensor ve un punto: para distinguir simple de doble, detectás la SECUENCIA
//  mientras avanzás:  rojo (línea 1) -> blanco (gap ~80mm) -> rojo (línea 2) = DOBLE.
//  Si tras la 1ra roja sigue blanco y no aparece otra = SIMPLE (se ignora).
//  (La RPi además calcula esto y manda green_state 10/11, pero acá usamos el sensor.)
//
//  IMPORTANTE: NO frenes mientras evaluás; seguí siguiendo la línea normal (case 7)
//  y llamá evaluarRojoSensor() cada vuelta. Actuá solo cuando devuelva 2 (doble).
//  CÓMO CONECTAR: reemplazá el bloque  if (color_detected == "Rojo") {...}  por:
//      int rojo = evaluarRojoSensor();
//      if (rojo == 2) { accionRojoDoble_parar(); break; }   // meta (doble)
//      // rojo == 1 (simple): no hacés nada, seguís de largo
// ============================================================================

enum EstadoRojo { ROJO_IDLE, ROJO_CRUZANDO1, ROJO_GAP };
EstadoRojo estadoRojo = ROJO_IDLE;
unsigned long rojoGapStart = 0;
#define ROJO_GAP_MAX_MS 600     // ventana para ver la 2da roja tras el gap — TUNEAR EN BANCO

// 0 = nada aún | 1 = roja SIMPLE confirmada | 2 = roja DOBLE confirmada
int evaluarRojoSensor()
{
    String c = get_color_fast();
    if (c == "Desconocido") return 0;          // sin dato fresco: no cambio de estado
    switch (estadoRojo)
    {
    case ROJO_IDLE:
        if (c == "Rojo") estadoRojo = ROJO_CRUZANDO1;                          // cruzando la 1ra
        return 0;
    case ROJO_CRUZANDO1:
        if (c != "Rojo") { estadoRojo = ROJO_GAP; rojoGapStart = millis(); }   // salí de la 1ra
        return 0;
    case ROJO_GAP:
        if (c == "Rojo") { estadoRojo = ROJO_IDLE; return 2; }                 // 2da roja -> DOBLE
        if (millis() - rojoGapStart > ROJO_GAP_MAX_MS) { estadoRojo = ROJO_IDLE; return 1; }  // SIMPLE
        return 0;
    }
    return 0;
}

void accionRojoDoble_parar()        // meta 2025: parar en la doble roja
{
    runTime(0, FORWARD, 0, 6000);   // quedate quieto 6s para el exit bonus
}


// ============================================================================
//  BLOQUE J — ESQUIVE 2024: ROTAR 360° + LADO POR PARIDAD   (OFICIAL 2024)
// ----------------------------------------------------------------------------
//  El desafío 2024 vale 100 PUNTOS por obstáculo bien resuelto. Pide: al ver un
//  obstáculo, alejarse un poco, rotar 360° sobre el eje (HORARIO si la cuenta de
//  intersecciones es PAR, ANTIHORARIO si es IMPAR) y luego pasar por IZQUIERDA
//  (par) o DERECHA (impar). El 360° es la "prueba" visible de que sabés la paridad.
//
//  OJO: runAngle(360) NO sirve (se normaliza a 0°). El 360 se hace por tiempo.
//  TUNEAR T_360_MS en banco y VERIFICAR el sentido (invertir el signo si gira al revés).
//  CÓMO CONECTAR: al principio del case 1 (obstáculo), antes del esquive:
//      rotar360(interPar());             // 2024: paridad de INTERSECCIONES (Bloque A-2)
//      RanNumber = ladoEsquiveInter();   // par->izq(1), impar->der(2) por intersecciones
// ============================================================================

#define T_360_MS 1700      // ms para una vuelta completa a vel 30 — TUNEAR EN BANCO

void rotar360(bool horario)
{
    double s = horario ? -1.0 : 1.0;   // -1 = horario (verificar en banco; invertir si hace falta)
    runTime(30, FORWARD, s, T_360_MS);
    robot.steer(0, FORWARD, 0);
}


// ============================================================================
//  BLOQUE K — RESET DE CONTADORES (tras LoP) y SOLO VÍCTIMA VIVA   (2024/2025)
// ----------------------------------------------------------------------------
//  2024: "el conteo se reinicia después de un LoP". Tras un LoP, el robot vuelve
//  a la salida, así que reseteá el contador en el bloque de reinicio (switch
//  apagado) de loop().
//  CÓMO CONECTAR: en loop(), dentro del if (digitalRead(32) == 1) { ... }, sumá:
//      verdes_total = 0; verde_estaba = false;
//
//  2025: solo importa la víctima VIVA (plateada). Las negras no suman ni restan.
//  Para ignorar la recolección de negras (green_state == 7) en el while "rescate":
//      if (SOLO_VICTIMA_VIVA && green_state == 7) { green_state = 0; }  // saltea negra
// ============================================================================

#define SOLO_VICTIMA_VIVA false   // 2025: poné true para ignorar víctimas negras


// ============================================================================
//  BLOQUE L — FLUJO DE EVACUACIÓN 2025 (solo víctima viva + depósito afuera)
// ----------------------------------------------------------------------------
//  CLAVE (lo que te hacía dudar): NO necesitás un estado nuevo. Tu while "linea"
//  YA llama serialEvent5() y get_color_fast() en CADA vuelta -> nunca dejás de
//  detectar. Solo agregás una REACCIÓN con un flag.
//
//  Mapeo sobre tus estados (rutina) actuales:
//   "linea"      -> cinta plateada (sensor) -> rutina="rescate"   (igual que hoy)
//   "rescate"    -> agarrás SOLO la plateada (gs6), ignorás la negra (gs7),
//                   llevando_victima=true, rutina="evacuacion"
//   "evacuacion" -> buscás la rampa: tu procesarColorEvacuacion() ve la cinta
//                   NEGRA -> accionNegro() YA te devuelve a rutina="linea"  (reuso)
//   "linea"+flag -> seguís hasta ver la zona verde (gs9) -> parás y depositás.
// ============================================================================

bool llevando_victima = false;   // true mientras cargás la víctima viva

// (1) En el while "rescate", usá ESTO en vez de la lógica de 2 pelotas/depósito:
void rescate2025()
{
    if (green_state == 6)        // plateada (viva) centrada y cerca (la manda la RPi)
    {
        // --- reusá TU secuencia de agarre de plateada (gs6 actual) ---
        claw.lower();  nonBlockingDelay(1000);
        claw.close();  nonBlockingDelay(1000);
        claw.lift();   nonBlockingDelay(1000);   // levantada >5s = 45 pts
        // -------------------------------------------------------------
        llevando_victima = true;
        if (!evacuacion_iniciada) { Serial5.write(247); evacuacion_iniciada = true; evacuacion_straight = false; }
        rutina = "evacuacion";   // ahora buscás la rampa de salida (cinta negra)
    }
    // green_state == 7 (negra): no hacés nada -> la ignorás
}

// (2) En el while "linea", ARRIBA (después de get_color_fast / leer_*), agregá:
//        if (llevando_victima && green_state == 9) depositarVivaYSeguir();
void depositarVivaYSeguir()
{
    robot.steer(0, FORWARD, 0);
    runTime(0, FORWARD, 0, 500);
    claw.lower();  nonBlockingDelay(800);
    claw.open();   nonBlockingDelay(800);    // soltás la víctima en la zona verde (30 pts)
    claw.lift();
    runTime(30, BACKWARD, 0, 300);           // te despegás
    llevando_victima = false;
    green_state = 0;                          // evita re-disparo con valor stale
}

// (3) Al SALIR de la zona (tu accionNegro(), cuando ve la cinta negra de la rampa)
//     avisá a la RPi que arranque a mirar la zona verde: mandá 246 si cargás víctima.
//     En accionNegro(), cambiá  Serial5.write(249);  por:
//        Serial5.write(llevando_victima ? 246 : 249);

//  OJO — 2 cosas en la RPi para que esto funcione:
//   A) Durante el agarre, que choose_stable_target apunte SOLO a la clase 0
//      (silver). Hoy apunta a la más estable de cualquier color.
//   B) Ver la zona verde MIENTRAS seguís la línea: el YOLO hoy solo corre dentro
//      de modo_rescate. Solución = hilos de YOLO globales + leer result_q sin
//      bloquear (get_nowait) en el estado de línea, y mandar gs9 al ver la clase 3.
//      Detalle completo en PLAYBOOK sección 0.8. (El gs9 lo dispara el código 246.)


// ============================================================================
//  NOTA SOBRE COSAS QUE SÍ TOCAN LA RPi (visión) — DIFÍCILES
// ----------------------------------------------------------------------------
//  Estas NO se resuelven en la Teensy. Si aparecen, hay que editar Main.py en la
//  RPi y recalibrar (caro en tiempo). Tenelas identificadas pero como último
//  recurso:
//   - Línea de otro color / seguir en reversa.
//   - Detectar/ignorar víctimas falsas (señuelos) — nuevo en reglas 2026.
//   - Detectar un color/marcador nuevo que tu APDS no tenga calibrado.
// ============================================================================

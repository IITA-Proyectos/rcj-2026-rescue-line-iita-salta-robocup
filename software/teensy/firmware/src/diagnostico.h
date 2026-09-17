#pragma once
// ============================================================================
//  diagnostico.h - REGISTRADOR CSV DE ALTA FRECUENCIA  (herramienta, no robot)
//
//  QUE ES ESTE ARCHIVO. Todo el registrador de 200 Hz que antes vivia en el
//  medio de main.cpp. Se saco de ahi el 2026-09-06 para que main.cpp sea SOLO
//  el robot: aca no hay una sola linea que se ejecute en competencia.
//
//  CUANDO ENTRA AL BINARIO: si MODO_DIAGNOSTICO vale 1. Y ATENCION, PORQUE ES
//  CONTRAINTUITIVO: el entorno `competencia` -el que se flashea para la pista-
//  LO PRENDE. Es el binario con el que se tuneo el movimiento que hoy funciona.
//  Con MODO_DIAGNOSTICO = 0 (entorno `telemetria`) todo esto desaparece en el
//  preprocesador: cero instrucciones, cero RAM, ni el anillo de 1024 muestras,
//  y el lazo corre mas rapido -que ES un cambio de comportamiento-.
//
//  COMO SE USA:
//      pio run --target upload        (ya viene prendido: entorno `competencia`)
//      python tools/registrar_diagnostico.py COM7 curva1.csv
//      python tools/analizar_diagnostico.py curva1.csv
//
//  ---------------------------------------------------------------------------
//  ATENCION AL ORDEN DEL #include, PORQUE ESTE HEADER NO ES AUTOSUFICIENTE.
//
//  Lee globales que declara main.cpp (bno, robot, fl/fr/bl/br, speed,
//  g_rx_steer, g_last_rx_ms, serial_frames_rx, g_line_branch) y macros de
//  drivebase.h (TICKS_VUELTA, MOTO_KS, MOTO_KV, MOTO_PISO, MOTO_PWM_ANTICOAST,
//  FIX_LAZO_MOTOR) y del panel de configuracion de main.cpp (LINE_*).
//
//  Por eso se incluye EN EL MEDIO de main.cpp, despues de declarar todo eso, y
//  no arriba con el resto de los #include. Si lo movés arriba, no compila.
//  Es a proposito: la alternativa era duplicar main.cpp en un archivo aparte, y
//  una copia se despega del original en una semana - ahi el diagnostico deja de
//  describir al robot que compite, que es justo lo unico que tiene que hacer.
//  ---------------------------------------------------------------------------
//
//  QUE MIDE Y POR QUE 200 Hz: la telemetria JSON manda a 10 Hz, el PID corre a
//  50 Hz y el desplome de PWM de la rueda interna dura decenas de milisegundos.
//  A 10 Hz se ve el antes y el despues, nunca el momento en que pasa.
//
//  DOS MACROS son toda la interfaz con main.cpp:
//      DIAG_SETUP()   una vez, al principio de setup()
//      DIAG_TICK()    en cada punto donde el programa pueda quedarse un rato:
//                     loop(), el lazo de linea, el lazo de idle y
//                     serviceMotionBackgroundTasks() (por donde pasan los cinco
//                     bucles bloqueantes runTime/runAngle/runDistance/...).
//  Las dos son VACIAS en competencia, asi que sus llamadas se pueden dejar
//  escritas en main.cpp sin costo alguno.
// ============================================================================

// Con DIAG_PUERTO=1 el CSV del registrador sale por Serial8, que es el MISMO
// cable por el que la telemetria manda su JSON. Los dos flujos se entrelazan y
// el resultado no es ni un CSV ni un JSON: es basura que ninguna herramienta
// avisa que esta mal. Se rompe el build antes de que pase.
#if defined(DIAG_PUERTO) && DIAG_PUERTO && TELEMETRIA
#error "DIAG_PUERTO=1 y TELEMETRIA=1 comparten Serial8: los dos flujos se mezclan. Dejar uno solo."
#endif

// ============================================================================
//  MODO_DIAGNOSTICO - registrador de alta frecuencia de la REACCION DE MOTORES
//
//  QUE ES: un SEGUNDO BINARIO construido desde ESTE MISMO archivo (entorno
//  `diagnostico` en platformio.ini). A proposito NO es una copia de main.cpp:
//  una copia se despega del original en una semana y ahi el diagnostico deja de
//  describir al robot que compite. Con MODO_DIAGNOSTICO=0 (entorno `telemetria`)
//  nada de esto entra al binario.
//
//  POR QUE HACE FALTA: la telemetria JSON manda a 10 Hz. El PID corre a 50 Hz
//  (SampleTime = 20 ms) y el desplome de PWM de la rueda interna dura decenas
//  de milisegundos. Muestrear a 10 Hz es submuestrear el fenomeno: se ve el
//  antes y el despues, nunca el momento en que pasa. Aca se muestrea a 200 Hz,
//  cuatro veces el lazo de control.
//
//  COMO NO PIERDE MUESTRAS EN LOS GIROS: runTime/runAngle/runDistance son
//  bucles BLOQUEANTES - el loop() no vuelve a correr hasta que terminan. Por eso
//  el muestreo se engancha ADEMAS en serviceMotionBackgroundTasks(), que es el
//  unico punto por el que pasan los cinco bucles bloqueantes. Y si aun asi
//  quedara un hueco NO se disimula: cada linea lleva su `dt` real medido y hay
//  un contador `drop` de muestras perdidas por anillo lleno.
//
//  SALIDA: una linea CSV por muestra, con cabecera, para que el archivo se
//  explique solo. Se graba con tools/registrar_diagnostico.py.
// ============================================================================
#if MODO_DIAGNOSTICO

// Puerto de salida:
//   0 = USB del Teensy (por defecto). No hay que cablear nada y no hay limite de
//       ancho de banda: es el que conviene para el banco de motores.
//   1 = Serial8 a DIAG_BAUD, para correr SUELTO en la pista con un adaptador
//       USB-TTL colgado del TX. OJO: la ESP32 de telemetria espera JSON y esto
//       es CSV, asi que en modo diagnostico la ESP32 no se usa.
#ifndef DIAG_PUERTO
#define DIAG_PUERTO 0
#endif
#define DIAG_BAUD       921600
#define DIAG_HZ         200
#define DIAG_PERIODO_US (1000000UL / DIAG_HZ)
#define DIAG_RING       1024     // 1024 a 200 Hz = 5 s. Mas margen que antes porque

#if DIAG_PUERTO
  #define DIAG_OUT Serial8
#else
  #define DIAG_OUT Serial
#endif

struct DiagMuestra {
    uint32_t us;          // micros() de la muestra
    uint16_t dt;          // us desde la muestra anterior (delata los huecos)
    int16_t  rxsteer;     // el ANGULO que llego de la RPi, x1000
    uint8_t  rxspeed;
    int16_t  rxage;       // ms desde la ultima trama completa (-1 = nunca llego)
    uint32_t rxf;         // contador de tramas completas (uint16 daba la vuelta a los ~22 min)
    int16_t  rot;         // DriveBase::_rotation x1000
    int16_t  ls, rs;      // consignas por lado, ya calculadas
    uint8_t  ddir;        // direccion pedida
    int16_t  ram;         // rama del case 7. TIENE QUE SER CON SIGNO: vale -1
                          // cuando el giro lo pidio un runAngle/runTime y no la
                          // vision. Con uint8_t el -1 llegaba como 255 y el
                          // analizador no reconocia ninguno de los dos casos.
    uint8_t  dir[4];      // FL FR BL BR - sentido COMANDADO
    int16_t  set[4];      // consigna de RPM por rueda
    int16_t  rpm[4];      // RPM medida (MAGNITUD: el encoder no informa sentido)
    uint8_t  pwm[4];      // esfuerzo aplicado
    int32_t  enc[4];      // pulseCount
    uint32_t tog[4];      // toggles del pin de direccion. uint16 daba la vuelta
                          // en ~33 s a la frecuencia del loop, y un delta negativo
                          // apagaba la deteccion C justo en la rueda que oscila.
    uint32_t raw[4];      // flancos CRUDOS: movimiento fisico sin suposiciones
    int16_t  yaw, pit;    // x10
    int16_t  gx, gy, gz;  // velocidad angular REAL x10
    uint32_t drop;        // perdidas AL MOMENTO DE LA MUESTRA. Antes se leia la
                          // global al DRENAR, hasta 2,5 s despues: la columna
                          // quedaba estampada sobre la fila equivocada.
};

// el DRENAJE depende de que el lazo principal lo visite, y el lazo de linea
// puede tardar decenas de ms por vuelta.
DMAMEM DiagMuestra diagRing[DIAG_RING];
IntervalTimer diagTimer;
// Productor unico (el ISR del timer) escribe diagCabeza; consumidor unico
// (diagDrenar, desde el lazo) escribe diagCola. Con indices de 16 bits
// alineados eso es atomico en un Cortex-M7: no hace falta candado.
volatile uint16_t diagCabeza = 0, diagCola = 0;
volatile unsigned long diagDropIsr = 0;
unsigned long diagDrop = 0;
static uint32_t diagUltimaUs = 0;
// Cache de la IMU: la lectura es I2C (~2 ms) y NO puede correr a 200 Hz. El
// BNO055 se actualiza a 100 Hz internamente, asi que refrescarla a 50 Hz no
// pierde informacion y saca el I2C del camino del muestreo.
static int16_t diagYaw = 0, diagPit = 0, diagGx = 0, diagGy = 0, diagGz = 0;

static inline int16_t diagSat(double v)
{
    if (isnan(v) || isinf(v)) return 0;
    if (v >  32000.0) return  32000;
    if (v < -32000.0) return -32000;
    return (int16_t)v;
}

void diagRefrescarImu()
{
    static unsigned long ult = 0;
    if (millis() - ult < 20) return;   // 50 Hz
    ult = millis();
    sensors_event_t ev;
    bno.getEvent(&ev);
    diagYaw = diagSat(ev.orientation.x * 10.0);
    diagPit = diagSat(ev.orientation.y * 10.0);
    imu::Vector<3> g = bno.getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);
    diagGx = diagSat(g.x() * 10.0);
    diagGy = diagSat(g.y() * 10.0);
    diagGz = diagSat(g.z() * 10.0);
}

// Toma una foto si ya paso el periodo. SOLO copia valores que ya estan en RAM:
// nada de I2C ni de cuentas, para que el costo sea despreciable y no altere el
// comportamiento que estamos tratando de medir.
// ============================================================================
//  MUESTREO POR TIMER DE HARDWARE - NO colgado del lazo.
//
//  POR QUE: el seguimiento de linea corre dentro de un while(rutina=="linea")
//  que esta ADENTRO de loop(), y el case 7 NO llama a
//  serviceMotionBackgroundTasks(). O sea que ningun enganche del lazo se
//  alcanzaba durante una curva: el registrador grababa CERO muestras justo
//  del fenomeno que se quiere medir. Con el timer, 200 Hz pase lo que pase.
//
//  Este ISR SOLO COPIA valores que ya estan en RAM: nada de I2C, nada de
//  formateo, nada que pueda bloquear. Formatear y escribir al puerto sigue
//  en el lazo (diagDrenar), que es donde puede esperar.
//
//  Lectura rota de un double mientras el lazo lo escribe: posible. Da un
//  valor absurdo que diagSat acota. Es dato de diagnostico, no de control:
//  se prefiere eso a frenar el lazo con noInterrupts() 200 veces por segundo.
// ============================================================================
void diagMuestrear()
{
    uint32_t ahora = micros();
    if (diagUltimaUs && (ahora - diagUltimaUs) < DIAG_PERIODO_US) return;
    uint32_t dt = diagUltimaUs ? (ahora - diagUltimaUs) : 0;
    diagUltimaUs = ahora;

    uint16_t sig = (uint16_t)((diagCabeza + 1) % DIAG_RING);
    if (sig == diagCola) { diagDropIsr++; return; }   // anillo lleno: se anota, no se miente

    DiagMuestra &m = diagRing[diagCabeza];
    m.us = ahora;
    m.dt = (dt > 65535UL) ? 65535 : (uint16_t)dt;
    m.rxsteer = diagSat(g_rx_steer * 1000.0);   // lo que MANDO la RPi, no la global pisada
    m.rxspeed = (uint8_t)constrain(speed, 0.0, 255.0);
    long edad = g_last_rx_ms ? (long)(millis() - g_last_rx_ms) : -1L;
    m.rxage = (edad > 32000L) ? 32000 : (int16_t)edad;
    m.rxf = (uint32_t)serial_frames_rx;
    m.rot = diagSat(robot._rotation * 1000.0);
    m.ls = diagSat(robot._leftspeed);
    m.rs = diagSat(robot._rightspeed);
    m.ddir = (uint8_t)robot._direction;
    m.ram = (int16_t)g_line_branch;
    Moto *mt[4] = { &fl, &fr, &bl, &br };
    for (int i = 0; i < 4; i++)
    {
        m.dir[i] = (uint8_t)mt[i]->_dir;
        m.set[i] = diagSat(mt[i]->_rpm);
        m.rpm[i] = diagSat(mt[i]->_realrpm);
        m.pwm[i] = (uint8_t)constrain(mt[i]->_pwmTotal, 0.0, 255.0);   // el que sale por el pin
        m.enc[i] = (int32_t)mt[i]->pulseCount;
        m.tog[i] = (uint32_t)mt[i]->dirToggles;
        m.raw[i] = (uint32_t)mt[i]->pulsesRaw;
    }
    m.yaw = diagYaw; m.pit = diagPit;
    m.gx = diagGx; m.gy = diagGy; m.gz = diagGz;
    m.drop = diagDrop + diagDropIsr;
    diagCabeza = sig;
}

// Vacia el anillo hacia el puerto SIN bloquear: escribe solo mientras haya lugar
// en el buffer de salida. Si no lo hay, la muestra espera en el anillo. Nunca
// frena el control - misma regla que la telemetria JSON.
// SENAL FISICA de que el registro esta vivo: el LED de la placa parpadea con
// cada volcado. Sin esto, un USB sin nadie leyendo deja availableForWrite() en 0,
// el anillo se llena, diagDrop sube y NO SE GRABA NADA - con el robot corriendo
// normal y sin ninguna pista hasta abrir el archivo a la noche.
// Si ademas se estan perdiendo muestras, el parpadeo pasa a ser rapido.
void diagLatido(bool perdiendo)
{
    static unsigned long ult = 0;
    static bool on = false;
    unsigned long periodo = perdiendo ? 60 : 400;
    if (millis() - ult < periodo) return;
    ult = millis();
    on = !on;
    digitalWriteFast(LED_BUILTIN, on);
}

void diagDrenar()
{
    // 384 = el largo maximo de una linea. Comparar contra un numero magico mas
    // chico dejaba pasar escrituras que despues bloqueaban, o -con el buffer de
    // 40 B de un Serial de Teensy 4- no dejaba pasar ninguna.
    unsigned long escritas = 0;
    while (diagCola != diagCabeza && DIAG_OUT.availableForWrite() >= 384)
    {
        const DiagMuestra &m = diagRing[diagCola];
        char l[384];   // peor caso medido ~321 B: con 256 truncaba en silencio
        int n = snprintf(l, sizeof(l),
            "%lu,%u,%lu,%d,%u,%d,%lu,%d,%d,%d,%u,%d,"
            "%u,%d,%d,%u,%ld,%lu,%lu,"
            "%u,%d,%d,%u,%ld,%lu,%lu,"
            "%u,%d,%d,%u,%ld,%lu,%lu,"
            "%u,%d,%d,%u,%ld,%lu,%lu,"
            "%d,%d,%d,%d,%d\n",
            (unsigned long)m.us, m.dt, (unsigned long)m.drop, m.rxsteer, m.rxspeed, m.rxage,
            (unsigned long)m.rxf, m.rot, m.ls, m.rs, m.ddir, m.ram,
            m.dir[0], m.set[0], m.rpm[0], m.pwm[0], (long)m.enc[0], (unsigned long)m.tog[0], (unsigned long)m.raw[0],
            m.dir[1], m.set[1], m.rpm[1], m.pwm[1], (long)m.enc[1], (unsigned long)m.tog[1], (unsigned long)m.raw[1],
            m.dir[2], m.set[2], m.rpm[2], m.pwm[2], (long)m.enc[2], (unsigned long)m.tog[2], (unsigned long)m.raw[2],
            m.dir[3], m.set[3], m.rpm[3], m.pwm[3], (long)m.enc[3], (unsigned long)m.tog[3], (unsigned long)m.raw[3],
            m.yaw, m.pit, m.gx, m.gy, m.gz);
        if (n > 0 && n < (int)sizeof(l)) DIAG_OUT.write((const uint8_t *)l, n);
        else diagDrop++;   // no entro: se cuenta como perdida, no se pierde callado
        diagCola = (uint16_t)((diagCola + 1) % DIAG_RING);
        escritas++;
    }
    static unsigned long dropPrev = 0;
    unsigned long dropAhora = diagDrop + diagDropIsr;
    diagLatido(dropAhora != dropPrev);
    dropPrev = dropAhora;
}

// La cabecera se REEMITE cada 2 s: asi el stream se explica solo desde
// cualquier punto en el que uno se enganche. Cuesta ~300 B cada 2 s contra los
// 40 kB/s de datos (0,4%). Abrir el USB no resetea un Teensy 4.1, asi que sin
// esto el que arranca el registrador tarde se pierde la unica cabecera que hubo.
static const char *DIAG_CABECERA =
    "us,dt,drop,rxsteer,rxspeed,rxage,rxf,rot,ls,rs,ddir,ram,"
    "fl_dir,fl_set,fl_rpm,fl_pwm,fl_enc,fl_tog,fl_raw,"
    "fr_dir,fr_set,fr_rpm,fr_pwm,fr_enc,fr_tog,fr_raw,"
    "bl_dir,bl_set,bl_rpm,bl_pwm,bl_enc,bl_tog,bl_raw,"
    "br_dir,br_set,br_rpm,br_pwm,br_enc,br_tog,br_raw,"
    "yaw,pit,gx,gy,gz";

// Reemite cabecera + procedencia. El `ult` se actualiza DESPUES del guard:
// si no habia lugar en el buffer, se reintenta en el proximo tick en vez de
// quemar la ventana entera de 2 s.
// La procedencia viaja CON cada cabecera. Si solo se emitiera al arrancar, el
// que engancha el registrador tarde graba un CSV sin saber con que binario se
// hizo, y entonces no sirve para comparar historico contra fix.
// Emite TODOS los flags que cambian comportamiento. Antes solo salia `lazo=`,
// asi que dos CSV podian diferir en el arbol del case 7, en las ganancias del
// feedforward o en el puerto y parecer perfectamente comparables. Un A/B entre
// corridas que difieren en mas de una cosa no es atribuible.
void diagProcedencia()
{
    DIAG_OUT.print("# hz="); DIAG_OUT.print(DIAG_HZ);
    DIAG_OUT.print(" ticks_vuelta="); DIAG_OUT.print(TICKS_VUELTA);
    DIAG_OUT.print(" fix_lazo="); DIAG_OUT.print(FIX_LAZO_MOTOR);
    DIAG_OUT.print(" fix_curva=1");   // horneado: la rampa continua es el unico camino
    DIAG_OUT.print(" ks="); DIAG_OUT.print(MOTO_KS, 2);
    DIAG_OUT.print(" kv="); DIAG_OUT.print(MOTO_KV, 3);
    DIAG_OUT.print(" piso="); DIAG_OUT.print(MOTO_PISO, 2);
    DIAG_OUT.print(" anticoast="); DIAG_OUT.print(MOTO_PWM_ANTICOAST, 1);
    DIAG_OUT.print(" diag_puerto="); DIAG_OUT.print(DIAG_PUERTO);
    // `lazo=` se mantiene por compatibilidad con los CSV ya grabados
    DIAG_OUT.print(" lazo="); DIAG_OUT.print(FIX_LAZO_MOTOR ? "nuevo" : "historico");
    // Las constantes del case 7. Sin esto, dos CSV grabados con ganancias o
    // umbrales distintos son indistinguibles: el 22-ago se grabaron diez y
    // despues no se pudo atribuir ninguna diferencia a ninguna constante.
    DIAG_OUT.print(" gain="); DIAG_OUT.print(LINE_STEER_GAIN, 2);
    DIAG_OUT.print(" rot_exp="); DIAG_OUT.print(LINE_ROT_EXP, 2);
    DIAG_OUT.print(" piv_entra="); DIAG_OUT.print(LINE_PIVOTE_ENTRA, 2);
    DIAG_OUT.print(" piv_sale="); DIAG_OUT.print(LINE_PIVOTE_SALE, 2);
    DIAG_OUT.print(" piv_vel="); DIAG_OUT.print(LINE_PIVOT_SPEED);
    DIAG_OUT.print(" piv_max_ms="); DIAG_OUT.print(LINE_PIVOTE_MAX_MS);
    DIAG_OUT.print(" piv_confirma_ms="); DIAG_OUT.print(LINE_PIVOTE_CONFIRMA_MS);
    DIAG_OUT.print(" freno_del="); DIAG_OUT.print(LINE_FRENO_DELANTERO);
    DIAG_OUT.print(" freno_f="); DIAG_OUT.print(LINE_FRENO_FACTOR, 2);
    DIAG_OUT.print(" freno_rm="); DIAG_OUT.print(LINE_FRENO_ROT_MULT, 2);
    DIAG_OUT.print(" freno_st="); DIAG_OUT.print(LINE_FRENO_STEER, 2);
    DIAG_OUT.print(" freno_vel="); DIAG_OUT.print(LINE_FRENO_VEL);
    DIAG_OUT.print(" recta_f="); DIAG_OUT.print(LINE_RECTA_FACTOR, 2);
    DIAG_OUT.print(" commit=");
#ifdef TLM_COMMIT
    DIAG_OUT.println(TLM_COMMIT);
#else
    DIAG_OUT.println("nogit");
#endif
}

void diagCabeceraPeriodica()
{
    static unsigned long ult = 0;
    if (millis() - ult < 2000) return;
    // 520 y no 420: la procedencia ya son ~378 B y los campos del codo suman
    // ~58 mas. Con 420 la cabecera periodica dejaria de emitirse EN SILENCIO
    // y se perderia la procedencia a mitad de corrida.
    if (DIAG_OUT.availableForWrite() < 520) return;   // cabecera + procedencia
    ult = millis();
    diagProcedencia();
    DIAG_OUT.println(DIAG_CABECERA);
}

void diagInicio()
{
#if DIAG_PUERTO
    DIAG_OUT.begin(DIAG_BAUD);
    // El buffer TX por defecto de un Serial de Teensy 4 son 40 bytes: con eso
    // el guard de diagDrenar NUNCA se cumple y no se escribe una sola linea.
    static uint8_t txbuf[4096];
    DIAG_OUT.addMemoryForWrite(txbuf, sizeof(txbuf));
#endif
    DIAG_OUT.println("# RescueBot IITA - diagnostico de reaccion de motores");
    diagProcedencia();
    DIAG_OUT.println(DIAG_CABECERA);
    // 200 Hz DE VERDAD, independientes de donde este parado el programa.
    diagTimer.begin(diagMuestrear, DIAG_PERIODO_US);
    diagTimer.priority(200);   // por debajo de las ISR de encoder, que son EL dato
}

// El muestreo NO esta aca: lo hace diagTimer a 200 Hz reales. Aca queda lo que
// SI puede esperar y lo que NO puede correr en un ISR (I2C de la IMU, formateo
// de texto, escritura al puerto).
#define DIAG_TICK()  do { diagRefrescarImu(); diagCabeceraPeriodica(); diagDrenar(); } while (0)
// Enganche de setup(). Abre el USB y arranca el timer de 200 Hz.
#define DIAG_SETUP() do { Serial.begin(115200); diagInicio(); } while (0)
#else
// Con MODO_DIAGNOSTICO=0 (entorno `telemetria`) las dos macros son
// vacias: no queda ni una instruccion, ni un byte de RAM, ni el anillo.
#define DIAG_TICK()  do { } while (0)
#define DIAG_SETUP() do { } while (0)
#endif // MODO_DIAGNOSTICO

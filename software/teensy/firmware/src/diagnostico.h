#pragma once
// diagnostico.h - registrador CSV de 200 Hz de la reaccion de motores.
// Entra si MODO_DIAGNOSTICO=1, y el entorno `competencia` LO PRENDE: es el binario con el que se
// tuneo el movimiento. Apagarlo (entorno `telemetria`) hace que el lazo corra mas rapido.
// Uso: pio run -t upload; python tools/registrar_diagnostico.py COM7 x.csv;
//      python tools/analizar_diagnostico.py x.csv
// No es autosuficiente: lee globales de main.cpp (bno, robot, fl/fr/bl/br, speed, g_rx_steer,
// g_last_rx_ms, serial_frames_rx, g_line_branch), macros MOTO_*/LINE_* y rampa.h, asi que se incluye en el
// medio de main.cpp, despues de declararlas. Movido arriba no compila.
// 200 Hz porque el PID corre a 50 Hz y el desplome de PWM dura decenas de ms.
// Interfaz: DIAG_SETUP() al principio de setup(); DIAG_TICK() en los lazos.

// DIAG_PUERTO=1 saca el CSV por Serial8, el mismo cable que la telemetria JSON: no pueden ir juntos.
#if defined(DIAG_PUERTO) && DIAG_PUERTO && TELEMETRIA
#error "DIAG_PUERTO=1 y TELEMETRIA=1 comparten Serial8: los dos flujos se mezclan. Dejar uno solo."
#endif

#if MODO_DIAGNOSTICO

// Puerto de salida: 0 = USB (por defecto); 1 = Serial8 a DIAG_BAUD con un adaptador USB-TTL en el
// TX, para correr sin cable (la ESP32 de telemetria no se usa: espera JSON).
#ifndef DIAG_PUERTO
#define DIAG_PUERTO 0
#endif
#define DIAG_BAUD       921600
#define DIAG_HZ         200
#define DIAG_PERIODO_US (1000000UL / DIAG_HZ)
#define DIAG_RING       1024     // 5 s a 200 Hz

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
    uint32_t rxf;         // tramas completas (32 bits: uint16 da la vuelta a los ~22 min)
    int16_t  rot;         // DriveBase::_rotation x1000
    int16_t  ls, rs;      // consignas por lado, ya calculadas
    uint8_t  ddir;        // direccion pedida
    int16_t  ram;         // rama del case 7; -1 = maniobra (runAngle/runTime): con signo
    uint8_t  dir[4];      // FL FR BL BR - sentido COMANDADO
    int16_t  set[4];      // consigna de RPM por rueda
    int16_t  rpm[4];      // RPM medida (MAGNITUD: el encoder no informa sentido)
    uint8_t  pwm[4];      // esfuerzo aplicado
    int32_t  enc[4];      // pulseCount
    uint32_t tog[4];      // toggles del pin de dir (32 bits: uint16 da la vuelta en ~33 s)
    uint32_t raw[4];      // flancos CRUDOS: movimiento fisico sin suposiciones
    int16_t  yaw, pit;    // x10
    int16_t  gx, gy, gz;  // velocidad angular REAL x10
    int16_t  rol;         // orientation.z x10: inclinacion de COSTADO
    int8_t   rampa;       // g_rampa_estado (rampa.h): 0 llano, 1 sube, -1 baja, 2 costado
    int8_t   pal;         // g_palillo (rampa.h): 0 nada, 1 rueda trabada, 2 empujando
    uint32_t drop;        // perdidas acumuladas al momento de la muestra (no al drenar)
};

// Margen amplio: el drenaje depende de que el lazo lo visite (decenas de ms por vuelta).
DMAMEM DiagMuestra diagRing[DIAG_RING];
IntervalTimer diagTimer;
// Productor unico (el ISR del timer) escribe diagCabeza; consumidor unico
// (diagDrenar, desde el lazo) escribe diagCola. Con indices de 16 bits
// alineados eso es atomico en un Cortex-M7: no hace falta candado.
volatile uint16_t diagCabeza = 0, diagCola = 0;
volatile unsigned long diagDropIsr = 0;
unsigned long diagDrop = 0;
static uint32_t diagUltimaUs = 0;
// Cache de la IMU refrescada a 50 Hz desde el lazo: el I2C (~2 ms) no puede ir en el ISR.
// El BNO055 actualiza a 100 Hz, asi que no se pierde informacion.
static int16_t diagYaw = 0, diagPit = 0, diagGx = 0, diagGy = 0, diagGz = 0, diagRol = 0;

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
    diagRol = diagSat(ev.orientation.z * 10.0);
    // Detector de rampa (rampa.h): usa esta misma lectura, sin I2C extra.
    rampaActualizar(ev.orientation.y, ev.orientation.z, ev.orientation.x,
                    ((float)fl.pulseCount + (float)fr.pulseCount +
                     (float)bl.pulseCount + (float)br.pulseCount) / 4.0f, ult);
    imu::Vector<3> g = bno.getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);
    diagGx = diagSat(g.x() * 10.0);
    diagGy = diagSat(g.y() * 10.0);
    diagGz = diagSat(g.z() * 10.0);
}

// Muestreo por IntervalTimer: 200 Hz aunque el lazo de linea no pase por DIAG_TICK.
// El ISR solo copia RAM (sin I2C, formateo ni nada que bloquee). Un double leido a medio
// escribir lo acota diagSat; a proposito no se usa noInterrupts().
void diagMuestrear()
{
    uint32_t ahora = micros();
    if (diagUltimaUs && (ahora - diagUltimaUs) < DIAG_PERIODO_US) return;
    uint32_t dt = diagUltimaUs ? (ahora - diagUltimaUs) : 0;
    diagUltimaUs = ahora;

    uint16_t sig = (uint16_t)((diagCabeza + 1) % DIAG_RING);
    if (sig == diagCola) { diagDropIsr++; return; }   // anillo lleno: se cuenta la perdida

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
    m.rol = diagRol; m.rampa = (int8_t)g_rampa_estado; m.pal = (int8_t)g_palillo;
    m.drop = diagDrop + diagDropIsr;
    diagCabeza = sig;
}

// LED de la placa: parpadeo lento = registrando; rapido = perdiendo muestras (p. ej. USB sin
// nadie leyendo, que llena el anillo sin grabar nada).
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

// Vacia el anillo sin bloquear: escribe solo mientras haya lugar en el buffer de salida.
void diagDrenar()
{
    // Escribe solo si entra una linea entera (384 B max), para no bloquear.
    unsigned long escritas = 0;
    while (diagCola != diagCabeza && DIAG_OUT.availableForWrite() >= 384)
    {
        const DiagMuestra &m = diagRing[diagCola];
        char l[384];   // peor caso medido ~321 B
        int n = snprintf(l, sizeof(l),
            "%lu,%u,%lu,%d,%u,%d,%lu,%d,%d,%d,%u,%d,"
            "%u,%d,%d,%u,%ld,%lu,%lu,"
            "%u,%d,%d,%u,%ld,%lu,%lu,"
            "%u,%d,%d,%u,%ld,%lu,%lu,"
            "%u,%d,%d,%u,%ld,%lu,%lu,"
            "%d,%d,%d,%d,%d,%d,%d,%d\n",
            (unsigned long)m.us, m.dt, (unsigned long)m.drop, m.rxsteer, m.rxspeed, m.rxage,
            (unsigned long)m.rxf, m.rot, m.ls, m.rs, m.ddir, m.ram,
            m.dir[0], m.set[0], m.rpm[0], m.pwm[0], (long)m.enc[0], (unsigned long)m.tog[0], (unsigned long)m.raw[0],
            m.dir[1], m.set[1], m.rpm[1], m.pwm[1], (long)m.enc[1], (unsigned long)m.tog[1], (unsigned long)m.raw[1],
            m.dir[2], m.set[2], m.rpm[2], m.pwm[2], (long)m.enc[2], (unsigned long)m.tog[2], (unsigned long)m.raw[2],
            m.dir[3], m.set[3], m.rpm[3], m.pwm[3], (long)m.enc[3], (unsigned long)m.tog[3], (unsigned long)m.raw[3],
            m.yaw, m.pit, m.gx, m.gy, m.gz, m.rol, m.rampa, m.pal);
        if (n > 0 && n < (int)sizeof(l)) DIAG_OUT.write((const uint8_t *)l, n);
        else diagDrop++;   // no entro: se cuenta como perdida
        diagCola = (uint16_t)((diagCola + 1) % DIAG_RING);
        escritas++;
    }
    static unsigned long dropPrev = 0;
    unsigned long dropAhora = diagDrop + diagDropIsr;
    diagLatido(dropAhora != dropPrev);
    dropPrev = dropAhora;
}

// La cabecera se reemite cada 2 s: abrir el USB no resetea el Teensy 4.1, y un registrador
// enganchado tarde igual la recibe.
static const char *DIAG_CABECERA =
    "us,dt,drop,rxsteer,rxspeed,rxage,rxf,rot,ls,rs,ddir,ram,"
    "fl_dir,fl_set,fl_rpm,fl_pwm,fl_enc,fl_tog,fl_raw,"
    "fr_dir,fr_set,fr_rpm,fr_pwm,fr_enc,fr_tog,fr_raw,"
    "bl_dir,bl_set,bl_rpm,bl_pwm,bl_enc,bl_tog,bl_raw,"
    "br_dir,br_set,br_rpm,br_pwm,br_enc,br_tog,br_raw,"
    "yaw,pit,gx,gy,gz,rol,rampa,pal";

// Procedencia: todos los flags que cambian comportamiento, con cada cabecera, para que dos CSV
// grabados con binarios distintos no parezcan comparables.
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
    // Constantes del case 7 (panel LINE_* de main.cpp).
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
    // Con un guard menor a 520 B la cabecera dejaria de emitirse sin aviso. `ult` se actualiza
    // despues del guard: sin lugar, se reintenta en el proximo tick.
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

// DIAG_TICK: lo que puede esperar y no puede ir en un ISR (I2C de la IMU, formateo, escritura).
// El muestreo lo hace diagTimer.
#define DIAG_TICK()  do { diagRefrescarImu(); diagCabeceraPeriodica(); diagDrenar(); } while (0)
// Enganche de setup(). Abre el USB y arranca el timer de 200 Hz.
#define DIAG_SETUP() do { Serial.begin(115200); diagInicio(); } while (0)
#else
// MODO_DIAGNOSTICO=0: macros vacias, no queda nada en el binario.
#define DIAG_TICK()  do { } while (0)
#define DIAG_SETUP() do { } while (0)
#endif // MODO_DIAGNOSTICO

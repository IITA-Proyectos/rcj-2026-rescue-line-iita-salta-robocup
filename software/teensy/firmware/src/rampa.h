#pragma once
// rampa.h - detector de rampa por estado SOSTENIDO y deteccion de atasco en el palillo (17-sep-2026).
// Lo alimenta diagRefrescarImu() a 50 Hz con la lectura de la IMU que ya hacia (sin I2C extra), asi
// que solo corre con MODO_DIAGNOSTICO=1 (entorno `competencia`). Sin eso nunca detecta nada.
//
// Estado de rampa (columna `rampa` del CSV; hoy nada del movimiento lo usa):
//   entra  inclinacion > 14 grados, sostenida 1 s Y avanzando 5 cm. En el piso hubo picos de hasta
//          21,5 grados, pero duraron 0,11 s y 1,2 cm como mucho: el umbral solo no alcanza.
//   sale   apenas baja de 10 grados (histeresis).
//   0 llano, 1 sube, -1 baja, 2 de costado. Avance = promedio de los 4 pulseCount.
// Validado con replay: 21 CSV de piso con datos nunca entra; rampa_mapa_1 y rampa_bajada_1 entra bien.
// El pitch instantaneo de ajustarVelocidadPorPendiente() y de PITCH_RAMPA sigue igual: es lo que
// funciona desde las 19:00 del 16-sep y no se toca.

// Interruptor general de las ACCIONES de rampa (hoy: solo el empuje del palillo).
//   1 = empuje del palillo prendido.
//   0 = el movimiento queda identico a las 19:00 del 16-sep; el detector igual registra.
#ifndef RAMPA_ACTIVA
#define RAMPA_ACTIVA 1
#endif
#if RAMPA_ACTIVA && !MODO_DIAGNOSTICO
#warning "Sin MODO_DIAGNOSTICO el detector de rampa no corre: el empuje del palillo nunca salta."
#endif

#define RAMPA_ENTRA_GRADOS  14.0f
#define RAMPA_SALE_GRADOS    8.0f
#define RAMPA_PERSISTE_MS   1000UL
#define RAMPA_AVANCE_CM     5.0f
#define RAMPA_HUECO_MS      200UL    // sin lecturas mas que esto (espera bloqueante): se recuenta
#define RAMPA_LLANO_PITCH   0.0f     // orientation.y en el piso
#define RAMPA_LLANO_ROL     -1.5f    // orientation.z en el piso (mediana de rampa_mapa_1)
#define RAMPA_CM_POR_TICK   (3.14159265f * 6.88f / TICKS_VUELTA)   // rueda de 68,8 mm

int g_rampa_estado = 0;

// Para el palillo: pitch > RAMPA_ENTRA_GRADOS sin cortar desde g_rampaSubeMs (NO exige avance:
// trabado no avanza), y el yaw y la hora de la ultima lectura.
static bool          g_rampaSube   = false;
static unsigned long g_rampaSubeMs = 0;
static float         g_rampaYaw    = 0.0f;
static unsigned long g_rampaUltMs  = 0;

static float rampaEnvolver(float grados)
{
    while (grados > 180.0f) grados -= 360.0f;
    while (grados < -180.0f) grados += 360.0f;
    return grados;
}

// pitch = orientation.y, rol = orientation.z, yaw = orientation.x,
// avanceTicks = promedio de los 4 pulseCount.
void rampaActualizar(float pitch, float rol, float yaw, float avanceTicks, unsigned long ms)
{
    static int candidato = 0;
    static unsigned long desdeMs = 0;
    static float avanceInicio = 0.0f;

    // Un hueco sin lecturas no cuenta como "sostenido": se vuelve a contar desde cero.
    if (g_rampaUltMs != 0 && ms - g_rampaUltMs > RAMPA_HUECO_MS)
    {
        candidato = 0;
        g_rampaSube = false;
    }
    g_rampaUltMs = ms;
    g_rampaYaw = yaw;

    float dy = pitch - RAMPA_LLANO_PITCH;
    float dz = rampaEnvolver(rol - RAMPA_LLANO_ROL);

    if (dy > RAMPA_ENTRA_GRADOS)
    {
        if (!g_rampaSube) { g_rampaSube = true; g_rampaSubeMs = ms; }
    }
    else
        g_rampaSube = false;

    if (g_rampa_estado != 0)
    {
        bool sigue = (g_rampa_estado == 1 && dy > RAMPA_SALE_GRADOS) ||
                     (g_rampa_estado == -1 && dy < -RAMPA_SALE_GRADOS) ||
                     (g_rampa_estado == 2 && fabsf(dz) > RAMPA_SALE_GRADOS);
        if (sigue) return;
        g_rampa_estado = 0;
        candidato = 0;
    }

    int nuevo = (dy > RAMPA_ENTRA_GRADOS) ? 1
              : (dy < -RAMPA_ENTRA_GRADOS) ? -1
              : (fabsf(dz) > RAMPA_ENTRA_GRADOS) ? 2 : 0;
    if (nuevo != candidato)
    {
        candidato = nuevo;
        desdeMs = ms;
        avanceInicio = avanceTicks;
        return;
    }
    if (nuevo != 0 && ms - desdeMs >= RAMPA_PERSISTE_MS &&
        fabsf(avanceTicks - avanceInicio) * RAMPA_CM_POR_TICK >= RAMPA_AVANCE_CM)
        g_rampa_estado = nuevo;
}

// --- Empuje del palillo: SOLO cuando quedo atascado subiendo ---
// Atascado = las tres cosas a la vez:
//   1. subiendo: pitch > 14 grados sin cortar hace 1 s o mas (en el piso nunca paso de 0,11 s);
//   2. alguna rueda mandada hacia adelante (consigna >= 10 rpm) gira a menos de 3 rpm durante
//      PALILLO_TRABADA_MS seguidos;
//   3. en ese tiempo el robot giro menos de PALILLO_YAW_MAX: en una curva la rueda de adentro
//      tambien se frena, pero el robot gira.
// Replay: 21 CSV de piso y rampa_mapa_1/rampa_bajada_1 (subidas con curvas y verdes) -> 0 disparos.
// En la subida normal la racha mas larga fue 0,16 s (rampa_mapa_1).
// El empuje (case 7) dura PALILLO_EMPUJE_MS o hasta que el pitch baje de PITCH_RAMPA, y despues
// vuelve todo a como estaba. Si sigue trabado, hace falta otro PALILLO_TRABADA_MS para repetirlo.
// Se ajustan sin editar, p. ej.: set PLATFORMIO_BUILD_FLAGS=-D PALILLO_TRABADA_MS=700
#ifndef PALILLO_TRABADA_MS
#define PALILLO_TRABADA_MS  500UL
#endif
#ifndef PALILLO_YAW_MAX
#define PALILLO_YAW_MAX     6.0f
#endif
#ifndef PALILLO_EMPUJE_MS
#define PALILLO_EMPUJE_MS   3000UL
#endif

int g_palillo = 0;                      // columna `pal` del CSV: 0 nada, 1 rueda trabada, 2 empujando
unsigned long g_palilloDesdeMs = 0;     // millis() del arranque del empuje en curso
// Inicio de la verificacion de rueda trabada. La telemetria lo publica para
// mostrar cuantos ms llevo contando antes de decidir empujar.
unsigned long g_palilloCuentaDesdeMs = 0;

// Una vez por vuelta del case 7, ANTES de mandar las ruedas: mira la orden y la medicion que dejo
// la vuelta anterior. enPendiente = pitch > PITCH_RAMPA. Devuelve true mientras dure el empuje.
bool palilloEmpuje(bool enPendiente)
{
    static bool          empujando  = false;
    static bool          contando   = false;
    static unsigned long trabaDesde = 0;
    static float         yaw0       = 0.0f;
    static unsigned long ultimaMs   = 0;
    const unsigned long ms = millis();

    // Si el case 7 dejo de correr (verde, maniobra, switch), lo de antes no vale: ni el empuje
    // en curso ni la cuenta de rueda trabada siguen del otro lado de la maniobra.
    if (ms - ultimaMs > RAMPA_HUECO_MS)
    {
        empujando = false;
        contando = false;
        g_palillo = 0;
        g_palilloCuentaDesdeMs = 0;
    }
    ultimaMs = ms;

    if (empujando)
    {
        if (enPendiente && ms - g_palilloDesdeMs < PALILLO_EMPUJE_MS)
            return true;
        empujando = false;
        contando = false;
        g_palillo = 0;
        g_palilloCuentaDesdeMs = 0;
    }

    const bool imuAlDia = (g_rampaUltMs != 0) && (ms - g_rampaUltMs <= RAMPA_HUECO_MS);
    const bool subiendo = imuAlDia && g_rampaSube && (ms - g_rampaSubeMs >= RAMPA_PERSISTE_MS);
    Moto *mt[4]       = { &fl, &fr, &bl, &br };
    const int adel[4] = { FORWARD, !FORWARD, FORWARD, !FORWARD };   // derechas espejadas
    bool trabada = false;
    for (int i = 0; i < 4; i++)
        if (mt[i]->_dir == adel[i] && mt[i]->_rpm >= 10.0 && mt[i]->_realrpm < 3.0)
            trabada = true;

    if (!subiendo || !trabada)
    {
        contando = false;
        g_palillo = 0;
        g_palilloCuentaDesdeMs = 0;
        return false;
    }
    if (!contando)
    {
        contando = true;
        trabaDesde = ms;
        g_palilloCuentaDesdeMs = ms;
        yaw0 = g_rampaYaw;
        g_palillo = 1;
        return false;
    }
    if (ms - trabaDesde < PALILLO_TRABADA_MS)
        return false;

    contando = false;
    g_palillo = 0;
    g_palilloCuentaDesdeMs = 0;
    if (fabsf(rampaEnvolver(g_rampaYaw - yaw0)) > PALILLO_YAW_MAX)
        return false;   // estaba doblando: es una curva, no un palillo
    empujando = true;
    g_palilloDesdeMs = ms;
    g_palillo = 2;
    return true;
}

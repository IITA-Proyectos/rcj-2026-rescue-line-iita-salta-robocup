// Calibracion rapida del APDS9960 por USB (la usa tools/calibracion_color.html).
//
// Los umbrales de classify_color() viven en g_cal_color. Arrancan con los valores medidos
// a mano (los mismos que estaban fijos en el codigo); si en la EEPROM hay una calibracion
// valida, se usa esa. Sin calibrar, el robot se comporta EXACTAMENTE igual que antes.
//
// Solo atiende comandos con el switch APAGADO (pin 32 = 1): el robot esta quieto.
// Todas las respuestas empiezan con "#CAL" para no confundirse con el CSV de diagnostico.
//
// Comandos (una linea, terminada en \n):
//   CAL?               -> imprime la calibracion vigente
//   CALS n             -> toma n lecturas crudas (1..50) y las imprime: #CAL S r g b c
//   CALSET clave valor -> cambia un umbral en RAM (efecto inmediato)
//   CALSAVE            -> guarda en EEPROM
//   CALDEF             -> vuelve a los valores de fabrica (RAM y EEPROM)
#pragma once
#include <EEPROM.h>

struct CalColor
{
    uint32_t magic;
    // Plateado
    uint16_t pl_c_min;
    float pl_rc_min, pl_rc_max, pl_rg_min, pl_rg_max, pl_rb_min, pl_rb_max;
    int16_t pl_bg_max;
    // Blanco
    uint16_t bl_c_min;
    float bl_rc_min, bl_rc_max;
    // Rojo
    uint16_t ro_c_min, ro_c_max;
    float ro_rc_min, ro_rg_min, ro_rb_min;
};

constexpr uint32_t CAL_COLOR_MAGIC = 0xC0102026UL;
constexpr int CAL_COLOR_EEPROM_ADDR = 3000;   // nadie mas usa la EEPROM

const CalColor CAL_COLOR_FABRICA = {
    CAL_COLOR_MAGIC,
    1500, 0.245f, 0.268f, 0.645f, 0.700f, 0.615f, 0.700f, 30,
    430, 0.195f, 0.245f,
    340, 900, 0.295f, 1.10f, 0.90f};

CalColor g_cal_color = CAL_COLOR_FABRICA;

void cal_color_cargar()
{
    CalColor leida;
    EEPROM.get(CAL_COLOR_EEPROM_ADDR, leida);
    if (leida.magic == CAL_COLOR_MAGIC)
        g_cal_color = leida;
}

void cal_color_imprimir()
{
    const CalColor &k = g_cal_color;
    Serial.print("#CAL CFG");
    Serial.print(" pl_c_min ");  Serial.print(k.pl_c_min);
    Serial.print(" pl_rc_min "); Serial.print(k.pl_rc_min, 4);
    Serial.print(" pl_rc_max "); Serial.print(k.pl_rc_max, 4);
    Serial.print(" pl_rg_min "); Serial.print(k.pl_rg_min, 4);
    Serial.print(" pl_rg_max "); Serial.print(k.pl_rg_max, 4);
    Serial.print(" pl_rb_min "); Serial.print(k.pl_rb_min, 4);
    Serial.print(" pl_rb_max "); Serial.print(k.pl_rb_max, 4);
    Serial.print(" pl_bg_max "); Serial.print(k.pl_bg_max);
    Serial.print(" bl_c_min ");  Serial.print(k.bl_c_min);
    Serial.print(" bl_rc_min "); Serial.print(k.bl_rc_min, 4);
    Serial.print(" bl_rc_max "); Serial.print(k.bl_rc_max, 4);
    Serial.print(" ro_c_min ");  Serial.print(k.ro_c_min);
    Serial.print(" ro_c_max ");  Serial.print(k.ro_c_max);
    Serial.print(" ro_rc_min "); Serial.print(k.ro_rc_min, 4);
    Serial.print(" ro_rg_min "); Serial.print(k.ro_rg_min, 4);
    Serial.print(" ro_rb_min "); Serial.print(k.ro_rb_min, 4);
    Serial.println();
}

bool cal_color_set(const char *clave, float v)
{
    CalColor &k = g_cal_color;
    if (!strcmp(clave, "pl_c_min"))  { k.pl_c_min = (uint16_t)v; return true; }
    if (!strcmp(clave, "pl_rc_min")) { k.pl_rc_min = v; return true; }
    if (!strcmp(clave, "pl_rc_max")) { k.pl_rc_max = v; return true; }
    if (!strcmp(clave, "pl_rg_min")) { k.pl_rg_min = v; return true; }
    if (!strcmp(clave, "pl_rg_max")) { k.pl_rg_max = v; return true; }
    if (!strcmp(clave, "pl_rb_min")) { k.pl_rb_min = v; return true; }
    if (!strcmp(clave, "pl_rb_max")) { k.pl_rb_max = v; return true; }
    if (!strcmp(clave, "pl_bg_max")) { k.pl_bg_max = (int16_t)v; return true; }
    if (!strcmp(clave, "bl_c_min"))  { k.bl_c_min = (uint16_t)v; return true; }
    if (!strcmp(clave, "bl_rc_min")) { k.bl_rc_min = v; return true; }
    if (!strcmp(clave, "bl_rc_max")) { k.bl_rc_max = v; return true; }
    if (!strcmp(clave, "ro_c_min"))  { k.ro_c_min = (uint16_t)v; return true; }
    if (!strcmp(clave, "ro_c_max"))  { k.ro_c_max = (uint16_t)v; return true; }
    if (!strcmp(clave, "ro_rc_min")) { k.ro_rc_min = v; return true; }
    if (!strcmp(clave, "ro_rg_min")) { k.ro_rg_min = v; return true; }
    if (!strcmp(clave, "ro_rb_min")) { k.ro_rb_min = v; return true; }
    return false;
}

// Lecturas CRUDAS (sin el promedio movil) con timeout: si el APDS no responde no se cuelga.
void cal_color_muestrear(int n)
{
    if (!color_sensor_ok) { Serial.println("#CAL ERR apds no arranco"); return; }
    if (n < 1) n = 1;
    if (n > 50) n = 50;
    for (int i = 0; i < n; i++)
    {
        unsigned long t0 = millis();
        while (!apds.colorDataReady())
        {
            if (millis() - t0 > 100) { Serial.println("#CAL ERR timeout"); return; }
            delay(1);
        }
        uint16_t r, g, b, c;
        apds.getColorData(&r, &g, &b, &c);
        Serial.printf("#CAL S %u %u %u %u\n", r, g, b, c);
        delay(APDS_COLOR_INTEGRATION_MS + 2);   // que la proxima sea una integracion nueva
    }
    Serial.println("#CAL SFIN");
}

void cal_color_servicio()
{
    static char linea[64];
    static uint8_t len = 0;
    while (Serial.available())
    {
        char ch = Serial.read();
        if (ch == '\r') continue;
        if (ch != '\n')
        {
            if (len < sizeof(linea) - 1) linea[len++] = ch;
            continue;
        }
        linea[len] = 0;
        len = 0;
        if (strncmp(linea, "CAL", 3) != 0) continue;

        if (digitalRead(32) != 1) { Serial.println("#CAL ERR apaga el switch"); continue; }

        char clave[16];
        float v;
        int n;
        if (!strcmp(linea, "CAL?")) cal_color_imprimir();
        else if (sscanf(linea, "CALS %d", &n) == 1) cal_color_muestrear(n);
        else if (sscanf(linea, "CALSET %15s %f", clave, &v) == 2)
            Serial.println(cal_color_set(clave, v) ? "#CAL OK" : "#CAL ERR clave");
        else if (!strcmp(linea, "CALSAVE"))
        {
            g_cal_color.magic = CAL_COLOR_MAGIC;
            EEPROM.put(CAL_COLOR_EEPROM_ADDR, g_cal_color);
            Serial.println("#CAL OK guardado");
        }
        else if (!strcmp(linea, "CALDEF"))
        {
            g_cal_color = CAL_COLOR_FABRICA;
            EEPROM.put(CAL_COLOR_EEPROM_ADDR, g_cal_color);
            cal_color_imprimir();
        }
        else Serial.println("#CAL ERR comando");
    }
}

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_web_ui.py — Embebe gui/dashboard.html dentro de src/web_ui.h como raw string
PROGMEM, para que el firmware de la ESP32 sirva la GUI sin SPIFFS/LittleFS.

Uso (desde software/esp32/telemetria/):
    python tools/gen_web_ui.py

Editas SIEMPRE gui/dashboard.html; despues corres esto y recompilas. La GUI es
la MISMA que se puede abrir directo en un navegador (tiene modo demo sin robot).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC_HTML = os.path.join(ROOT, "gui", "dashboard.html")
OUT_H = os.path.join(ROOT, "src", "web_ui.h")
DELIM = "HTMLDOC"


def main():
    with open(SRC_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    if (")" + DELIM + '"') in html:
        sys.exit("ERROR: el delimitador '%s' aparece en el HTML. Cambia DELIM." % DELIM)

    header = (
        "// ============================================================================\n"
        "//  web_ui.h  —  GUI de telemetria embebida (PROGMEM).\n"
        "//  AUTOGENERADO desde gui/dashboard.html por tools/gen_web_ui.py — NO editar a\n"
        "//  mano: modifica el .html y volve a generar (python tools/gen_web_ui.py).\n"
        "// ============================================================================\n"
        "#ifndef WEB_UI_H\n"
        "#define WEB_UI_H\n"
        "#include <pgmspace.h>\n\n"
        'const char INDEX_HTML[] PROGMEM = R"' + DELIM + "(\n"
    )
    footer = "\n)" + DELIM + '";\n\n#endif // WEB_UI_H\n'

    with open(OUT_H, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + html + footer)

    print("OK: %s (%d bytes de HTML)" % (os.path.relpath(OUT_H, ROOT), len(html)))


if __name__ == "__main__":
    main()

# Investigación: ruedas de máximo coeficiente de fricción para Rescue Line

> **Fecha:** 2026-07-03
> **Contexto:** el robot pierde tracción en la rampa (ver [2026-07-02-auditoria-independiente-rampa-plateado.md](2026-07-02-auditoria-independiente-rampa-plateado.md)). Se investigó qué material de rueda maximiza el grip para un robot de ~1–2 kg sobre pista RCJ (MDF pintado blanco / laminado, rampas de 25°, superficies plateadas/aluminio, ambiente con polvo), tanto en ruedas comerciales como en compuestos para moldear.
> **Metodología:** deep research multi-agente (21 fuentes, 25 claims sometidos a verificación adversarial de 3 votos: 22 confirmados, 3 refutados). Cada afirmación de este doc lleva su nivel de confianza. **Ningún μ citado fue medido sobre las superficies reales de RCJ** — la validación en banco es obligatoria antes de decidir (regla de oro 3 del repo).

---

## 1. La física primero: por qué "el material más pegajoso" es la pregunta equivocada

**Confianza: ALTA** — verificado 3-0 contra papers peer-reviewed (Persson & Xu, *J. Chem. Phys.* 163, 141001, 2025; Tiwari et al., *Frontiers in Mechanical Engineering*, 2020; *Tribology Letters* 73:106, 2025).

1. **La fricción de un elastómero tiene dos mecanismos**, no uno:
   - **Adhesión**: cizallamiento en el **área de contacto real** entre goma y piso (eventos stick-slip de segmentos poliméricos a escala nanométrica).
   - **Histéresis viscoelástica**: energía disipada al deformarse cíclicamente contra las asperezas del sustrato.

   En superficies **lisas** (MDF pintado, laminado, rampa de aluminio) domina el término adhesivo, y lo que lo maximiza es el **área de contacto real**.

2. **El área de contacto real la maximiza el módulo bajo (dureza Shore A baja), no la "pegajosidad".** Experimento clave (Tiwari et al. 2020): silanizar vidrio reduce el trabajo de adhesión **a la mitad** y el coeficiente de fricción del caucho **casi no cambia**. Cita textual: *"There is no simple relation between adhesion and friction."* Un material que se siente pegajoso al tacto no necesariamente tracciona más.

3. **Dureza baja = más fricción en piso liso limpio** (medido): sobre epoxi limpio, NBR de 57.9 Shore A dio COF 2.216 vs 0.70 con 84 Shore A (p<0.0001), por reducción del área de contacto real. *Caveat: el estudio cubre 57.9–84 ShA; la extrapolación a 10–30A es direccional, no medida.*

4. **Contraintuitivo y clave para RCJ — la dureza baja también gana con polvo** (*Tribology Letters* 2025): en pisos lisos contaminados con partículas, las gomas **más blandas** dieron **mayor** COF (p<0.0001), porque en esa condición manda la interacción partícula–piso (rodadura de partículas) y la goma blanda la suprime. El costo real del compuesto blando y taqueado es **operativo** (hay que limpiarlo antes de cada corrida), no de mecanismo.

5. **El número objetivo:** para subir 25° se necesita μ > tan(25°) ≈ **0.47**, más margen por transferencia de peso y aceleración → apuntar a **μ efectivo ≥ 0.8–1.0**. Alcanzable con holgura con PU/silicona Shore A 10–30.

6. **El punto dulce es Shore A 15–30, no "lo más blando que exista".** Por debajo de ~10A la rueda se deforma en exceso bajo carga, se desgasta rápido y aspira el polvo de la pista sin ganancia real de grip. Las guías de casting de ruedas de sumo (miscircuitos.com, mcuoneclipse.com) coinciden: *"the rubber needs Shore A between 20 or 30"*.

**Sobre los rodillos de fotocopiadora** (hipótesis inicial del equipo): el instinto es correcto — son exactamente esto, siliconas/uretanos industriales de Shore A bajo. Pero no son "lo mejor que existe": son la versión industrial de lo mismo que se puede comprar o moldear adaptado a nuestra llanta.

---

## 2. Las 10 soluciones, rankeadas

### Verificadas con fuentes (confianza ALTA/MEDIA)

#### 1. Ruedas FingerTech de poliuretano Shore A20 — mejor opción comercial encontrada

- **Qué es:** neumático de PU Shore A20 desgasificado al vacío sobre llanta de aluminio 6061 anodizado. Estándar de grip en mini-sumo. Existe variante Shore A45 (más durable, menos grip).
- **μ declarado por el fabricante:** **1.75 contra MDF liso sin pintar** (vs 1.30 silicona y 1.05 goma en su misma prueba). *Caveat verificado 2-1: benchmark del propio fabricante, sin metodología publicada, sobre MDF sin pintar — no asumir que transfiere a MDF pintado blanco ni a la rampa plateada.*
- **Diámetros:** 44.45 / 50.8 (48.5 g) / 63.5 / 76.2 mm — tres entran en el rango 30–70 mm.
- **Precio observado:** mini-sumo 1.125" ≈ USD 16.79 el par; línea sumo ≈ CAD 23.87.
- **Compra:** [FingerTech mini-sumo wheels](https://www.fingertechrobotics.com/proddetail.php?prod=ft-minisumo-wheels-1125) · [FingerTech sumo wheels](https://www.fingertechrobotics.com/proddetail.php?prod=ft-sumo-wheel) — importar desde Canadá o vía RobotShop. Costo y plazo de importación a Argentina: **no establecido, cotizar**.
- **Mantenimiento obligado** (lo exige el propio fabricante, verificado 3-0): *"Clean the tires with isopropyl alcohol wipes before each match for optimal traction"*.

#### 2. Moldear con Smooth-On VytaFlex 20 (uretano Shore 20A) — mejor opción casera

- **Qué es:** caucho de uretano de la misma familia y dureza nominal que el compuesto FingerTech.
- **Por qué es viable para un equipo escolar** (datasheet verificado 3-0): mezcla **1A:1B por volumen o peso**, **no requiere desgasificado al vacío**, contracción despreciable. Molde impreso en 3D + vaselina como desmoldante, curado ~16–24 h.
- **Corroboración independiente de uso en ruedas de sumo:** [miscircuitos.com](https://miscircuitos.com/how-to-cast-sumo-wheels-handmade/) · [mcuoneclipse.com](https://mcuoneclipse.com/2017/12/28/making-perfect-sticky-diy-sumo-robot-tires/) · [hackaday.com](https://hackaday.com/2016/05/09/glue-your-sumo-robot-to-the-mat-with-custom-sticky-tires/)
- **Datasheet:** [smooth-on.com/products/vytaflex-20](https://www.smooth-on.com/products/vytaflex-20/)
- **Compra en Argentina:** ver sección 3 — Duoflex es distribuidor oficial; el VF20 **no está publicado online hoy**, pedir cotización directa.

#### 3. Moldear con Dragon Skin 10 (silicona platino Shore 10A) — disponibilidad argentina confirmada

- **Qué es:** silicona de curado platino. Serie disponible en 10A / 15A / 20A / 30A.
- **Specs verificadas 3-0** (boletín técnico Smooth-On rev. abril 2025): DS10 = Shore 10A, tracción 475 psi, **elongación 1000%, desgarro 102 pli** (Die B, ASTM D-624) — durabilidad mecánica alta pese a la blandura, clave para que una rueda blanda sobreviva la competencia.
- **Trade-off honesto:** en el benchmark FingerTech la silicona rindió μ=1.30 vs 1.75 del PU. Es **la opción localmente disponible, no la de máximo grip**.
- **Ojo:** el Dragon Skin **FX-Pro es Shore 2A** — demasiado blando para rueda con 0.5–1 kg de carga. Comprar **DS 10 o DS 20**, no FX-Pro.
- **Datasheet:** [Dragon Skin Series TB (PDF)](https://www.smooth-on.com/tb/files/DRAGON_SKIN_SERIES_TB.pdf)
- **Compra en Argentina:** verificado que Duoflex Sudamericana vende Smooth-On por MercadoLibre (listing confirmado de FX-Pro 0.90 kg ≈ $76.145 ARS — precio de snippet sin fecha confiable, **re-cotizar**).

### Criterio de ingeniería (SIN fuente verificada en esta pasada — validar en banco)

#### 4. VytaFlex 10 (uretano Shore 10A)

Un escalón más de grip que el VF20 a costa de desgaste y captación de polvo. Vale la pena moldear un par de cada dureza y comparar en la rampa plateada real. Datasheet: [smooth-on.com/products/vytaflex-10](https://www.smooth-on.com/products/vytaflex-10/). Mismo canal de compra que el VF20 (Duoflex, a pedido).

#### 5. Ruedas de silicona JSumo SLT20 / SLT20P (Shore 20A)

En la [comparativa del propio JSumo (2015)](https://blog.jsumo.com/wheel-report-2015-our-wheels-slt20-slt20p-against-to-banebots-fingertech-wheels/) rinden levemente arriba de FingerTech en su metodología (μ 0.75 vs 0.70 — números **no comparables** con el 1.75 de FingerTech, metodologías distintas). Dato a chequear: [arsumo.com.ar lista repuestos de silicona para SLT20](https://arsumo.com.ar/productos/par-de-repuesto-silicona-para-rueda-slt20/) — habría stock nacional.

#### 6. Rodillos de fotocopiadora/impresora reciclados

Silicona o uretano blando de calidad industrial, costo cero. Contras: diámetro y eje fijos, hay que mecanizar el acople, dureza desconocida. Buena opción de **prototipo cero-costo**, no la solución final.

#### 7. BaneBots (PU Shore 30A)

Comerciales, robustas, fáciles de conseguir. En la comparativa JSumo quedaron últimas en grip (μ 0.55 en su prueba) por ser más duras. Opción "segura pero mediocre" — se documenta para descartarla con argumento.

#### 8. TPU blando impreso en 3D (Filaflex 60A–70A o similar)

Conveniencia máxima si hay impresora con direct-drive: iterar diseño de banda en horas. Pero 60A imprimible es mucho más duro que 20A moldeado → grip claramente inferior. **Uso recomendado: imprimir la llanta y moldear la banda encima**, no como superficie de tracción.

#### 9. Banda de látex/goma natural sobre llanta impresa

Tiras de cámara de látex o tubo de látex estirado sobre llanta 3D. Bajo costo, funciona, pero la goma natural rindió μ=1.05 en el benchmark FingerTech — es el piso de la lista.

#### 10. Lo que NO usar, con el porqué

- **Sorbothane:** es amortiguador viscoelástico; desgarro pésimo, se destruye como rueda.
- **Ecoflex 00-30 / siliconas Shore 00 / Dragon Skin FX-Pro (2A):** demasiado blandas — deformación excesiva bajo carga, riesgo de delaminación de la llanta, aspiradora de polvo.
- **Tratamientos pegajosos superficiales** (belt dressing, adhesivos en spray): grip que muere en metros con polvo, y las sustancias que dejan residuo en la pista suelen estar prohibidas en RCJ — **verificar reglamento vigente antes de considerar cualquier tratamiento**.

---

## 3. Links de compra en Argentina (estado al 2026-07-03)

**Hallazgo honesto:** no hay publicación viva de VytaFlex 10 ni 20 en Argentina. Lo publicado hoy es **VytaFlex 30** (que igual entra en el óptimo Shore 20–30).

### Publicaciones activas verificadas — vendedor DUOFLEX SUDAMERICANA (distribuidor oficial Smooth-On)

| Producto | Presentación | Link |
|---|---|---|
| VytaFlex **30** kit de prueba | 0,86 kg (alcanza para un juego de ruedas) | [MercadoLibre MLAU192757621](https://www.mercadolibre.com.ar/smooth-on-vytaflex-so-30-caucho-uretano-kit-086kg-moldes/up/MLAU192757621) |
| VytaFlex **30** galón | 7,26 kg | [MercadoLibre MLA-769006445](https://articulo.mercadolibre.com.ar/MLA-769006445-smoothon-vytaflex-ga-30-1-galon-726kg-caucho-poliuretano-_JM) |
| Dragon Skin FX-Pro (2A — **no comprar para ruedas**, referencia de que venden la línea) | 0,90 kg | [Tienda Duoflex MLA-768984323](https://www.tiendaduoflex.com.ar/MLA-768984323-smoothon-silicona-al-platino-dragon-skin-ds-fx-pro-090kg-_JM) |

### Para pedir VytaFlex 10/20 o Dragon Skin 10/20

- **Catálogo Duoflex línea VytaFlex:** [duoflex.com.ar — VytaFlex](http://www.duoflex.com.ar/detalle.php?a=vytaflex.-cauchos-de-poliuretano-de-ultima-generacion&d=2&t=2) *(certificado SSL roto — abrir igual, es el catálogo oficial; lista la línea 10A–60A)*
- **Tienda online:** [duoflexsudamericana.mercadoshops.com.ar](https://duoflexsudamericana.mercadoshops.com.ar) · [búsqueda "vytaflex" en ML](https://listado.mercadolibre.com.ar/vytaflex)
- **Contacto directo Duoflex** (Floresta, CABA): tel. **(011) 2124-2732** · WhatsApp **+54 9 11 6850 1010**. Preguntar por **VF 10 y VF 20 en kit chico (~0,9 kg)** y por **Dragon Skin 10/20** — publican en ML solo parte del catálogo.
- **Todas sus publicaciones:** [Melinterest — DUOFLEX SUDAMERICANA](http://ar.melinterest.com/?r=site/search&seller_id=193135361&seller_nickname=DUOFLEX%20SUDAMERICANA)

### Alternativas de importación

- [FingerTech mini-sumo wheels (Canadá)](https://www.fingertechrobotics.com/proddetail.php?prod=ft-minisumo-wheels-1125) — ruedas terminadas, sin proceso químico.
- [Amazon — VytaFlex 20, unidad pinta](https://www.amazon.com/-/es/Vytaflex-20-hacer-moldes-uretano/dp/B00IRC0MJW) — vía courier.

> ⚠️ Precios en ARS: re-cotizar siempre antes de decidir; los montos citados provienen de snippets sin fecha confiable.

---

## 4. Plan de acción recomendado

1. **Ya:** comprar el kit de prueba **VytaFlex 30 (0,86 kg)** publicado en ML y moldear el primer juego de ruedas (molde impreso en 3D). Con esto se valida molde, proceso y el protocolo de test de rampa.
2. **En paralelo:** pedir a Duoflex por WhatsApp cotización de **VF20** (y VF10 si lo traen). Si llega, moldear el segundo juego y comparar durezas en la rampa real.
3. **En paralelo:** cotizar importación de **2 pares FingerTech A20 (50.8 mm)** — plan B comercial probado en competencia.
4. **Protocolo de pits no negociable** con cualquier compuesto blando: **limpiar las ruedas con alcohol isopropílico antes de cada corrida**. Presupuestar toallitas IPA en el kit.
5. **Validación en banco obligatoria** (regla de oro 3): plancha de la superficie real (MDF pintado y rampa plateada), robot completo encima, inclinar hasta deslizamiento → **μ = tan(ángulo de deslizamiento)**. Comparar candidatos ahí, no por datasheet. Registrar resultados en [testing/TEST_LOG.md](../../testing/TEST_LOG.md).
6. **Preguntar en el [foro oficial RCJ](https://junior.forum.robocup.org/t/wheel-recommendations-for-robocup-junior-rescue-maze/5384)** qué usan los equipos top de Rescue Line — la investigación no encontró ninguna fuente verificable sobre esto.

---

## 5. Preguntas abiertas (sin fuente — resolver en banco o preguntando)

1. ¿Cuál es el μ real de PU Shore A20 y silicona 10–20A **sobre la rampa plateada/aluminio y sobre MDF pintado blanco** con la carga del robot? Ningún dato verificado cubre esas superficies.
2. ¿Qué ruedas/compuestos usan efectivamente los equipos top de RoboCup Rescue Line y mini-sumo internacional?
3. ¿Duoflex trae VytaFlex 10/20 a pedido? ¿Costo y plazo de importar FingerTech desde Canadá?
4. ¿Una silicona muy blanda (≤10A) soporta 0.5–1 kg por rueda en rampa de 25° sin deformación excesiva ni delaminación?

## 6. Claims refutados durante la verificación (NO citar como establecidos)

- Que Shore 10A sea "el estándar" del mini-sumo competitivo (0-3 en contra).
- Dos claims sobre películas de contaminación líquida como mecanismo dominante de pérdida de grip (1-2 en contra cada uno).

---

## Fuentes principales

**Física (peer-reviewed):**
- Persson & Xu, [*Rubber friction: Theory, mechanisms, and challenges*](https://pubs.aip.org/aip/jcp/article/163/14/141001/3366813/Rubber-friction-Theory-mechanisms-and-challenges), J. Chem. Phys. 163, 141001 (2025)
- Tiwari et al., [*Rubber adhesion and friction*](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2020.620233/full), Frontiers in Mechanical Engineering (2020)
- [*Tribology Letters* 73:106 (2025)](https://link.springer.com/article/10.1007/s11249-025-02046-4) — dureza de goma vs COF en pisos limpios y contaminados
- [Composites Communications (2018) — histéresis en compuestos de caucho](https://www.sciencedirect.com/science/article/abs/pii/S245221391830007X)

**Producto (primarias):**
- [FingerTech mini-sumo wheels](https://www.fingertechrobotics.com/proddetail.php?prod=ft-minisumo-wheels-1125) · [FingerTech sumo wheels](https://www.fingertechrobotics.com/proddetail.php?prod=ft-sumo-wheel)
- [Smooth-On VytaFlex 20](https://www.smooth-on.com/products/vytaflex-20/) · [VytaFlex 10](https://www.smooth-on.com/products/vytaflex-10/) · [Dragon Skin Series TB](https://www.smooth-on.com/tb/files/DRAGON_SKIN_SERIES_TB.pdf)

**Práctica (blogs/foros — confianza media):**
- [JSumo Wheel Report 2015](https://blog.jsumo.com/wheel-report-2015-our-wheels-slt20-slt20p-against-to-banebots-fingertech-wheels/) · [mcuoneclipse — DIY sticky sumo tires](https://mcuoneclipse.com/2017/12/28/making-perfect-sticky-diy-sumo-robot-tires/) · [miscircuitos — cast sumo wheels](https://miscircuitos.com/how-to-cast-sumo-wheels-handmade/) · [Ask Aaron — materials](https://runamok.tech/AskAaron/materials.html) · [Foro oficial RCJ — wheel recommendations](https://junior.forum.robocup.org/t/wheel-recommendations-for-robocup-junior-rescue-maze/5384)

---

*Documento generado a partir de deep research multi-agente con verificación adversarial (2026-07-03). Los niveles de confianza reflejan qué sobrevivió la verificación con fuentes; lo marcado como "criterio de ingeniería" debe validarse en banco antes de basar decisiones de compra grandes.*

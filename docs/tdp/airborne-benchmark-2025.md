# Airborne 2025 TDP Benchmark

Reference file:

- `C:\Users\villa\Downloads\00_Airborne_TDP_RoboCup_Rescue_Line_2025.pdf`

This note summarizes structural lessons from the Airborne 2025 Rescue Line TDP, which the user identified as a 100% rubric reference. It is not copied into the IITA TDP; it is used as a style and scoring benchmark.

## Structure that scored well

Airborne used the official template structure directly:

1. Abstract.
2. Introduction with short member roles.
3. Project Planning.
4. Integration Plan.
5. Hardware.
6. Mechanical design.
7. Electronic design.
8. Software architecture.
9. Innovative solutions.
10. Performance Evaluation.
11. Conclusion.

The paper was compact: it did not create a separate heading for every rubric item. Instead, it placed the rubric evidence inside the template sections.

## Reusable scoring patterns

| Pattern | Why it helps the rubric | Applied to IITA TDP |
|---|---|---|
| Requirements table: requirement / tools / final solution | Directly satisfies requirements definition and links rules to design choices. | Added as Table 1 in `TDP.md`. |
| One visible project schedule | Shows milestones, timeline and review gates. | Added Table 2 with gates and owners. |
| Integration figure plus explanation | Makes communication between components obvious. | Added Mermaid system integration figure and component matrix. |
| Hardware overview before sub-sections | Helps the reader understand the robot before details. | Added high-level Hardware introduction. |
| Mechanical modules described by function | Shows internal interfaces and workability. | Added Table 4. |
| Custom PCB and power explanation | Supports electronic innovation and reliability. | Added electronics architecture and power figure. |
| Software flow diagrams | Supports architecture score without dumping source code. | Added software state flow. |
| One or two real problems in performance | Shows insight, not just description. | Added lighting and responsiveness challenges. |

## What IITA still needs to match the benchmark

1. Render all Mermaid diagrams into images for the final PDF.
2. Add current robot photos next to CAD images.
3. Fill `testing/TEST_LOG.md` with real measured values.
4. Export the BOM using the official 2026 BOM template.
5. Decide the final AI runtime/model path and make code, docs and TDP match.
6. Keep the final PDF within 10 pages from Abstract to Conclusion.

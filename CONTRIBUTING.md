# Guía de Contribución

## Commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scope): descripción
fix(scope): descripción
docs(scope): descripción
test(scope): descripción
hardware(scope): descripción
```

Scopes válidos: `teensy`, `rpi`, `vision`, `control`, `comms`, `power`, `mechanics`, `docs`

## Branches

- `main`: rama protegida, solo via PR
- `feat/<nombre>`: nuevas funcionalidades
- `fix/<nombre>`: correcciones
- `docs/<nombre>`: documentación

## Pull Requests

Cada PR debe incluir:

1. Resumen técnico de los cambios
2. Evidencia de testing (fotos, videos, logs)
3. Declaración de uso de IA (si aplica)
4. Issue vinculado

## Issues

Todo trabajo debe originarse en un Issue. Usar las labels definidas en el repositorio.

## Uso de IA

Si se usó IA (ChatGPT, Claude, Copilot, etc.) en el desarrollo, declararlo en el PR con:

- Herramienta usada
- Qué parte del código fue asistida
- Si se revisó/modificó manualmente

---
name: m3u-to-backup
description: "Mueve canales de official.m3u a backup.m3u por ID global y reordena la lista oficial. Usar cuando el usuario pida pasar canales a respaldo, mover fuentes caidas a backup, o quitar entradas de official dejandolas en backup.m3u."
---

# Mover canales a backup.m3u

Workflow para sacar entradas de `official.m3u` y guardarlas en `backup.m3u`.

## Requisito obligatorio: IDs del usuario

**No ejecutar sin IDs.** El usuario debe indicar uno o más IDs globales de `official.m3u` (el numero al inicio de `tvg-name`, ej. `88` en `88 Star Channel 1`).

Si el mensaje no incluye IDs, pedirlos y detenerse. No inferir IDs ni buscar canales por nombre.

Formatos aceptados del usuario:

- Lista separada por comas: `88, 91, 102`
- Lista separada por espacios: `88 91 102`
- Rango: `88-92` (expandir a `88 89 90 91 92`)

## Ejecucion

Desde la raiz del repo:

```bash
python3 scripts/move_to_backup.py <id1> <id2> ...
```

Ejemplo:

```bash
python3 scripts/move_to_backup.py 88 91
```

El script:

1. Extrae de `official.m3u` las entradas cuyo ID global coincida.
2. Las agrega a `backup.m3u` sin el ID global en `tvg-name` ni en el nombre visible (formato `Star Channel 1`).
3. Omite URLs ya presentes en `backup.m3u`.
4. Reagrupa `backup.m3u` por `group-title`.
5. Ejecuta `python3 scripts/clean_m3u.py` para reordenar y recalcular IDs en `official.m3u`.

Si algun ID no existe, el script falla; informar el error al usuario y no decir "trabajo realizado".

## Respuesta al finalizar (obligatorio)

Al terminar el trabajo con exito, la respuesta al usuario debe ser **exactamente** una sola linea:

```text
trabajo realizado
```

Nada mas. Sin resumen, sin listado de canales movidos, sin conteos, sin explicaciones, sin preguntas de seguimiento.

## Errores comunes

- **Ejecutar sin IDs**: prohibido; pedir los IDs primero.
- **Buscar por nombre en vez de ID**: prohibido; exigir el ID global.
- **Editar las listas a mano**: usar siempre `move_to_backup.py`.
- **Olvidar el cleanup**: el script ya ejecuta `clean_m3u.py`; no hace falta correrlo aparte.

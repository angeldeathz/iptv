---
name: m3u-remove-channels
description: "Elimina canales de official.m3u por ID global y recalcula los IDs correlativos. Usar cuando el usuario pida quitar, borrar o eliminar canales de la lista oficial, sacar fuentes que no funcionan, o limpiar entradas probadas en TV."
---

# Eliminar canales de official.m3u

Workflow para quitar entradas de `official.m3u` de forma permanente (no van a `backup.m3u`).

## Requisito obligatorio: IDs del usuario

**No ejecutar sin IDs.** El usuario debe indicar uno o más IDs globales de `official.m3u` (el número al inicio de `tvg-name`, ej. `88` en `88 Star Channel 1`).

Si el mensaje no incluye IDs:

1. Pedirlos explícitamente.
2. Detenerse. No inferir IDs ni buscar canales por nombre.

Formatos aceptados del usuario:

- Lista separada por comas: `88, 91, 102`
- Lista separada por espacios: `88 91 102`
- Rango: `88-92` (expandir a `88 89 90 91 92`)

### Ayudar al usuario a identificar IDs

Si el usuario no sabe qué ID corresponde a un canal, puedes listar entradas actuales sin ejecutar la eliminación:

```bash
grep -E '^#EXTINF' official.m3u | head -30
```

O, si acaba de probar en TV y quiere quitar caídos:

```bash
python3 scripts/check_channels.py
```

Aun así, **no eliminar hasta que el usuario confirme los IDs**.

## Ejecución

Desde la raíz del repo:

```bash
python3 scripts/remove_channels.py <id1> <id2> ...
```

Ejemplo:

```bash
python3 scripts/remove_channels.py 88 91
```

El script:

1. Extrae de `official.m3u` las entradas cuyo ID global coincida.
2. Las elimina de forma permanente (no se copian a `backup.m3u`).
3. Ejecuta `python3 scripts/clean_m3u.py` para reordenar categorías, recalcular IDs correlativos y deduplicar URLs.

Si algún ID no existe, el script falla; informar el error al usuario y no decir "trabajo realizado".

## Diferencia con m3u-to-backup

| Acción | Skill / script |
|--------|----------------|
| Quitar de official y guardar en backup | `m3u-to-backup` → `move_to_backup.py` |
| Quitar de official sin respaldo | `m3u-remove-channels` → `remove_channels.py` |

Si el usuario quiere conservar la fuente por si vuelve a funcionar, usar `m3u-to-backup`, no esta skill.

## Respuesta al usuario (obligatorio)

Tras una eliminación exitosa, la respuesta completa al usuario es **solo** esta línea, sin texto antes ni después:

```text
trabajo realizado
```

Prohibido añadir resúmenes, conteos, nombres de canales, IDs eliminados, confirmaciones extra o cualquier otra frase. Ni un punto más.

## Errores comunes

- **Ejecutar sin IDs**: prohibido; pedir los IDs primero.
- **Buscar por nombre en vez de ID**: prohibido; exigir el ID global.
- **Editar official.m3u a mano**: usar siempre `remove_channels.py`.
- **Confundir con backup**: si el usuario quiere respaldo, usar `move_to_backup.py`.
- **Olvidar el cleanup**: el script ya ejecuta `clean_m3u.py`; no hace falta correrlo aparte.

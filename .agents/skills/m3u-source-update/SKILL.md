---
name: m3u-source-update
description: "Busca canales en las listas M3U de origen con scripts/search_sources.py y agrega TODAS las fuentes encontradas a official.m3u para que el usuario las pruebe en TV. Usar cuando el usuario pida buscar fuentes, agregar respaldos, reemplazar un canal caido, o actualizar la lista desde servidores de origen."
---

# Actualizar official.m3u desde fuentes de origen

Workflow para encontrar señales en servidores Astra y volcarlas en `official.m3u`.

## Politica principal

**Agregar TODAS las fuentes encontradas**, no elegir solo una. El usuario las prueba en su TV y luego elimina las que no sirvan.

Excepcion: si el usuario pide explicitamente reemplazar una sola URL o agregar solo una fuente, seguir esa instruccion.

## Cuando usar esta skill

- El usuario pide buscar un canal en las fuentes de origen.
- Hay que agregar respaldos o variantes para testear en TV.
- Hay que reemplazar una URL caida (solo si el usuario lo pide).
- Hay que incorporar un canal nuevo desde los servidores verificados.

Para criterios editoriales (prioridad LATAM, orden de parrilla), combinar con la skill `m3u-lineup`.

## Paso 1: Buscar coincidencias

Ejecutar desde la raiz del repo:

```bash
python3 scripts/search_sources.py "<consulta>" --json
```

Preferir `--json` para no omitir coincidencias al parsear la salida.

Reglas de consulta:

- Usar el nombre limpio del canal, sin prefijos de pais ni resolucion (ej. `star channel`, no `CL: Star Channel HD`).
- Si hay muchos resultados irrelevantes, afinar la consulta o usar `--regex`.
- No usar `--source` salvo que el usuario limite la busqueda a un servidor.

## Paso 2: Agregar todas las fuentes (no filtrar)

Recorrer **todas** las coincidencias de **todas** las fuentes disponibles.

Para cada match:

| Condicion | Accion |
|-----------|--------|
| URL ya en `official.m3u` (`in_official: true`) | **Omitir** — ya esta para probar |
| URL nueva | **Agregar** como variante del canal |
| Fuente con error (timeout, lista vacia) | **Omitir** — no hay URL que agregar |

No descartar candidatos por calidad, servidor o audio. El usuario decide en TV.

Orden sugerido al insertar (solo visual; `clean_m3u.py` reordena por calidad):

1. Resolucion mas alta primero (`1080p` / `FHD` / `HD` antes que `SD`).
2. Dentro de la misma calidad, mantener el orden del JSON de `search_sources.py`.

## Paso 3: Editar official.m3u

### Canal ya existente

1. Localizar el bloque del canal en `official.m3u` (por nombre o ID).
2. Insertar **debajo del ultimo bloque de ese canal** (o al final del grupo si no hay variantes) un `#EXTINF` + URL por cada fuente nueva.
3. **No reemplazar** la URL principal salvo que el usuario lo pida.
4. Reutilizar el `tvg-logo` del canal existente en cada bloque nuevo.

### Canal nuevo (no esta en la lista)

1. Insertar todos los bloques en la seccion tematica adecuada.
2. Usar el `tvg-logo` del origen si existe; si no, dejar sin logo (el cleanup puede resolverlo).

### Plantilla por fuente nueva

```text
#EXTINF:-1 group-title="Peliculas" tvg-name="Star Channel HD",Star Channel HD
http://servidor/play/xxxx/index.m3u8
```

Si el origen trae `#EXTVLCOPT:http-user-agent=...`, copiar esas lineas entre `#EXTINF` y la URL.

Reglas al copiar metadatos del origen:

- No copiar `tvg-id`.
- Usar el `display_name` del origen como nombre provisional en `#EXTINF`.
- No preocuparse por IDs correlativos, indices de repeticion ni `group-title` final: `clean_m3u.py` los recalcula y agrupa variantes del mismo canal.

### Quitar canal

Solo si el usuario lo pide: eliminar bloque completo (`#EXTINF`, `#EXTVLCOPT` si hay, URL).

## Paso 4: Limpiar la lista (obligatorio)

Tras cualquier edicion de `official.m3u`:

```bash
python3 scripts/clean_m3u.py
```

Verificar que el script termina sin errores. Tras el cleanup, variantes del mismo canal quedan como `N Canal X 1`, `N Canal X 2`, etc., ordenadas por calidad.

## Paso 5: Confirmar al usuario

Resumir:

1. Consulta usada.
2. **Total agregadas** vs **ya existentes** vs **omitidas** (fuente caida).
3. Rango de IDs finales del canal tras cleanup (ej. `88 Star Channel 1` … `88 Star Channel 9`).
4. Listado breve: servidor + URL de cada fuente **nueva** agregada.
5. Recordar que puede probar en TV y pedir eliminar las que fallen.

## Checklist

```
- [ ] Ejecutar search_sources.py --json
- [ ] Agregar TODAS las URLs nuevas (sin filtrar por calidad)
- [ ] Omitir solo URLs ya presentes o fuentes no disponibles
- [ ] Ejecutar clean_m3u.py
- [ ] Informar cuantas fuentes se agregaron y sus IDs finales
```

## Comandos utiles

```bash
# Busqueda con salida estructurada (usar siempre para agregar fuentes)
python3 scripts/search_sources.py "star channel" --json

# Busqueda legible para revisar rapido
python3 scripts/search_sources.py "espn 2"

# Verificar canales caidos despues de probar en TV
python3 scripts/check_channels.py
```

## Errores comunes

- **Elegir solo la mejor fuente**: esta skill agrega todas; el usuario prueba en TV.
- **Editar nombres/IDs a mano**: dejar que `clean_m3u.py` los normalice.
- **Olvidar el cleanup**: rompe taxonomia, IDs y deduplicacion.
- **Reemplazar en vez de agregar**: solo reemplazar si el usuario lo pide explicitamente.
- **Copiar tvg-id del origen**: prohibido; el cleanup lo quita igual.

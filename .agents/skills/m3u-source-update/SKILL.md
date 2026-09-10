---
name: m3u-source-update
description: "Busca canales en las listas M3U de origen con scripts/search_sources.py y actualiza official.m3u (reemplazar URL, agregar respaldo o canal nuevo). Usar cuando el usuario pida buscar fuentes, reemplazar un canal caido, agregar respaldo, o actualizar la lista desde servidores de origen."
---

# Actualizar official.m3u desde fuentes de origen

Workflow para encontrar señales en servidores Astra y aplicarlas en `official.m3u`.

## Cuando usar esta skill

- El usuario pide buscar un canal en las fuentes de origen.
- Hay que reemplazar una URL caida o de baja calidad.
- Hay que agregar un respaldo del mismo canal.
- Hay que incorporar un canal nuevo desde los servidores verificados.

Para criterios editoriales (prioridad LATAM, 1080p, orden de parrilla), combinar con la skill `m3u-lineup`.

## Paso 1: Buscar coincidencias

Ejecutar desde la raiz del repo:

```bash
python3 scripts/search_sources.py "<consulta>"
```

Reglas de consulta:

- Usar el nombre limpio del canal, sin prefijos de pais ni resolucion (ej. `star channel`, no `CL: Star Channel HD`).
- Si hay muchos resultados, acotar con `--source <host:puerto>`.
- Para analisis estructurado, usar `--json`.

Interpretar la salida:

- `EN LISTA -> ID N` = esa URL ya esta en `official.m3u`.
- `(nueva fuente)` = candidata para agregar o reemplazar.
- Fuentes no disponibles al final = ignorar salvo que el usuario pida revisarlas.

## Paso 2: Elegir la mejor fuente

Prioridad de seleccion (de mayor a menor):

1. Resolucion mas alta (`1080p` / `FHD` / `HD` sobre `SD`).
2. Nombre estable y sin geo-block innecesario.
3. Servidor ya usado en la lista (menos sorpresas de compatibilidad).
4. Señal en espanol o LATAM; evitar audio doble con ingles primero si el usuario usa Smart TV.

Si hay varias opciones validas, elegir la principal y dejar otras como respaldo solo si el usuario lo pidio o si el canal ya tiene variantes en la lista.

No adoptar una fuente si la URL ya existe en otro canal (el cleanup la eliminara).

## Paso 3: Determinar el tipo de cambio

| Situacion | Accion |
|-----------|--------|
| Reemplazar fuente principal | Cambiar solo la linea URL del bloque existente |
| Agregar respaldo | Duplicar el bloque `#EXTINF` + URL debajo del canal, con nombre provisional del origen |
| Canal nuevo | Insertar bloque `#EXTINF` + URL en la seccion tematica correcta |
| Quitar canal | Eliminar bloque completo (`#EXTINF`, `#EXTVLCOPT` si hay, URL) |

### Reemplazar URL (caso mas comun)

1. Localizar el canal en `official.m3u` por ID o nombre (`tvg-name`).
2. Sustituir la linea de URL por la elegida.
3. Conservar `#EXTINF`, `tvg-logo`, `#EXTVLCOPT` existentes salvo que el origen requiera `user-agent` distinto.

### Agregar desde origen

Plantilla minima (el cleanup normaliza nombres, grupos e IDs):

```text
#EXTINF:-1 group-title="Peliculas" tvg-name="Star Channel HD",Star Channel HD
http://servidor/play/xxxx/index.m3u8
```

Si el origen trae `#EXTVLCOPT:http-user-agent=...`, copiar esas lineas entre `#EXTINF` y la URL.

Reglas al copiar metadatos del origen:

- No copiar `tvg-id`.
- Puedes copiar `tvg-logo` si mejora el canal o falta logo.
- No preocuparse por IDs correlativos ni `group-title` final: `clean_m3u.py` los recalcula.

## Paso 4: Limpiar la lista (obligatorio)

Tras cualquier edicion de `official.m3u`:

```bash
python3 scripts/clean_m3u.py
```

Verificar que el script termina sin errores. Revisar diff: IDs recalculados, duplicados eliminados, grupos en PascalCase.

## Paso 5: Confirmar al usuario

Resumir en lenguaje claro:

1. Consulta usada.
2. Fuente elegida (servidor + URL).
3. Tipo de cambio (reemplazo, respaldo, alta, baja).
4. ID final del canal en `official.m3u` tras el cleanup.
5. Alternativas descartadas solo si aportan contexto (ej. misma calidad en otro servidor).

## Checklist

```
- [ ] Ejecutar search_sources.py con consulta adecuada
- [ ] Elegir fuente segun calidad y estabilidad
- [ ] Editar official.m3u (solo lo necesario)
- [ ] Ejecutar clean_m3u.py
- [ ] Informar ID, URL y tipo de cambio al usuario
```

## Comandos utiles

```bash
# Busqueda basica
python3 scripts/search_sources.py "espn 2"

# Una sola fuente
python3 scripts/search_sources.py "mega" --source 38.44.109.41:8003

# Salida JSON
python3 scripts/search_sources.py "star channel" --json

# Verificar canales caidos despues de un cambio masivo
python3 scripts/check_channels.py
```

## Errores comunes

- **Editar nombres/IDs a mano**: dejar que `clean_m3u.py` los normalice.
- **Olvidar el cleanup**: rompe taxonomia, IDs y deduplicacion.
- **Agregar URL duplicada**: el cleanup la elimina; mejor reemplazar o elegir URL unica.
- **Copiar tvg-id del origen**: prohibido en esta lista; el cleanup lo quita igual.

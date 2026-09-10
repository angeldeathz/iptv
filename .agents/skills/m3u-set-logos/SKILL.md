---
name: m3u-set-logos
description: "Asigna URLs de iconos reales (tvg-logo) en official.m3u por ID global del canal. Usar cuando el usuario pida poner logos, iconos, imagenes o tvg-logo a canales especificos por ID, corregir logos rotos o reemplazar placeholders."
---

# Asignar logos reales en official.m3u

Workflow para poner `tvg-logo` con iconos reales del canal, identificando entradas por **ID global** (primer numero de `tvg-name`, ej. `88` en `88 Star Channel 1`).

## Requisito obligatorio: IDs del usuario

**No ejecutar sin IDs.** El usuario debe indicar uno o mas IDs globales.

Si el mensaje no incluye IDs:

1. Pedirlos explicitamente.
2. Detenerse. No inferir IDs ni buscar canales por nombre para aplicar logos.

Formatos aceptados del usuario:

- Lista separada por comas: `5, 10, 88`
- Lista separada por espacios: `5 10 88`
- Rango: `88-92` (expandir a `88 89 90 91 92`)

### Ayudar al usuario a identificar IDs

Si no sabe que ID corresponde a un canal, listar entradas sin modificar nada:

```bash
grep -E '^#EXTINF' official.m3u | head -40
```

Aun asi, **no actualizar logos hasta que el usuario confirme los IDs**.

## Paso 1: Resolver logos automaticamente

Desde la raiz del repo:

```bash
python3 scripts/set_logos.py <id1> <id2> ... --json
```

Ejemplo:

```bash
python3 scripts/set_logos.py 5 10 88 --json
```

El script:

1. Localiza los canales por ID en `official.m3u`.
2. Obtiene el nombre limpio del canal (sin indice de repeticion).
3. Busca logo en este orden:
   - `LOGO_LIBRARY` de `scripts/clean_m3u.py` (curado, preferido)
   - Listas M3U de origen (`search_sources.py`) emparejando por nombre limpio
4. Elige la mejor URL (prioriza Wikimedia, `cdn.m3u.cl`, HTTPS).
5. Aplica el mismo logo a **todas las variantes** del mismo canal en `official.m3u`.

Si el usuario entrega una URL concreta:

```bash
python3 scripts/set_logos.py 88 --logo "https://upload.wikimedia.org/..."
```

## Paso 2: Completar logos no encontrados

Si `--json` devuelve `"source": "not_found"` o el script termina con codigo `2`:

1. Buscar logo oficial del canal en fuentes confiables:
   - Wikimedia Commons
   - `cdn.m3u.cl/logo/...`
   - Logopedia (como respaldo)
2. Evitar placeholders genericos, iconos rotos o URLs sin relacion con el canal.
3. Aplicar manualmente con `--logo` o editando solo `tvg-logo` en `#EXTINF`.
4. Si el logo es estable y reutilizable, agregarlo a `LOGO_LIBRARY` en `scripts/clean_m3u.py`.

No inventar URLs. Si no hay logo confiable, informarlo y dejar el canal sin cambio.

## Paso 3: Limpiar la lista (obligatorio)

Tras escribir cambios en `official.m3u`:

```bash
python3 scripts/clean_m3u.py
```

`clean_m3u.py` preserva logos existentes y propaga el logo a variantes hermanas que sigan vacias.

## Paso 4: Confirmar al usuario

Resumir:

1. IDs solicitados.
2. Canales actualizados (nombre limpio + logo URL).
3. Variantes afectadas (cuantas entradas recibieron el logo).
4. Canales sin logo encontrado, si los hubo.
5. Fuente del logo (`logo_library`, `source_playlists`, `manual`, busqueda web).

## Checklist

```
- [ ] Confirmar IDs con el usuario
- [ ] Ejecutar set_logos.py --json
- [ ] Resolver manualmente los not_found (si hay)
- [ ] Ejecutar clean_m3u.py
- [ ] Informar logos aplicados y pendientes
```

## Comandos utiles

```bash
# Simular sin escribir archivo
python3 scripts/set_logos.py 5 10 --dry-run --json

# Forzar logo especifico
python3 scripts/set_logos.py 88 --logo "https://cdn.m3u.cl/logo/1234_Channel.png"

# Ver logos actuales de un canal
grep -E '^#EXTINF.*tvg-name="88 ' official.m3u
```

## Errores comunes

- **Ejecutar sin IDs**: prohibido; pedir los IDs primero.
- **Cambiar solo una variante**: el script propaga logo al canal completo; mantener consistencia.
- **Usar iconos dudosos**: preferir logos oficiales o de repositorios estables.
- **Olvidar clean_m3u.py**: puede dejar variantes sin logo o formato inconsistente.
- **Sobrescribir un logo bueno con uno peor**: si ya hay Wikimedia/`cdn.m3u.cl`, no reemplazar salvo que el usuario lo pida.

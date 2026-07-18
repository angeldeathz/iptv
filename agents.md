# Guía para Agentes - Mantenimiento de official.m3u

Este repositorio contiene una lista de canales de televisión curada en el archivo `official.m3u`. Para asegurar que la grilla de canales permanezca limpia, consistente y correctamente formateada, siempre que realices cambios o agregues nuevos canales debes ejecutar el script de limpieza automatizado.

## Reglas de Formato para `official.m3u`

1. **Orden del Lineup (Categorías)**: Los canales deben ordenarse según grupos temáticos estandarizados (de mayor a menor prioridad):
   1. `Nacionales`
   2. `Regionales`
   3. `Infantiles`
   4. `Peliculas`
   5. `Series`
   6. `Deportes`
   7. `Noticias`
   8. `Musica`
   9. `Documentales`
   10. `Variedades`
   11. `Internacionales`

2. **Atributo `group-title`**: Todos los `group-title` deben estar en **PascalCase** (ej. `Nacionales`, `Peliculas`, `Series`). Nunca usar MAYÚSCULAS completas ni minúsculas completas.

3. **Sin Prefijos ni Sufijos de País**: El nombre del canal no debe incluir códigos de países ni su pertenencia geográfica (ej. `CL: Chilevision FHD` debe ser `Chilevision FHD`, sin prefijos como `CL:`, `MX:`, `BR:`, `USA:`, `US:`, `ES:`, ni sufijos como `MX`, `Brazil`, `BR`, `USA`, etc.).

4. **Sin Etiquetas de Resolución**: Las etiquetas de resolución y calidad (`HD`, `FHD`, `SD`, `HEVC`, `1080p`, `720p`, `576p`, `480p`, `[Geo-blocked]`, etc.) se deben remover del nombre limpio del canal para agrupar las señales repetidas.

5. **Identificadores (IDs) de Nombre**:
   - Cada canal debe comenzar con un ID global incremental (empezando en `1`).
   - Cada canal debe terminar con un ID de repetición (empezando en `1`). Este ID se incrementa de forma secuencial únicamente para copias o calidades alternativas del mismo canal (ej. si hay 4 variantes de "Canal 13", se formatearán como `Canal 13 1`, `Canal 13 2`, `Canal 13 3`, `Canal 13 4`).
   - El formato final del nombre visible es: `<global_id> <clean_name> <repetition_index>`.

6. **Atributo `tvg-name`**: Todos los canales deben incluir el atributo `tvg-name` en la línea `#EXTINF`. El formato es `<global_id> <clean_name> <repetition_index>` (ej. `1 Chilevision 1`, `4 Canal 13 1`). Cada `tvg-name` debe ser único en toda la lista; ninguno puede repetirse. El ID global correlativo siempre va al inicio del nombre.

7. **Atributo `tvg-id`**: No incluir `tvg-id` en ningún canal. Esta lista se usa en apps IPTV de TV sin EPG, por lo que el atributo no es necesario.

8. **Priorización de Calidad**: Al agrupar variantes duplicadas del mismo canal, se deben ordenar con la mejor resolución disponible primero (priorizando HEVC > FHD/1080p > HD/720p > SD/576p/480p).

9. **URLs Únicas**: No puede haber dos canales con la misma URL de stream. Si se agregan entradas duplicadas, el script de limpieza elimina automáticamente las copias y conserva solo una (priorizando mejor calidad en el nombre y, en empate, la primera aparición en el archivo). Tras la deduplicación, se recalculan los IDs correlativos.

---

## Ejecución del Script de Limpieza

Para automatizar la aplicación de estas reglas (incluyendo reordenamiento, normalización de nombres, actualización de IDs y formateo general), simplemente ejecuta el script de Python provisto en el espacio de trabajo:

```bash
python3 scripts/clean_m3u.py
```

> [!IMPORTANT]
> **Es obligatorio ejecutar este script cada vez que modifiques o agregues canales en `official.m3u`.** Esto evita inconsistencias en la grilla, elimina URLs duplicadas y asegura que los IDs y el orden sean actualizados de forma totalmente correcta e idempotente.

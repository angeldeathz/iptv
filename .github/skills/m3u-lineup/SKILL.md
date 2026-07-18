---
name: m3u-lineup-curator
description: "Use when curating IPTV M3U playlists, especially official.m3u, to prioritize Latin American channels, prefer 1080p sources, and order channels like a provider lineup (Movistar, DIRECTV, Claro)."
---

# Curador de listas M3U

Esta skill define cómo mantener `official.m3u` como una parrilla de proveedor de TV: limpia, consistente y orientada a Latinoamérica.

## Objetivo

1. Tratar `official.m3u` como una grilla editorial, no como un volcado de enlaces.
2. Priorizar canales de Latinoamérica, con foco en señales hispanohablantes y panregionales.
3. Dejar Brasil y otros mercados no prioritarios al final, solo si aportan cobertura única o necesaria.
4. Preferir siempre la mejor calidad disponible, con prioridad clara para `1080p`.
5. Ordenar por categorías como lo hace un proveedor: nacionales, infantiles, películas, series, deportes, noticias, música, documentales y otros.

## Criterios de selección

1. Si un canal tiene varias fuentes, elegir primero la más estable y con mejor resolución.
2. El orden de preferencia de calidad es `1080p`, `720p`, `576p`, `480p`, `SD`.
3. Mantener variantes secundarias solo cuando sirvan como respaldo real o aporten una región distinta dentro de LATAM.
4. Evitar duplicados innecesarios. Si hay más de una entrada para el mismo canal, la primera debe ser la principal.
5. No inventar metadatos: conservar `tvg-id`, `tvg-name`, `tvg-logo`, `group-title`, `user-agent` y `#EXTVLCOPT` cuando existan.

## Orden de la grilla

Sigue esta lógica de ordenación:

1. Canales nacionales y abiertos del mercado objetivo.
2. Canales regionales o locales relevantes.
3. Infantiles.
4. Películas.
5. Series y entretenimiento.
6. Deportes.
7. Noticias e información.
8. Música, estilo de vida y cultura.
9. Documentales y educación.
10. Internacionales y variantes secundarias.

Dentro de cada grupo:

1. Canal principal primero.
2. Versión `HD` o `1080p` inmediatamente después.
3. Versiones `720p`, `576p` y `SD` al final.
4. Si hay variantes por región, conservar el bloque de Latinoamérica hispanohablante antes que otras variantes.

## Taxonomía sugerida de grupos

Usa categorías consistentes y reconocibles por el usuario:

1. `NACIONALES`
2. `REGIONALES`
3. `INFANTILES`
4. `PELICULAS`
5. `SERIES`
6. `DEPORTES`
7. `NOTICIAS`
8. `MUSICA`
9. `DOCUMENTALES`
10. `VARIEDADES`
11. `INTERNACIONALES`

## Reglas editoriales

1. No ordenar alfabéticamente salvo que el usuario lo pida.
2. No mezclar Brasil dentro del bloque principal de Latinoamérica hispanohablante.
3. No mover canales solo por nombre si eso rompe la lógica de proveedor.
4. Si un canal está duplicado con calidades distintas, dejar la mejor versión más arriba.
5. Preservar la sintaxis M3U exacta para no romper reproductores.

## Resultado esperado

Cuando esta skill se use sobre `official.m3u`, el resultado debe parecer una lista curada por un operador de TV: orden por bloques temáticos, prioridad LATAM, calidad alta primero y estructura estable.

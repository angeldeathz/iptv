---
name: check-dead
description: >-
  Comprueba qué canales de official.m3u no responden (URL caída). Usar cuando
  pidan canales muertos, caídos, abajo, fuera de línea, sondeo de la parrilla o
  revisar official.m3u sin tocar la línea de canales.
---

# Canales caídos en official.m3u

## Regla única

No sondees URLs a mano, no uses curl en bucle ni edites `official.m3u`. Solo ejecuta el script del repositorio y resume su salida.

Desde la raíz de **iptv**:

```bash
python3 scripts/check_dead.py
```

- Necesita red (`full_network` en el sandbox).
- Salida: un objeto JSON en stdout con clave `dead` (lista de entradas caídas).
- Cada elemento incluye `id`, `name`, `group`, `url`, `reason` (`timeout`, `http_404`, `no_stream`, etc.).
- Exit code `1` si hay al menos un canal muerto; `0` si todos responden.
- Playlist distinta (opcional): `python3 scripts/check_dead.py /ruta/otra.m3u`

## Respuesta al usuario

- Si `dead` está vacío: una línea indicando que la parrilla responde en ese sondeo.
- Si hay muertos: lista breve por ID y nombre (y `reason` solo si ayuda); no vuelques el JSON completo salvo que lo pida.

No uses `scripts/iptv.py` para este sondeo salvo que, después, el usuario pida cambiar la parrilla (eso sigue en la skill `iptv`).
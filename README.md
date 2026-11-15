# Alevín 1º Año · Primera FFCV Alicante · Grup 2

Web para consultar partidos, horarios, campos y clasificación. Los datos se actualizan solos cada día.

```
GitHub Actions (cron diario) ──► API JSON de ffcv.es ──► Supabase (Postgres)
                                                              │
                         GitHub Pages (docs/index.html) ◄─────┘  lectura con clave anon
```

No hace falta scraping de HTML: `ffcv.es/competiciones` carga los datos desde estos endpoints JSON:

| Dato | Endpoint |
|---|---|
| Jornadas y fechas | `api/filtros/jornadas_fetch.php?cod_grupo=…` |
| Partidos de una jornada | `api/partidos/resultados_por_grupo_jornada_data.php?cod_temporada=…&cod_competicion=…&cod_grupo=…&cod_jornada=…` |
| Clasificación | `api/clasificaciones/clasificaciones_ajax.php?cod_grupo=…&cod_jornada=…` |
| Acta (alineaciones) | `api/partidos/ficha_partido_ajax.php?cod_partido=…` |

## Pestaña Costa City E

El script lee el acta de cada partido jugado por los equipos de `FFCV_EQUIPOS` (por defecto el Costa City E, `29538208`) y guarda los convocados en la tabla `alineaciones`. La web calcula para cada jugador las convocatorias, las veces que ha sido titular o suplente, las capitanías y los resultados del equipo con él convocado. Las actas de fútbol 8 de la FFCV no recogen goleadores, tarjetas ni cambios, así que esos datos no existen.

Los jugadores son menores, así que solo se guarda el nombre y la inicial del primer apellido. Las fotos de las actas no se guardan.

## Escudos

El script guarda en `equipos.escudo_url` la dirección del escudo oficial en ffcv.es, y la web lo muestra directamente. Si algún escudo no carga (por ejemplo, si la FFCV bloquea que otras webs enlacen sus imágenes), aparece en su lugar una insignia de color con las iniciales del equipo.

## Puesta en marcha (unos 15 minutos)

1. **Supabase.** Crea un proyecto gratuito en supabase.com. En *SQL Editor*, pega y ejecuta `supabase/schema.sql`. En *Project Settings → API*, copia la *Project URL*, la clave `anon` y la clave `service_role`.
2. **GitHub.** Crea un repositorio y sube esta carpeta tal cual.
3. **Secretos.** En el repo, ve a *Settings → Secrets and variables → Actions → New repository secret* y añade:
   - `SUPABASE_URL` con la Project URL
   - `SUPABASE_SERVICE_KEY` con la clave `service_role` (nunca la pongas en la web)
4. **Primera carga.** En la pestaña *Actions*, abre *Actualizar datos FFCV* y pulsa *Run workflow*. Comprueba en Supabase (*Table Editor*) que se han llenado las tablas.
5. **Web.** En `docs/index.html`, rellena `SUPABASE_URL` y `SUPABASE_ANON_KEY` (la clave `anon` es pública y con las políticas del esquema solo permite leer). Haz commit.
6. **GitHub Pages.** En *Settings → Pages*, elige *Deploy from a branch*, rama `main`, carpeta `/docs`. La web quedará en `https://TU_USUARIO.github.io/NOMBRE_REPO/`.

## Probar en local

```bash
DRY_RUN=1 python3 scraper/scrape.py
```

## Otro grupo o categoría

Abre el grupo en `ffcv.es/competiciones`. La URL lleva `cod_temporada`, `cod_competicion` y `cod_grupo`. Cambia esos tres valores en `.github/workflows/actualizar.yml` y `GRUPO` en `docs/index.html`. Para seguir a otro equipo, pon su código (sale en la ficha del partido) en `FFCV_EQUIPOS` y en `MI` dentro de `docs/index.html`.

## Horario de actualización

Una vez al día a las 23:17, y los sábados y domingos también a las 13:17 y 19:17 (hora de Madrid en invierno). Se cambia en el `cron` del workflow. GitHub puede retrasar unos minutos las ejecuciones programadas.

## Si la FFCV bloquea las peticiones

Los endpoints son públicos (los usa su propia web), pero no están documentados y su `robots.txt` no invita a automatizar. Por eso el script hace pocas peticiones (unas 25 por ejecución) y con pausas. Si un día GitHub Actions empieza a recibir errores o HTML en vez de JSON, la FFCV estará filtrando las IPs de servidores. Hay dos alternativas:
- ejecutar `scraper/scrape.py` desde un ordenador de casa con una tarea programada (cron o el Programador de tareas de Windows);
- hacer las peticiones desde un navegador sin interfaz con Playwright.

Datos no oficiales, extraídos de la web de la FFCV. Ante cualquier duda, manda ffcv.es.

## Botón «Forzar actualización»

La web llama a la función de Supabase `actualizar` (`supabase/functions/actualizar/index.ts`), que lanza el workflow de GitHub. Para que el token de GitHub no quede a la vista en la web pública, la función lo guarda como secreto en Supabase. Además, no deja lanzar otra actualización si ya hay una en marcha o si la última empezó hace menos de 10 minutos. Mientras la función no esté instalada, el botón abre la página del workflow en GitHub.

Para activarla:
1. En GitHub, ve a *Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token*. En *Repository access* elige *Only select repositories → alevin*, y en *Permissions → Repository permissions → Actions* elige *Read and write*. Copia el token.
2. En Supabase, ve a *Edge Functions → Secrets* y añade `GITHUB_TOKEN` con ese token.
3. En *Edge Functions → Deploy a new function → Via Editor*, ponle de nombre `actualizar`, pega el contenido de `index.ts` y despliégala. Después, en los ajustes de la función, desactiva *Verify JWT* (*Enforce JWT verification*).

#!/usr/bin/env python3
"""
Descarga calendario, resultados y clasificación de un grupo de la FFCV
(endpoints JSON que usa ffcv.es/competiciones) y los guarda en Supabase.

Variables de entorno:
  SUPABASE_URL          https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY  secret key (sb_secret_…) o la antigua service_role
  FFCV_TEMPORADA        22         (2026/27)
  FFCV_COMPETICION      905432151  (Primera FFCV Aleví 1r. any Alacant)
  FFCV_GRUPO            905432153  (Grup 2)
  FFCV_EQUIPOS          29538208   (equipos de los que guardar alineaciones,
                                    separados por comas; Club Costa City E)
  FFCV_MODO             auto (por defecto: directo y, si da 403, navegador),
                        directo o navegador (Chromium con Playwright)
  DRY_RUN=1             solo imprime, no escribe en Supabase

El modo directo solo usa la biblioteca estándar; el modo navegador necesita
`pip install playwright && playwright install chromium`.
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime

API = "https://ffcv.es/competiciones/api/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

TEMPORADA   = os.environ.get("FFCV_TEMPORADA", "22")
COMPETICION = os.environ.get("FFCV_COMPETICION", "905432151")
GRUPO       = os.environ.get("FFCV_GRUPO", "905432153")
EQUIPOS     = [e.strip() for e in os.environ.get("FFCV_EQUIPOS", "29538208").split(",") if e.strip()]
DRY_RUN     = os.environ.get("DRY_RUN") == "1"


def nombre_corto(n):
    """'MUÑOZ PASCUAL, MARTIN' -> 'Martin M.' (son menores: no guardamos el nombre completo)"""
    if "," in n:
        apellidos, nombre = [x.strip() for x in n.split(",", 1)]
    else:
        apellidos, nombre = "", n.strip()
    nombre = " ".join(w.capitalize() for w in nombre.split()[:1])
    return f"{nombre} {apellidos[:1].upper()}." if apellidos else nombre


MODO = os.environ.get("FFCV_MODO", "auto")   # auto | directo | navegador
_page = None


def _navegador():
    """Abre Chromium sin ventana en ffcv.es y devuelve la página (Playwright)."""
    global _page
    if _page is None:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="es-ES")
        _page = ctx.new_page()
        _page.goto("https://ffcv.es/competiciones/", wait_until="domcontentloaded", timeout=60000)
        print("  (modo navegador: Chromium abierto en ffcv.es)")
    return _page


def get_json_navegador(url):
    page = _navegador()
    res = page.evaluate("""async (u) => {
        const r = await fetch(u, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
        return [r.status, await r.text()];
    }""", url)
    if res[0] != 200:
        raise RuntimeError(f"HTTP {res[0]}")
    return json.loads(res[1])


def descargar_imagen(url):
    """Descarga una imagen y la devuelve como data URI (o None si falla)."""
    try:
        if MODO == "navegador":
            return _navegador().evaluate("""async (u) => {
                const r = await fetch(u);
                if (!r.ok) return null;
                const b = await r.blob();
                if (b.size > 400000) return null;
                return await new Promise(ok => { const f = new FileReader(); f.onload = () => ok(f.result); f.readAsDataURL(b); });
            }""", url)
        import base64
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://ffcv.es/competiciones/"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data, tipo = r.read(), r.headers.get_content_type()
        if len(data) > 400000 or not tipo.startswith("image/"):
            return None
        return f"data:{tipo};base64," + base64.b64encode(data).decode()
    except Exception as e:
        print(f"  aviso: escudo {url}: {e}", file=sys.stderr)
        return None


def get_json(path, **params):
    global MODO
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    if MODO == "navegador":
        for intento in range(3):
            try:
                return get_json_navegador(url)
            except Exception as e:
                print(f"  aviso: {path} (navegador) intento {intento+1}: {e}", file=sys.stderr)
                time.sleep(3 * (intento + 1))
        raise RuntimeError(f"No se pudo leer {url} ni con navegador")
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://ffcv.es/competiciones/",
        "X-Requested-With": "XMLHttpRequest",
    })
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                txt = r.read().decode("utf-8", "replace")
            return json.loads(txt)
        except Exception as e:  # red, 5xx o respuesta no-JSON (bloqueo)
            print(f"  aviso: {path} intento {intento+1}: {e}", file=sys.stderr)
            if MODO == "auto" and "403" in str(e):
                print("  la FFCV rechaza la petición directa: paso a modo navegador")
                MODO = "navegador"
                return get_json(path, **params)
            time.sleep(3 * (intento + 1))
    raise RuntimeError(f"No se pudo leer {url}")


def fecha_iso(s):
    """'14/11/2026' o '15-11-2026' -> '2026-11-14'"""
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def goles(resultado):
    m = re.match(r"\s*(\d+)\s*-\s*(\d+)\s*$", resultado or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def escudo(url):
    return ("https://ffcv.es" + url.split("?")[0]) if url else None


def main():
    print(f"Grupo {GRUPO} · competición {COMPETICION} · temporada {TEMPORADA}")
    jornadas = get_json("filtros/jornadas_fetch.php", cod_grupo=GRUPO)["jornadas"]

    equipos, partidos, filas_jornadas, actas = {}, [], [], []
    ultima_jugada = 1
    for jo in jornadas:
        n = int(jo["codjornada"])
        filas_jornadas.append({"cod_grupo": GRUPO, "jornada": n,
                               "fecha": fecha_iso(jo.get("fecha_jornada"))})
        data = get_json("partidos/resultados_por_grupo_jornada_data.php",
                        cod_temporada=TEMPORADA, cod_competicion=COMPETICION,
                        cod_grupo=GRUPO, cod_jornada=n)
        for p in data.get("partidos") or []:
            gl, gv = goles(p.get("resultado"))
            jugado = p.get("estado") == "1" and gl is not None
            if jugado:
                ultima_jugada = max(ultima_jugada, n)
            for lado in ("local", "visitante"):
                cod = p[f"cod_equipo_{lado}"]
                equipos[cod] = {"cod_equipo": cod, "nombre": p[lado],
                                "escudo_url": escudo(p.get(f"escudo_{lado}"))}
            if jugado and p.get("codacta"):
                actas.append((n, p["codacta"], p["cod_equipo_local"], p["cod_equipo_visitante"]))
            partidos.append({
                "cod_grupo": GRUPO, "jornada": n,
                "cod_local": p["cod_equipo_local"],
                "cod_visitante": p["cod_equipo_visitante"],
                "fecha": fecha_iso(p.get("fecha")), "hora": p.get("hora") or None,
                "campo": p.get("campo") or None,
                "goles_local": gl if jugado else None,
                "goles_visitante": gv if jugado else None,
                "jugado": jugado,
                "provisional": p.get("resultado_provisional") == "1",
                "cod_acta": p.get("codacta") or None,
                "motivo_estado": p.get("motivo_estado") or None,
                "actualizado": datetime.utcnow().isoformat() + "Z",
            })
        time.sleep(0.5)  # ser amable con el servidor

    clas = get_json("clasificaciones/clasificaciones_ajax.php",
                    cod_grupo=GRUPO, cod_jornada=ultima_jugada)
    filas_clas = []
    for t in clas.get("clasificacion") or []:
        equipos.setdefault(t["codequipo"], {"cod_equipo": t["codequipo"],
                                            "nombre": t["nombre"],
                                            "escudo_url": escudo(t.get("url_img"))})
        filas_clas.append({
            "cod_grupo": GRUPO, "cod_equipo": t["codequipo"],
            "jornada": ultima_jugada, "posicion": int(t["posicion"]),
            "pj": int(t["jugados"]), "g": int(t["ganados"]),
            "e": int(t["empatados"]), "p": int(t["perdidos"]),
            "gf": int(t["goles_a_favor"]), "gc": int(t["goles_en_contra"]),
            "puntos": int(t["puntos"]),
            "racha": "".join(r["tipo"] for r in t.get("racha_partidos") or []),
            "actualizado": datetime.utcnow().isoformat() + "Z",
        })

    filas_alin = []
    for n, acta, loc, vis in actas:
        seguidos = [e for e in (loc, vis) if e in EQUIPOS]
        if not seguidos:
            continue
        f = get_json("partidos/ficha_partido_ajax.php", cod_partido=acta)
        for eq in seguidos:
            lado = "local" if f.get("codigo_equipo_local") == eq else "visitante"
            entrenador = (f.get("entrenador_local") if lado == "local" else f.get("entrenador_visitante")) or ""
            for j in f.get(f"jugadores_equipo_{lado}") or []:
                filas_alin.append({
                    "cod_grupo": GRUPO, "cod_equipo": eq, "jornada": n, "cod_acta": acta,
                    "cod_jugador": j["codjugador"], "nombre": nombre_corto(j["nombre_jugador"]),
                    "dorsal": int(j["dorsal"]) if (j.get("dorsal") or "").isdigit() else None,
                    "posicion": j.get("posicion") or None,
                    "titular": j.get("titular") == "1", "capitan": j.get("capitan") == "1",
                    "portero": j.get("portero") == "1",
                    "esquema": f.get(f"esquema_{lado}") or None,
                    "entrenador": nombre_corto(entrenador) if entrenador.strip() else None,
                    "actualizado": datetime.utcnow().isoformat() + "Z",
                })
        time.sleep(0.5)

    print(f"{len(filas_alin)} filas de alineaciones de {len(EQUIPOS)} equipo(s)")
    print(f"{len(equipos)} equipos · {len(partidos)} partidos · "
          f"clasificación tras J{ultima_jugada} ({len(filas_clas)} filas)")

    for e in equipos.values():   # todas las filas con las mismas columnas (lo exige Supabase)
        e["escudo_data"] = descargar_imagen(e["escudo_url"]) if e.get("escudo_url") else None
        if e.get("escudo_url"):
            time.sleep(0.3)
    print(f"{sum(1 for e in equipos.values() if e.get('escudo_data'))} escudos descargados")

    if DRY_RUN:
        print(json.dumps({"clasificacion": filas_clas[:3], "partido": partidos[:1]},
                         ensure_ascii=False, indent=2))
        return

    upsert("equipos", list(equipos.values()), "cod_equipo")
    upsert("jornadas", filas_jornadas, "cod_grupo,jornada")
    upsert("partidos", partidos, "cod_grupo,jornada,cod_local,cod_visitante")
    upsert("clasificacion", filas_clas, "cod_grupo,cod_equipo")
    upsert("alineaciones", filas_alin, "cod_acta,cod_equipo,cod_jugador")
    print("Supabase actualizado ✔")


def upsert(tabla, filas, on_conflict):
    if not filas:
        return
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"]
    url = f"{base}/rest/v1/{tabla}?on_conflict={on_conflict}"
    req = urllib.request.Request(url, method="POST",
        data=json.dumps(filas).encode(),
        headers={"apikey": key,  # claves nuevas sb_secret_…: solo en apikey
                 "Content-Type": "application/json",
                 "Prefer": "resolution=merge-duplicates,return=minimal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"  {tabla}: {len(filas)} filas (HTTP {r.status})")


if __name__ == "__main__":
    main()

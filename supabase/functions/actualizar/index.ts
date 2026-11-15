// Supabase Edge Function: lanza el workflow "Actualizar datos FFCV" de GitHub.
// Necesita el secreto GITHUB_TOKEN (token fine-grained con permiso Actions: Read and write
// solo sobre el repositorio pmunyoz/alevin). Se despliega con "Verify JWT" desactivado.

const REPO = "pmunyoz/alevin";
const WORKFLOW = "actualizar.yml";
const ESPERA_MIN = 10; // no lanzar otra ejecución si la última empezó hace menos de 10 min

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "apikey, authorization, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json(405, { error: "Usa POST" });

  const token = Deno.env.get("GITHUB_TOKEN");
  if (!token) return json(500, { error: "Falta el secreto GITHUB_TOKEN" });

  const gh = (path: string, init: RequestInit = {}) =>
    fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "alevin-actualizar",
        ...(init.headers || {}),
      },
    });

  // ¿Hay una ejecución en marcha o muy reciente?
  const ult = await gh("/runs?per_page=1");
  if (ult.ok) {
    const run = (await ult.json()).workflow_runs?.[0];
    if (run) {
      const min = (Date.now() - new Date(run.created_at).getTime()) / 60000;
      if (run.status !== "completed") {
        return json(429, { error: "Ya hay una actualización en marcha", enMarcha: true });
      }
      if (min < ESPERA_MIN) {
        return json(429, { error: `Se actualizó hace ${Math.round(min)} min. Espera un poco.` });
      }
    }
  }

  const r = await gh("/dispatches", { method: "POST", body: JSON.stringify({ ref: "main" }) });
  if (r.status === 204) return json(200, { ok: true });
  return json(502, { error: `GitHub respondió ${r.status}`, detalle: await r.text() });
});

// Server-side Supabase REST helper for the Vercel functions. Uses the public anon key from the
// environment (read-only through row-level security). Nothing here is sent to the browser.
const URL = (process.env.SUPABASE_URL || "").replace(/\/$/, "");
const KEY = process.env.SUPABASE_ANON_KEY || "";

async function query(path) {
  if (!URL || !KEY) throw new Error("SUPABASE_URL / SUPABASE_ANON_KEY not configured");
  const headers = { apikey: KEY };
  if (!KEY.startsWith("sb_")) headers.Authorization = `Bearer ${KEY}`; // legacy JWT keys only
  const res = await fetch(`${URL}/rest/v1/${path}`, { headers });
  if (!res.ok) throw new Error(`Supabase ${res.status}: ${(await res.text()).slice(0, 200)}`);
  return res.json();
}

function send(res, status, body, cacheSeconds = 60) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", `s-maxage=${cacheSeconds}, stale-while-revalidate=600`);
  res.status(status).send(JSON.stringify(body));
}

module.exports = { query, send };

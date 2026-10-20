// GET /api/summary : overall metrics, baseline ranking, claims, memo decision and text, verifier and
// golden-set results, evidence packs and monthly complaint counts. All read from the database.
const { query, send } = require("./_supabase");

module.exports = async (req, res) => {
  try {
    const [metrics, issues, claims, evidence, monthly] = await Promise.all([
      query("metrics?select=key,value"),
      query("issues?select=*&order=rank.asc"),
      query("claims?select=*&order=claim_id.asc"),
      query("evidence?select=*&order=issue_id.asc,severity.desc"),
      query("monthly?select=*&order=month.asc&limit=1000"),
    ]);
    const m = Object.fromEntries(metrics.map((r) => [r.key, r.value]));
    send(res, 200, { source: "supabase", metrics: m, issues, claims, evidence, monthly });
  } catch (e) {
    send(res, 500, { error: String(e.message || e) }, 0);
  }
};

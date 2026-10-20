// GET /api/reviews?issue=ISS-PLAYBACK&limit=25&offset=0  -> member reviews of an issue, highest severity first
// GET /api/reviews?id=<review_id>                         -> one processed review record
const { query, send } = require("./_supabase");

const COLS = "review_id,status,reason,topic,intent,severity,sentiment,needs_review,evidence_quote,cache_source_id,issue_id,review_rating,review_timestamp";

module.exports = async (req, res) => {
  try {
    const { id, issue } = req.query || {};
    const limit = Math.min(parseInt(req.query.limit || "25", 10) || 25, 100);
    const offset = Math.max(parseInt(req.query.offset || "0", 10) || 0, 0);
    if (id) {
      const rows = await query(`reviews?select=${COLS}&review_id=eq.${encodeURIComponent(id)}`);
      return send(res, rows.length ? 200 : 404, rows[0] || { error: "not found" });
    }
    if (!issue || !/^ISS-[A-Z]+$/.test(issue)) return send(res, 400, { error: "issue=ISS-<TOPIC> or id=<review_id> required" }, 0);
    const rows = await query(
      `reviews?select=${COLS}&issue_id=eq.${issue}&order=severity.desc,review_id.asc&limit=${limit}&offset=${offset}`
    );
    send(res, 200, { issue, limit, offset, reviews: rows });
  } catch (e) {
    send(res, 500, { error: String(e.message || e) }, 0);
  }
};

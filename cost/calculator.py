"""100-review cost and runtime calculator (offline replay).

Default mode recomputes costs from saved usage and editable rates. It reads files only:
no API key, no network, no model calls. Importing this module makes no calls either.

    python3 -m cost.calculator replay  --usage cost/usage.csv --rates cost/rates.csv
    python3 -m cost.calculator project --usage cost/usage.csv --rates cost/rates.csv \
            --assumptions cost/assumptions.json

Arithmetic (per billing item):  item_cost = billed_units x price_per_unit
Rates are per million tokens in the file; they are divided by 1,000,000 before use.
Categories are mutually exclusive: uncached input, cached input, output.
Reasoning tokens are not added again when the provider already bills them as output.

Projections use measured per-unit usage, multiplied by full-run counts, plus fixed overhead
once. A projected cost above the budget is flagged, never silently capped.
"""

import csv
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

MILLION = Decimal(1_000_000)
TOKEN_ITEMS = ("uncached_input", "cached_input", "output")


def money(x):
    return Decimal(x).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def load_rates(path):
    """rates.csv columns: provider,model,item,price_per_million_tokens,currency,as_of,source_url,verified"""
    rates = {}
    with Path(path).open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["model"], row["item"])
            rates[key] = {"price": Decimal(row["price_per_million_tokens"]), "currency": row["currency"],
                          "as_of": row["as_of"], "source_url": row["source_url"],
                          "verified": row["verified"].strip().lower() == "true"}
    return rates


def load_usage(path):
    """usage.csv columns: stage,model,call_id,uncached_input_tokens,cached_input_tokens,output_tokens,outcome,seconds"""
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cost_by_stage(usage, rates):
    """Returns per-stage token totals, cost items, and totals. Missing rates are reported, not zeroed."""
    stages = {}
    unknown = []
    for row in usage:
        s = stages.setdefault(row["stage"], {"model": row["model"], "calls": 0, "failed": 0,
                                             "uncached_input": 0, "cached_input": 0, "output": 0, "seconds": 0.0})
        s["calls"] += 1
        if row["outcome"] != "succeeded":
            s["failed"] += 1
        for item in TOKEN_ITEMS:
            col = {"uncached_input": "uncached_input_tokens", "cached_input": "cached_input_tokens",
                   "output": "output_tokens"}[item]
            s[item] += int(row.get(col) or 0)
        s["seconds"] += float(row.get("seconds") or 0)

    total = Decimal(0)
    report = {}
    for name, s in stages.items():
        items = {}
        for item in TOKEN_ITEMS:
            rate = rates.get((s["model"], item))
            if rate is None and s[item] == 0:
                items[item] = None          # item not billed by this provider and no units used
                continue
            if rate is None:
                unknown.append(f"{name}:{item}")
                items[item] = None
                continue
            cost = money(Decimal(s[item]) / MILLION * rate["price"])
            items[item] = {"units": s[item], "price_per_million": str(rate["price"]),
                           "cost": str(cost), "currency": rate["currency"], "as_of": rate["as_of"],
                           "source_url": rate["source_url"], "verified": rate["verified"]}
            total += cost
        report[name] = {"model": s["model"], "calls": s["calls"], "failed_calls": s["failed"],
                        "seconds_summed": round(s["seconds"], 3), "items": items}
    return {"stages": report, "api_total": str(money(total)), "unknown_rates": unknown}


def replay(usage_path, rates_path):
    usage = load_usage(usage_path)
    rates = load_rates(rates_path)
    result = cost_by_stage(usage, rates)
    result["note"] = ("Offline replay. Summed call seconds are not wall-clock time when calls overlap. "
                      "Local compute is not included in api_total.")
    return result


def project(usage_path, rates_path, assumptions_path):
    """Scale measured per-call usage to full-run counts. Overhead is counted once."""
    usage = load_usage(usage_path)
    rates = load_rates(rates_path)
    a = json.loads(Path(assumptions_path).read_text(encoding="utf-8"))
    measured = cost_by_stage(usage, rates)
    measured_calls = {s: v["calls"] for s, v in measured["stages"].items()}
    scenarios = {}
    for name, sc in a["scenarios"].items():
        total = Decimal(0)
        per_stage = {}
        for stage, cost_info in measured["stages"].items():
            base_calls = measured_calls[stage] or 1
            full_calls = sc["full_run_units"][stage]
            factor = Decimal(full_calls) / Decimal(base_calls)
            stage_total = Decimal(0)
            for item in TOKEN_ITEMS:
                info = cost_info["items"].get(item)
                if info:
                    stage_total += Decimal(info["cost"]) * factor
            per_stage[stage] = str(money(stage_total))
            total += stage_total
        total += Decimal(str(sc.get("fixed_overhead_usd", 0)))
        budget = Decimal(str(a["budget_usd"]))
        scenarios[name] = {"api_total": str(money(total)), "per_stage": per_stage,
                           "budget_usd": str(budget), "over_budget": total > budget}
    return {"measured": measured, "scenarios": scenarios,
            "note": "Projections scale measured pilot usage. Estimates are not measured results."}


def main(argv):
    if len(argv) < 2 or argv[1] not in ("replay", "project"):
        print(__doc__)
        return 2
    args = dict(zip(argv[2::2], argv[3::2]))
    if argv[1] == "replay":
        out = replay(args["--usage"], args["--rates"])
    else:
        out = project(args["--usage"], args["--rates"], args["--assumptions"])
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

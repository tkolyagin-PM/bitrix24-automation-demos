"""Case 2 — sales KPI dashboard built from Bitrix24 deals.

Run: python dashboard.py  -> out/dashboard.html (self-contained page, open in any browser).
Put it on a schedule and publish the file (or push the numbers to Google Sheets / Looker Studio).
"""
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from b24 import OPEN_STAGES, SLA_DAYS, STAGE_NAMES, Client, parse_dt
from demo_data import TODAY

OUT = Path(__file__).parent / "out"


def kpis(deals, users, now, days=30):
    start = now - timedelta(days=days)
    amt = lambda d: float(d["OPPORTUNITY"])
    created = [d for d in deals if parse_dt(d["DATE_CREATE"]) >= start]
    closed = [d for d in deals if d["CLOSED"] == "Y" and parse_dt(d["MOVED_TIME"]) >= start]
    won = [d for d in closed if d["STAGE_ID"] == "WON"]
    open_deals = [d for d in deals if d["STAGE_ID"] in OPEN_STAGES]
    cycle = [(parse_dt(d["MOVED_TIME"]) - parse_dt(d["DATE_CREATE"])).days for d in won]

    def stuck(d):
        return (now - parse_dt(d["MOVED_TIME"])).total_seconds() / 86400 > SLA_DAYS[d["STAGE_ID"]]

    daily_new, daily_won = Counter(), Counter()
    for d in created:
        daily_new[parse_dt(d["DATE_CREATE"]).date()] += 1
    for d in won:
        daily_won[parse_dt(d["MOVED_TIME"]).date()] += amt(d)
    dates = [(start + timedelta(days=i + 1)).date() for i in range(days)]

    src = defaultdict(lambda: [0, 0])
    for d in closed:
        src[d["SOURCE_ID"]][d["STAGE_ID"] == "WON"] += 1

    managers = []
    for uid, name in users.items():
        mine_closed = [d for d in closed if d["ASSIGNED_BY_ID"] == uid]
        mine_won = [d for d in mine_closed if d["STAGE_ID"] == "WON"]
        mine_open = [d for d in open_deals if d["ASSIGNED_BY_ID"] == uid]
        managers.append({
            "name": name, "open": len(mine_open), "stuck": sum(map(stuck, mine_open)),
            "won": len(mine_won), "revenue": sum(map(amt, mine_won)),
            "winrate": round(100 * len(mine_won) / len(mine_closed)) if mine_closed else 0,
        })
    managers.sort(key=lambda m: -m["revenue"])

    return {
        "now": now.strftime("%d %b %Y, %H:%M"),
        "tiles": [
            ["New deals (30d)", f"{len(created)}", ""],
            ["Revenue won (30d)", f"${sum(map(amt, won)):,.0f}", f"{len(won)} deals"],
            ["Win rate", f"{round(100 * len(won) / max(len(closed), 1))}%", "won / closed"],
            ["Avg. sales cycle", f"{sum(cycle) / max(len(cycle), 1):.1f} d", "created → won"],
            ["Stuck past SLA", f"{sum(map(stuck, open_deals))}", f"of {len(open_deals)} open"],
        ],
        "dates": [d.strftime("%d %b") for d in dates],
        "daily_new": [daily_new.get(d, 0) for d in dates],
        "daily_won": [round(daily_won.get(d, 0)) for d in dates],
        "stages": [STAGE_NAMES[s] for s in OPEN_STAGES],
        "stage_count": [sum(d["STAGE_ID"] == s for d in open_deals) for s in OPEN_STAGES],
        "stage_stuck": [sum(d["STAGE_ID"] == s and stuck(d) for d in open_deals) for s in OPEN_STAGES],
        "sources": sorted(src, key=lambda s: -sum(src[s])),
        "src_won": [src[s][1] for s in sorted(src, key=lambda s: -sum(src[s]))],
        "src_lost": [src[s][0] for s in sorted(src, key=lambda s: -sum(src[s]))],
        "managers": managers,
    }


TEMPLATE = Path(__file__).parent / "templates" / "dashboard.html"


def main():
    client = Client()
    data = kpis(client.deals(), client.users(), TODAY if client.demo else datetime.now())
    OUT.mkdir(exist_ok=True)
    page = TEMPLATE.read_text().replace("/*DATA*/null", json.dumps(data))  # no external libraries
    (OUT / "dashboard.html").write_text(page)
    print("out/dashboard.html written")


if __name__ == "__main__":
    main()

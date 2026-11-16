"""Case 1 — daily morning report from Bitrix24 to Telegram.

Run:  python morning_report.py            # demo data, prints the message
      BITRIX_WEBHOOK=... TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=... python morning_report.py --send
Schedule it with cron / any scheduler, e.g. every weekday at 09:00.
"""
import html
import os
import sys
from collections import Counter, defaultdict
from datetime import timedelta

import requests

from b24 import OPEN_STAGES, SLA_DAYS, STAGE_NAMES, Client, parse_dt
from demo_data import TODAY


def money(x):
    return f"${x:,.0f}"


def build_report(deals, users, now):
    y_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0)
    y_end = y_start + timedelta(days=1)
    amount = lambda d: float(d["OPPORTUNITY"])
    yesterday = lambda d, f: y_start <= parse_dt(d[f]) < y_end

    created = [d for d in deals if yesterday(d, "DATE_CREATE")]
    won = [d for d in deals if d["STAGE_ID"] == "WON" and yesterday(d, "MOVED_TIME")]
    lost = [d for d in deals if d["STAGE_ID"] == "LOSE" and yesterday(d, "MOVED_TIME")]
    open_deals = [d for d in deals if d["STAGE_ID"] in OPEN_STAGES]

    stuck = []
    for d in open_deals:
        days = (now - parse_dt(d["MOVED_TIME"])).total_seconds() / 86400
        if days > SLA_DAYS[d["STAGE_ID"]]:
            stuck.append((days - SLA_DAYS[d["STAGE_ID"]], days, d))
    stuck.sort(key=lambda x: -x[0])
    overdue = [d for d in open_deals if parse_dt(d["CLOSEDATE"]).date() < now.date()]
    due_today = [d for d in open_deals if parse_dt(d["CLOSEDATE"]).date() == now.date()]

    e = html.escape
    lines = [f"<b>📊 Sales morning report — {now:%a, %d %b %Y}</b>", "",
             "<b>Yesterday</b>",
             f"🆕 New deals: <b>{len(created)}</b> ({money(sum(map(amount, created)))})",
             f"✅ Won: <b>{len(won)}</b> ({money(sum(map(amount, won)))})",
             f"❌ Lost: <b>{len(lost)}</b>", "",
             f"<b>Pipeline now: {len(open_deals)} deals, {money(sum(map(amount, open_deals)))}</b>"]
    by_stage = Counter(d["STAGE_ID"] for d in open_deals)
    lines += [f"• {STAGE_NAMES[s]}: {by_stage.get(s, 0)}" for s in OPEN_STAGES]

    lines += ["", f"<b>⚠️ Stuck past SLA: {len(stuck)}</b>"]
    for over, days, d in stuck[:5]:
        lines.append(f"• #{d['ID']} {e(d['TITLE'][:34])} — {STAGE_NAMES[d['STAGE_ID']]}, "
                     f"{days:.0f}d ({e(users[d['ASSIGNED_BY_ID']])})")
    if len(stuck) > 5:
        lines.append(f"  …and {len(stuck) - 5} more")

    lines += ["", f"<b>⏰ Deadlines:</b> {len(due_today)} today, {len(overdue)} overdue"]

    per_mgr = defaultdict(lambda: [0, 0, 0])
    for d in created:
        per_mgr[d["ASSIGNED_BY_ID"]][0] += 1
    for d in won:
        per_mgr[d["ASSIGNED_BY_ID"]][1] += 1
    for _, _, d in stuck:
        per_mgr[d["ASSIGNED_BY_ID"]][2] += 1
    lines += ["", "<b>👤 Managers</b> (new / won / stuck)"]
    for uid, name in sorted(users.items(), key=lambda u: -per_mgr[u[0]][2]):
        n, w, s = per_mgr[uid]
        flag = " 🔴" if s >= 8 else ""
        lines.append(f"• {e(name)}: {n} / {w} / {s}{flag}")
    return "\n".join(lines)


def send_telegram(text):
    token, chat = os.environ["TELEGRAM_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text, "parse_mode": "HTML"}, timeout=30)
    r.raise_for_status()


def main():
    client = Client()
    text = build_report(client.deals(), client.users(), TODAY if client.demo else __import__("datetime").datetime.now())
    if "--send" in sys.argv:
        send_telegram(text)
        print("Sent to Telegram")
    else:
        print(text)
    return text


if __name__ == "__main__":
    main()

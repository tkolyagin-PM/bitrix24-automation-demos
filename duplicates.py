"""Case 3 — duplicate lead detector for Bitrix24.

The same client often writes twice: once from the website form, once via a call-back
request, with the phone typed differently ("+1 555 0142" vs "8 (555) 014-2").
Bitrix24's built-in duplicate check misses many of these, two managers call the
same person, and the conversion report gets inflated.

Run: python duplicates.py          # prints the alert
     python duplicates.py --send   # sends it to Telegram (TELEGRAM_TOKEN / TELEGRAM_CHAT_ID)
"""
import html
import re
import sys
from difflib import SequenceMatcher

from b24 import Client, parse_dt
from morning_report import send_telegram


def phone_key(raw):
    """Normalize a phone to its last 7 digits — robust to +1 / 8 / spaces / dashes."""
    digits = re.sub(r"\D", "", raw or "")
    return digits[-7:] if len(digits) >= 7 else None


def same_person(a, b):
    """Names match if first names agree (one may lack the surname) or they are near-identical."""
    a, b = a.lower().strip(), b.lower().strip()
    return a.split()[0] == b.split()[0] or SequenceMatcher(None, a, b).ratio() > 0.8


def find_duplicates(leads):
    by_phone = {}
    for lead in leads:
        for ph in lead.get("PHONE") or []:
            key = phone_key(ph["VALUE"])
            if key:
                by_phone.setdefault(key, []).append((lead, ph["VALUE"]))
    groups = []
    for key, items in by_phone.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda x: parse_dt(x[0]["DATE_CREATE"]))
        first, *rest = items
        groups.append({
            "phone": key, "original": first,
            "dups": [(lead, raw, same_person(first[0]["NAME"], lead["NAME"])) for lead, raw in rest],
        })
    return sorted(groups, key=lambda g: g["original"][0]["DATE_CREATE"], reverse=True)


def build_alert(groups, users):
    e = html.escape
    lines = [f"<b>🔁 Possible duplicate leads: {len(groups)}</b>", ""]
    for g in groups:
        (orig, raw) = g["original"]
        lines.append(f"<b>{e(orig['NAME'])}</b> · {e(raw)}")
        lines.append(f"  #{orig['ID']} {e(orig['TITLE'])} → {e(users[orig['ASSIGNED_BY_ID']])}")
        for lead, raw2, same_name in g["dups"]:
            same_mgr = lead["ASSIGNED_BY_ID"] == orig["ASSIGNED_BY_ID"]
            lines.append(f"  #{lead['ID']} {e(lead['TITLE'])} · {e(raw2)} → {e(users[lead['ASSIGNED_BY_ID']])}"
                         f"{'' if same_mgr else ' ⚠️ other manager'}"
                         f"{'' if same_name else ' ❓ name differs — check'}")
        lines.append("")
    lines.append("Merge in Bitrix24 or close the newer lead with reason «Duplicate».")
    return "\n".join(lines)


def main():
    client = Client()
    text = build_alert(find_duplicates(client.leads()), client.users())
    if "--send" in sys.argv:
        send_telegram(text)
        print("Sent to Telegram")
    else:
        print(text)
    return text


if __name__ == "__main__":
    main()

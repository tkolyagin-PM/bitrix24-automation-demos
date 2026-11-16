"""Generate a fictional Bitrix24-like dataset (deals + leads) for the demo.

Everything here is made up: company, managers, clients and phone numbers
(+1 555-01xx numbers are reserved for fiction). The structure mirrors what
Bitrix24 REST returns from crm.deal.list / crm.lead.list, so the same report
code runs against a real portal by switching b24.Client to webhook mode.
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path(__file__).parent / "data"
TODAY = datetime(2026, 11, 16, 9, 0)  # report date: Monday morning

MANAGERS = {
    1: "Emily Carter",
    2: "Daniel Moore",
    3: "Sofia Rossi",
    4: "Liam Novak",
    5: "Ava Schmidt",
}
# Bitrix24 default deal pipeline
STAGES = ["NEW", "PREPARATION", "PREPAYMENT_INVOICE", "EXECUTING", "FINAL_INVOICE"]
SOURCES = {"WEB": 0.38, "CALL": 0.22, "ADVERTISING": 0.18, "RECOMMENDATION": 0.12, "EMAIL": 0.10}
PRODUCTS = ["Sofa set", "Kitchen cabinets", "Office chairs x12", "Wardrobe", "Dining table",
            "Bedroom set", "Bookshelves", "Reception desk", "Outdoor furniture", "Kids room set"]
FIRST = ["James", "Olivia", "Noah", "Mia", "Lucas", "Emma", "Ethan", "Chloe", "Mason", "Grace",
         "Henry", "Zoe", "Jack", "Lily", "Leo", "Ruby", "Max", "Ella", "Oscar", "Nora"]
LAST = ["Walker", "Bennett", "Hughes", "Price", "Foster", "Reed", "Barnes", "Cole", "Hayes", "Ward"]
# typical days spent in a stage before moving on
STAGE_DAYS = {"NEW": (0.1, 2), "PREPARATION": (0.5, 4), "PREPAYMENT_INVOICE": (1, 5),
              "EXECUTING": (1, 6), "FINAL_INVOICE": (0.5, 4)}
# chance to be lost while in this stage
LOSS = {"NEW": 0.08, "PREPARATION": 0.15, "PREPAYMENT_INVOICE": 0.15, "EXECUTING": 0.12, "FINAL_INVOICE": 0.05}


def fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+05:00")


def pick_weighted(rnd, weights):
    r, acc = rnd.random(), 0.0
    for key, w in weights.items():
        acc += w
        if r <= acc:
            return key
    return key


def make_deals(rnd, n=420):
    deals = []
    for i in range(n):
        created = TODAY - timedelta(days=rnd.uniform(0, 45), hours=rnd.uniform(0, 10))
        manager = rnd.choice(list(MANAGERS))
        slow = 1.8 if manager == 4 else 1.0  # one manager is noticeably slower
        t, stage, moved = created, "NEW", created
        for st in STAGES:
            stage, moved = st, t
            lo, hi = STAGE_DAYS[st]
            dur = timedelta(days=rnd.uniform(lo, hi) * slow)
            if rnd.random() < 0.07:  # some deals get forgotten
                dur *= rnd.uniform(3, 6)
            if t + dur > TODAY:
                break
            t += dur
            if rnd.random() < LOSS[st]:
                stage, moved = "LOSE", t
                break
        else:
            stage, moved = "WON", t
        amount = round(rnd.lognormvariate(7.6, 0.6), -1)
        deals.append({
            "ID": str(10000 + i),
            "TITLE": f"{rnd.choice(PRODUCTS)} — {rnd.choice(FIRST)} {rnd.choice(LAST)}",
            "STAGE_ID": stage,
            "ASSIGNED_BY_ID": str(manager),
            "OPPORTUNITY": f"{amount:.2f}",
            "CURRENCY_ID": "USD",
            "SOURCE_ID": pick_weighted(rnd, SOURCES),
            "DATE_CREATE": fmt(created),
            "MOVED_TIME": fmt(moved),
            "CLOSEDATE": fmt(created + timedelta(days=rnd.randint(7, 21))),
            "CLOSED": "Y" if stage in ("WON", "LOSE") else "N",
        })
    return deals


def make_leads(rnd, n=60):
    leads = []
    phones = [f"+1 555 01{x:02d}" for x in range(100)]
    rnd.shuffle(phones)
    for i in range(n):
        name = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
        created = TODAY - timedelta(days=rnd.uniform(0, 7))
        leads.append({"ID": str(500 + i), "NAME": name, "TITLE": f"Website request — {name}",
                      "PHONE": [{"VALUE": phones[i], "VALUE_TYPE": "WORK"}],
                      "ASSIGNED_BY_ID": str(rnd.choice(list(MANAGERS))),
                      "SOURCE_ID": pick_weighted(rnd, SOURCES), "DATE_CREATE": fmt(created)})
    # plant realistic duplicates: same person writes again with a differently formatted phone
    for j, src in enumerate(rnd.sample(leads, 6)):
        digits = "".join(c for c in src["PHONE"][0]["VALUE"] if c.isdigit())  # 155501xx
        local = digits[1:]
        variants = [f"({local[:3]}) {local[3:]}", f"+{digits}", f"{local[:3]}-{local[3:]}",
                    f"1 {local[:3]} {local[3:5]} {local[5:]}"]
        name = src["NAME"] if j % 2 else src["NAME"].split()[0]  # sometimes only first name
        created = datetime.fromisoformat(src["DATE_CREATE"][:19]) + timedelta(hours=rnd.uniform(2, 60))
        leads.append({"ID": str(600 + j), "NAME": name, "TITLE": f"Call back request — {name}",
                      "PHONE": [{"VALUE": rnd.choice(variants), "VALUE_TYPE": "MOBILE"}],
                      "ASSIGNED_BY_ID": str(rnd.choice(list(MANAGERS))),
                      "SOURCE_ID": rnd.choice(list(SOURCES)), "DATE_CREATE": fmt(min(created, TODAY))})
    return leads


def main():
    rnd = random.Random(42)
    DATA.mkdir(exist_ok=True)
    users = [{"ID": str(k), "NAME": v.split()[0], "LAST_NAME": v.split()[1]} for k, v in MANAGERS.items()]
    for name, rows in {"deals": make_deals(rnd), "leads": make_leads(rnd), "users": users}.items():
        (DATA / f"{name}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
        print(f"data/{name}.json: {len(rows)} rows")


if __name__ == "__main__":
    main()

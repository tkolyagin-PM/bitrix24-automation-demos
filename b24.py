"""Minimal Bitrix24 REST client: webhook mode for a real portal, demo mode for local JSON."""
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

DATA = Path(__file__).parent / "data"


class Client:
    def __init__(self, webhook=None):
        # e.g. https://yourcompany.bitrix24.com/rest/1/xxxxxxxx/
        self.webhook = (webhook or os.getenv("BITRIX_WEBHOOK", "")).rstrip("/")

    @property
    def demo(self):
        return not self.webhook

    def call(self, method, params=None):
        resp = requests.post(f"{self.webhook}/{method}.json", json=params or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def list_all(self, method, params=None):
        """Fetch every page of a *.list method (Bitrix24 returns 50 rows per page)."""
        params, rows, start = dict(params or {}), [], 0
        while start is not None:
            data = self.call(method, {**params, "start": start})
            rows += data.get("result", [])
            start = data.get("next")
            time.sleep(0.5)  # stay under the ~2 requests/second webhook limit
        return rows

    def _demo(self, name):
        return json.loads((DATA / f"{name}.json").read_text())

    def deals(self):
        if self.demo:
            return self._demo("deals")
        return self.list_all("crm.deal.list", {"select": [
            "ID", "TITLE", "STAGE_ID", "ASSIGNED_BY_ID", "OPPORTUNITY", "CURRENCY_ID",
            "SOURCE_ID", "DATE_CREATE", "MOVED_TIME", "CLOSEDATE", "CLOSED"]})

    def leads(self):
        if self.demo:
            return self._demo("leads")
        return self.list_all("crm.lead.list", {"select": ["ID", "NAME", "TITLE", "PHONE",
                                                          "ASSIGNED_BY_ID", "SOURCE_ID", "DATE_CREATE"]})

    def users(self):
        rows = self._demo("users") if self.demo else self.list_all("user.get")
        return {u["ID"]: f"{u['NAME']} {u['LAST_NAME']}".strip() for u in rows}


def parse_dt(value):
    return datetime.fromisoformat(value[:19])


STAGE_NAMES = {"NEW": "New", "PREPARATION": "Qualification", "PREPAYMENT_INVOICE": "Proposal",
               "EXECUTING": "Negotiation", "FINAL_INVOICE": "Contract", "WON": "Won", "LOSE": "Lost"}
OPEN_STAGES = ["NEW", "PREPARATION", "PREPAYMENT_INVOICE", "EXECUTING", "FINAL_INVOICE"]
# max days a deal may sit in a stage before it counts as stuck
SLA_DAYS = {"NEW": 1, "PREPARATION": 3, "PREPAYMENT_INVOICE": 4, "EXECUTING": 5, "FINAL_INVOICE": 3}

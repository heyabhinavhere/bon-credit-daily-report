"""
Amplitude API Client
Fetches and processes raw event data for the BON Credit daily report.
"""

import requests
import gzip
import json
import io
import os
from datetime import datetime
from collections import defaultdict


class AmplitudeClient:
    def __init__(self):
        self.api_key = os.environ["AMPLITUDE_API_KEY"]
        self.secret_key = os.environ["AMPLITUDE_SECRET_KEY"]
        self.base_url = "https://amplitude.com/api/2"

        # Configurable event names — set these in your .env to match your Amplitude taxonomy
        self.signup_event = os.environ.get("SIGNUP_EVENT", "Sign Up Complete")
        self.card_linked_event = os.environ.get("CARD_LINKED_EVENT", "Card Linked")
        self.bank_linked_event = os.environ.get("BANK_LINKED_EVENT", "Bank Account Linked")
        self.screen_event = os.environ.get("SCREEN_EVENT", "Screen View")
        self.screen_property = os.environ.get("SCREEN_PROPERTY", "screen_name")

    # -------------------------------------------------------------------------
    # Summary counts via Segmentation API (fast, low data transfer)
    # -------------------------------------------------------------------------

    def get_event_count(self, event_type: str, date: datetime) -> int:
        """Return unique user count for a given event on a specific date."""
        date_str = date.strftime("%Y%m%d")
        url = f"{self.base_url}/events/segmentation"
        params = {
            "e": json.dumps({"event_type": event_type}),
            "start": date_str,
            "end": date_str,
            "m": "uniques",
        }
        try:
            resp = requests.get(
                url, auth=(self.api_key, self.secret_key), params=params, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"]["series"][0][0]
        except Exception as e:
            print(f"[WARN] Could not fetch count for '{event_type}': {e}")
            return 0

    def get_dau(self, date: datetime) -> int:
        """Return daily active users (any active event) for a specific date."""
        return self.get_event_count("_active", date)

    # -------------------------------------------------------------------------
    # Full raw export for user-level breakdown
    # -------------------------------------------------------------------------

    def export_events(self, date: datetime) -> list:
        """
        Download all events for a date via the Amplitude Export API.
        Returns a list of event dicts.
        Note: Requires the Export API to be enabled on your Amplitude plan.
        """
        start = date.strftime("%Y%m%dT00")
        end = date.strftime("%Y%m%dT23")
        url = f"{self.base_url}/export"
        params = {"start": start, "end": end}

        print(f"[INFO] Exporting events for {date.strftime('%Y-%m-%d')}...")
        resp = requests.get(
            url,
            auth=(self.api_key, self.secret_key),
            params=params,
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()

        events = []
        # Response is one or more gzipped NDJSON chunks
        with gzip.GzipFile(fileobj=io.BytesIO(resp.content)) as gz:
            for line in gz:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        print(f"[INFO] Fetched {len(events):,} events.")
        return events

    # -------------------------------------------------------------------------
    # Data processing — builds the structured report payload
    # -------------------------------------------------------------------------

    def process_events(self, events: list) -> dict:
        """
        Process raw Amplitude events into a structured report dictionary.
        Returns summary stats + per-user breakdown for new signups.
        """
        # Per-user accumulator
        users = defaultdict(lambda: {
            "user_id": None,
            "signed_up": False,
            "card_linked": False,
            "bank_linked": False,
            "cards_count": 0,
            "banks_count": 0,
            "screens": [],
            "session_ids": set(),
            "session_windows": {},   # session_id -> {start, end}
            "event_count": 0,
        })

        for event in events:
            # Prefer user_id; fall back to device_id for anonymous sessions
            uid = event.get("user_id") or event.get("device_id", "anonymous")
            event_type = event.get("event_type", "")
            session_id = event.get("session_id")
            event_time = self._parse_time(event.get("event_time", ""))

            u = users[uid]
            u["user_id"] = uid
            u["event_count"] += 1

            # Session tracking for time-spent calculation
            if session_id and event_time:
                u["session_ids"].add(session_id)
                win = u["session_windows"]
                if session_id not in win:
                    win[session_id] = {"start": event_time, "end": event_time}
                else:
                    if event_time < win[session_id]["start"]:
                        win[session_id]["start"] = event_time
                    if event_time > win[session_id]["end"]:
                        win[session_id]["end"] = event_time

            # Screen tracking
            if event_type == self.screen_event:
                screen = (
                    event.get("event_properties", {}).get(self.screen_property)
                    or event.get("event_properties", {}).get("screen")
                    or ""
                )
                if screen and screen not in u["screens"]:
                    u["screens"].append(screen)

            # Key event flags
            if event_type == self.signup_event:
                u["signed_up"] = True
            elif event_type == self.card_linked_event:
                u["card_linked"] = True
                u["cards_count"] += 1
            elif event_type == self.bank_linked_event:
                u["bank_linked"] = True
                u["banks_count"] += 1

        # Build final report structures
        all_user_records = []
        new_signup_records = []

        for uid, u in users.items():
            time_spent_mins = self._calc_session_time(u["session_windows"])
            record = {
                "user_id": uid,
                "signed_up": u["signed_up"],
                "card_linked": u["card_linked"],
                "bank_linked": u["bank_linked"],
                "cards_count": u["cards_count"],
                "banks_count": u["banks_count"],
                "screens": u["screens"][:12],
                "time_spent_mins": time_spent_mins,
                "session_count": len(u["session_ids"]),
                "event_count": u["event_count"],
            }
            all_user_records.append(record)
            if u["signed_up"]:
                new_signup_records.append(record)

        total_active = len(all_user_records)
        card_linked_count = sum(1 for u in all_user_records if u["card_linked"])
        bank_linked_count = sum(1 for u in all_user_records if u["bank_linked"])
        avg_session_mins = (
            round(
                sum(u["time_spent_mins"] for u in all_user_records) / total_active, 1
            )
            if total_active > 0
            else 0
        )

        return {
            "total_active_users": total_active,
            "new_signup_count": len(new_signup_records),
            "card_linked_count": card_linked_count,
            "bank_linked_count": bank_linked_count,
            "avg_session_mins": avg_session_mins,
            "new_signups": new_signup_records,      # Full user-level breakdown
            "all_users": all_user_records,          # All active users
        }

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_time(time_str: str):
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _calc_session_time(session_windows: dict) -> float:
        """Total minutes across all sessions for a user."""
        total_seconds = sum(
            (w["end"] - w["start"]).total_seconds()
            for w in session_windows.values()
        )
        return round(total_seconds / 60, 1)

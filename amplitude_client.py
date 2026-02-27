"""
Amplitude API Client
Fetches and processes the full previous-day event export for the BON Credit daily report.
One export call → everything derived from it. No separate segmentation calls needed.
"""

import requests
import gzip
import zipfile
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

        # ── Core funnel ──────────────────────────────────────────────────────
        self.install_event        = os.environ.get("FRESH_INSTALL_EVENT",        "[Amplitude] Application Installed")
        self.signup_started       = os.environ.get("SIGNUP_STARTED_EVENT",       "sign_up_started_event")
        self.signup_completed     = os.environ.get("SIGNUP_EVENT",               "sign_up_completed_event")
        self.signup_failed        = os.environ.get("SIGNUP_FAILED_EVENT",        "sign_up_failed")
        self.onboarding_complete  = os.environ.get("ONBOARDING_COMPLETE_EVENT",  "onboarding_complete")
        self.onboarding_dropoff   = os.environ.get("ONBOARDING_DROPOFF_EVENT",   "onboarding_screen_drop_off")

        # ── Activation ───────────────────────────────────────────────────────
        self.card_initiate        = os.environ.get("CARD_INITIATE_EVENT",        "add_card_initiate")
        self.card_success         = os.environ.get("CARD_LINKED_EVENT",          "add_card_successful")
        self.card_failed          = os.environ.get("CARD_FAIL_EVENT",            "add_card_unsuccessful")
        self.bank_initiate        = os.environ.get("BANK_INITIATE_EVENT",        "add_bank_initiate")
        self.bank_success         = os.environ.get("BANK_LINKED_EVENT",          "add_bank_successful")
        self.bank_failed          = os.environ.get("BANK_FAIL_EVENT",            "add_bank_unsuccessful")
        self.autopay_setup        = os.environ.get("AUTOPAY_SETUP_EVENT",        "autopay_setup_successful")
        self.autopay_enabled      = os.environ.get("AUTOPAY_ENABLED_EVENT",      "autopay_enabled")
        self.income_added         = os.environ.get("INCOME_ADDED_EVENT",         "add_income_successful")

        # ── Payments ─────────────────────────────────────────────────────────
        self.bill_pay_initiated   = os.environ.get("BILL_PAY_INITIATED_EVENT",   "one_time_bill_payment_initiated")
        self.bill_pay_success     = os.environ.get("BILL_PAY_SUCCESS_EVENT",     "one_time_bill_payment_success")
        self.bill_pay_failed      = os.environ.get("BILL_PAY_FAILED_EVENT",      "one_time_bill_payment_failed")
        self.pay_bill_success     = os.environ.get("PAY_BILL_SUCCESS_EVENT",     "pay_bill_success")
        self.pay_bill_initiated   = os.environ.get("PAY_BILL_INITIATED_EVENT",   "pay_bill_initiated")
        self.payment_failed       = os.environ.get("PAYMENT_FAILED_EVENT",       "payment_failed")

        # ── Engagement ───────────────────────────────────────────────────────
        self.screen_event         = os.environ.get("SCREEN_EVENT",               "common_screen_view_tracker")
        self.screen_property      = os.environ.get("SCREEN_PROPERTY",            "screen_name")
        self.credgpt_started      = os.environ.get("CREDGPT_STARTED_EVENT",      "credgpt_chat_started")
        self.credgpt_ended        = os.environ.get("CREDGPT_ENDED_EVENT",        "credgpt_chat_ended")
        self.spinwheel_started    = os.environ.get("SPINWHEEL_STARTED_EVENT",    "spinwheel_started")
        self.spinwheel_completed  = os.environ.get("SPINWHEEL_COMPLETED_EVENT",  "spinwheel_completed")
        self.reward_initiated     = os.environ.get("REWARD_INITIATED_EVENT",     "slot_reward_redeem_initiated")
        self.reward_success       = os.environ.get("REWARD_SUCCESS_EVENT",       "slot_reward_redeem_successful")
        self.reward_failed        = os.environ.get("REWARD_FAILED_EVENT",        "slot_reward_redeem_failed")
        self.notif_click          = os.environ.get("NOTIF_CLICK_EVENT",          "notification_click")

        # ── Churn & Security ─────────────────────────────────────────────────
        self.churn_event          = os.environ.get("CHURN_EVENT",                "delete_membership")
        self.fraud_blocked        = os.environ.get("FRAUD_BLOCKED_EVENT",        "device_integrity_blocked")

        # ── Marketing ────────────────────────────────────────────────────────
        self.influencer_referral  = os.environ.get("INFLUENCER_REFERRAL_EVENT",  "influencer_referral")
        self.payer_verified       = os.environ.get("PAYER_VERIFIED_EVENT",       "payer_verified")
        self.select_debts         = os.environ.get("SELECT_DEBTS_EVENT",         "select_debts")
        self.extra_payment_set    = os.environ.get("EXTRA_PAYMENT_EVENT",        "extra_payment_set")

    # ─────────────────────────────────────────────────────────────────────────
    # Export
    # ─────────────────────────────────────────────────────────────────────────

    def export_events(self, date: datetime) -> list:
        """Download all events for a date via the Amplitude Export API."""
        start = date.strftime("%Y%m%dT00")
        end   = date.strftime("%Y%m%dT23")
        url   = f"{self.base_url}/export"
        params = {"start": start, "end": end}

        print(f"[INFO] Exporting events for {date.strftime('%Y-%m-%d')}...")

        last_err = None
        for attempt in range(1, 4):
            try:
                resp = requests.get(
                    url,
                    auth=(self.api_key, self.secret_key),
                    params=params,
                    stream=True,
                    timeout=420,  # 7 minutes — large exports can be slow
                )
                resp.raise_for_status()

                events = []
                content = resp.content

                # Amplitude returns a ZIP containing one or more gzipped NDJSON files
                if content[:2] == b'PK':
                    with zipfile.ZipFile(io.BytesIO(content)) as zf:
                        for name in zf.namelist():
                            with zf.open(name) as zipped_file:
                                raw = zipped_file.read()
                                # Each file inside the zip is gzip-compressed
                                try:
                                    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as gz:
                                        for line in gz:
                                            line = line.strip()
                                            if line:
                                                try:
                                                    events.append(json.loads(line))
                                                except json.JSONDecodeError:
                                                    continue
                                except gzip.BadGzipFile:
                                    # Some entries may be plain NDJSON
                                    for line in raw.splitlines():
                                        line = line.strip()
                                        if line:
                                            try:
                                                events.append(json.loads(line))
                                            except json.JSONDecodeError:
                                                continue
                else:
                    # Fallback: plain gzip
                    with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                        for line in gz:
                            line = line.strip()
                            if line:
                                try:
                                    events.append(json.loads(line))
                                except json.JSONDecodeError:
                                    continue

                print(f"[INFO] Fetched {len(events):,} raw events.")
                return events

            except Exception as e:
                last_err = e
                print(f"[WARN] Attempt {attempt}/3 failed: {e}. Retrying...")

        raise RuntimeError(f"Amplitude export failed after 3 attempts: {last_err}")

    # ─────────────────────────────────────────────────────────────────────────
    # Processing
    # ─────────────────────────────────────────────────────────────────────────

    def process_events(self, events: list) -> dict:
        """
        Single pass over all events → structured report payload.
        Every metric is derived here so the rest of the stack just reads dicts.
        """

        # ── Aggregate counters (unique users per action) ──────────────────
        buckets = {
            "installs":             set(),
            "signup_started":       set(),
            "signup_completed":     set(),
            "signup_failed":        set(),
            "onboarding_complete":  set(),
            "onboarding_dropoff":   set(),
            "card_initiated":       set(),
            "card_success":         set(),
            "card_failed":          set(),
            "bank_initiated":       set(),
            "bank_success":         set(),
            "bank_failed":          set(),
            "autopay_setup":        set(),
            "income_added":         set(),
            "bill_pay_initiated":   set(),
            "bill_pay_success":     set(),
            "bill_pay_failed":      set(),
            "credgpt_users":        set(),
            "spinwheel_users":      set(),
            "reward_success":       set(),
            "notif_clicks":         set(),
            "churned":              set(),
            "fraud_blocked":        set(),
            "influencer_referral":  set(),
            "payer_verified":       set(),
            "select_debts":         set(),
            "extra_payment_set":    set(),
            "all_active":           set(),
        }

        # Raw totals (not unique users — count occurrences)
        raw_counts = defaultdict(int)

        # ── Per-user data ─────────────────────────────────────────────────
        users = defaultdict(lambda: {
            "user_id":              None,
            "signup_started":       False,
            "signed_up":            False,
            "signup_failed":        False,
            "onboarding_complete":  False,
            "card_linked":          False,
            "card_failed":          False,
            "bank_linked":          False,
            "bank_failed":          False,
            "autopay_setup":        False,
            "income_added":         False,
            "churned":              False,
            "fraud_blocked":        False,
            "used_credgpt":         False,
            "used_spinwheel":       False,
            "redeemed_reward":      False,
            "cards_count":          0,
            "banks_count":          0,
            "bill_payments_made":   0,
            "screens":              [],
            "session_ids":          set(),
            "session_windows":      {},
            "event_count":          0,
        })

        for event in events:
            uid = event.get("user_id") or event.get("device_id", "anonymous")
            et  = event.get("event_type", "")
            sid = event.get("session_id")
            t   = self._parse_time(event.get("event_time", ""))

            u = users[uid]
            u["user_id"] = uid
            u["event_count"] += 1
            buckets["all_active"].add(uid)
            raw_counts[et] += 1

            # Session windows for time-spent
            if sid and t:
                u["session_ids"].add(sid)
                win = u["session_windows"]
                if sid not in win:
                    win[sid] = {"start": t, "end": t}
                else:
                    if t < win[sid]["start"]: win[sid]["start"] = t
                    if t > win[sid]["end"]:   win[sid]["end"]   = t

            # Screen tracking
            if et == self.screen_event:
                screen = (
                    event.get("event_properties", {}).get(self.screen_property)
                    or event.get("event_properties", {}).get("screen_name", "")
                )
                if screen and screen not in u["screens"]:
                    u["screens"].append(screen)

            # ── Funnel ──────────────────────────────────────
            if et == self.install_event:
                buckets["installs"].add(uid)
            elif et == self.signup_started:
                u["signup_started"] = True
                buckets["signup_started"].add(uid)
            elif et == self.signup_completed:
                u["signed_up"] = True
                buckets["signup_completed"].add(uid)
            elif et == self.signup_failed:
                u["signup_failed"] = True
                buckets["signup_failed"].add(uid)
            elif et == self.onboarding_complete:
                u["onboarding_complete"] = True
                buckets["onboarding_complete"].add(uid)
            elif et == self.onboarding_dropoff:
                buckets["onboarding_dropoff"].add(uid)

            # ── Activation ──────────────────────────────────
            elif et == self.card_initiate:
                buckets["card_initiated"].add(uid)
            elif et == self.card_success:
                u["card_linked"] = True
                u["cards_count"] += 1
                buckets["card_success"].add(uid)
            elif et == self.card_failed:
                u["card_failed"] = True
                buckets["card_failed"].add(uid)
            elif et == self.bank_initiate:
                buckets["bank_initiated"].add(uid)
            elif et == self.bank_success:
                u["bank_linked"] = True
                u["banks_count"] += 1
                buckets["bank_success"].add(uid)
            elif et == self.bank_failed:
                u["bank_failed"] = True
                buckets["bank_failed"].add(uid)
            elif et in (self.autopay_setup, self.autopay_enabled):
                u["autopay_setup"] = True
                buckets["autopay_setup"].add(uid)
            elif et == self.income_added:
                u["income_added"] = True
                buckets["income_added"].add(uid)

            # ── Payments ────────────────────────────────────
            elif et in (self.bill_pay_initiated, self.pay_bill_initiated):
                buckets["bill_pay_initiated"].add(uid)
            elif et in (self.bill_pay_success, self.pay_bill_success):
                u["bill_payments_made"] += 1
                buckets["bill_pay_success"].add(uid)
            elif et in (self.bill_pay_failed, self.payment_failed):
                buckets["bill_pay_failed"].add(uid)

            # ── Engagement ──────────────────────────────────
            elif et in (self.credgpt_started, self.credgpt_ended):
                u["used_credgpt"] = True
                buckets["credgpt_users"].add(uid)
            elif et in (self.spinwheel_started, self.spinwheel_completed):
                u["used_spinwheel"] = True
                buckets["spinwheel_users"].add(uid)
            elif et == self.reward_success:
                u["redeemed_reward"] = True
                buckets["reward_success"].add(uid)
            elif et == self.notif_click:
                buckets["notif_clicks"].add(uid)

            # ── Churn & Security ────────────────────────────
            elif et == self.churn_event:
                u["churned"] = True
                buckets["churned"].add(uid)
            elif et == self.fraud_blocked:
                u["fraud_blocked"] = True
                buckets["fraud_blocked"].add(uid)

            # ── Marketing ───────────────────────────────────
            elif et == self.influencer_referral:
                buckets["influencer_referral"].add(uid)
            elif et == self.payer_verified:
                buckets["payer_verified"].add(uid)
            elif et == self.select_debts:
                buckets["select_debts"].add(uid)
            elif et == self.extra_payment_set:
                buckets["extra_payment_set"].add(uid)

        # ── Convert sets → counts ──────────────────────────────────────────
        def c(key): return len(buckets[key])

        def pct(num, den):
            """Safe percentage string, e.g. '73%'."""
            return f"{round(num / den * 100)}%" if den > 0 else "—"

        dau = c("all_active")
        avg_session = self._avg_session(users, dau)

        # ── Per-user records for new signups ───────────────────────────────
        new_signups = []
        for uid, u in users.items():
            if u["signed_up"]:
                new_signups.append({
                    "user_id":             uid,
                    "card_linked":         u["card_linked"],
                    "card_failed":         u["card_failed"],
                    "bank_linked":         u["bank_linked"],
                    "bank_failed":         u["bank_failed"],
                    "onboarding_complete": u["onboarding_complete"],
                    "autopay_setup":       u["autopay_setup"],
                    "used_credgpt":        u["used_credgpt"],
                    "cards_count":         u["cards_count"],
                    "banks_count":         u["banks_count"],
                    "bill_payments_made":  u["bill_payments_made"],
                    "screens":             u["screens"][:15],
                    "time_spent_mins":     self._calc_session_time(u["session_windows"]),
                    "session_count":       len(u["session_ids"]),
                    "event_count":         u["event_count"],
                })

        return {
            # ── Growth funnel ──────────────────────────────────────────────
            "installs":                     c("installs"),
            "signup_started":               c("signup_started"),
            "signup_completed":             c("signup_completed"),
            "signup_failed":                c("signup_failed"),
            "onboarding_complete":          c("onboarding_complete"),
            "onboarding_dropoff":           c("onboarding_dropoff"),
            "install_to_signup_rate":       pct(c("signup_completed"), c("installs")),
            "started_to_completed_rate":    pct(c("signup_completed"), c("signup_started")),
            "signup_to_onboarding_rate":    pct(c("onboarding_complete"), c("signup_completed")),

            # ── Activation ─────────────────────────────────────────────────
            "card_initiated":               c("card_initiated"),
            "card_success":                 c("card_success"),
            "card_failed":                  c("card_failed"),
            "card_success_rate":            pct(c("card_success"), c("card_initiated")),
            "bank_initiated":               c("bank_initiated"),
            "bank_success":                 c("bank_success"),
            "bank_failed":                  c("bank_failed"),
            "bank_success_rate":            pct(c("bank_success"), c("bank_initiated")),
            "autopay_setups":               c("autopay_setup"),
            "income_added":                 c("income_added"),
            "payer_verified":               c("payer_verified"),
            "select_debts":                 c("select_debts"),
            "extra_payment_set":            c("extra_payment_set"),

            # ── Payments ───────────────────────────────────────────────────
            "bill_pay_initiated":           c("bill_pay_initiated"),
            "bill_pay_success":             c("bill_pay_success"),
            "bill_pay_failed":              c("bill_pay_failed"),
            "bill_pay_success_rate":        pct(c("bill_pay_success"), c("bill_pay_initiated")),

            # ── Engagement ─────────────────────────────────────────────────
            "dau":                          dau,
            "avg_session_mins":             avg_session,
            "credgpt_users":                c("credgpt_users"),
            "spinwheel_users":              c("spinwheel_users"),
            "reward_redeemed":              c("reward_success"),
            "notif_clicks":                 c("notif_clicks"),

            # ── Churn & Security ───────────────────────────────────────────
            "churned":                      c("churned"),
            "fraud_blocked":                c("fraud_blocked"),

            # ── Marketing ──────────────────────────────────────────────────
            "influencer_referrals":         c("influencer_referral"),

            # ── User-level ─────────────────────────────────────────────────
            "new_signups":                  new_signups,
            "new_signup_count":             c("signup_completed"),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

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
        total = sum(
            (w["end"] - w["start"]).total_seconds()
            for w in session_windows.values()
        )
        return round(total / 60, 1)

    @staticmethod
    def _avg_session(users: dict, dau: int) -> float:
        if dau == 0:
            return 0.0
        total_mins = sum(
            AmplitudeClient._calc_session_time(u["session_windows"])
            for u in users.values()
        )
        return round(total_mins / dau, 1)

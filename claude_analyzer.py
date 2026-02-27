"""
Claude Analyzer
Sends the full structured report data to Claude and returns a narrative analysis.
"""

import os
import json
import anthropic
from datetime import datetime


def analyze_with_claude(d: dict, report_date: datetime) -> dict:
    """
    d: the full dict returned by AmplitudeClient.process_events()
    Returns: {executive_summary, highlights, watch_list, full_text}
    """
    client   = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    date_str = report_date.strftime("%A, %B %d, %Y")

    # Slim down the user table for Claude — cap at 50 to stay within tokens
    signups_preview = d["new_signups"][:50]
    full_activation = sum(
        1 for u in d["new_signups"]
        if u["card_linked"] and u["bank_linked"]
    )
    partial_activation = sum(
        1 for u in d["new_signups"]
        if (u["card_linked"] or u["bank_linked"]) and not (u["card_linked"] and u["bank_linked"])
    )
    zero_activation = sum(
        1 for u in d["new_signups"]
        if not u["card_linked"] and not u["bank_linked"]
    )

    data_for_claude = {
        "date": date_str,
        "growth_funnel": {
            "app_installs":                d["installs"],
            "signup_started":              d["signup_started"],
            "signup_completed":            d["new_signup_count"],
            "signup_failed":               d["signup_failed"],
            "onboarding_complete":         d["onboarding_complete"],
            "onboarding_dropoff":          d["onboarding_dropoff"],
            "install_to_signup_rate":      d["install_to_signup_rate"],
            "started_to_completed_rate":   d["started_to_completed_rate"],
            "signup_to_onboarding_rate":   d["signup_to_onboarding_rate"],
        },
        "activation": {
            "card_attempts":    d["card_initiated"],
            "card_success":     d["card_success"],
            "card_failed":      d["card_failed"],
            "card_success_rate": d["card_success_rate"],
            "bank_attempts":    d["bank_initiated"],
            "bank_success":     d["bank_success"],
            "bank_failed":      d["bank_failed"],
            "bank_success_rate": d["bank_success_rate"],
            "autopay_setups":   d["autopay_setups"],
            "income_added":     d["income_added"],
        },
        "payments": {
            "initiated":        d["bill_pay_initiated"],
            "success":          d["bill_pay_success"],
            "failed":           d["bill_pay_failed"],
            "success_rate":     d["bill_pay_success_rate"],
            "extra_payment_set": d["extra_payment_set"],
        },
        "engagement": {
            "dau":              d["dau"],
            "avg_session_mins": d["avg_session_mins"],
            "credgpt_users":    d["credgpt_users"],
            "spinwheel_users":  d["spinwheel_users"],
            "rewards_redeemed": d["reward_redeemed"],
            "notif_clicks":     d["notif_clicks"],
        },
        "retention_risk": {
            "churned_users":    d["churned"],
            "fraud_blocked":    d["fraud_blocked"],
        },
        "marketing": {
            "influencer_referrals": d["influencer_referrals"],
        },
        "new_signup_cohort_summary": {
            "total":                  d["new_signup_count"],
            "full_activation":        full_activation,
            "partial_activation":     partial_activation,
            "zero_activation":        zero_activation,
            "used_credgpt":           sum(1 for u in d["new_signups"] if u["used_credgpt"]),
            "autopay_enabled":        sum(1 for u in d["new_signups"] if u["autopay_setup"]),
            "avg_time_spent_mins":    round(
                sum(u["time_spent_mins"] for u in d["new_signups"]) / len(d["new_signups"]), 1
            ) if d["new_signups"] else 0,
            "card_failed_only":       sum(
                1 for u in d["new_signups"] if u["card_failed"] and not u["card_linked"]
            ),
        },
        "new_signup_sample": [
            {
                "user_id":            u["user_id"],
                "full_activation":    u["card_linked"] and u["bank_linked"],
                "card_linked":        u["card_linked"],
                "bank_linked":        u["bank_linked"],
                "autopay":            u["autopay_setup"],
                "credgpt":            u["used_credgpt"],
                "time_mins":          u["time_spent_mins"],
                "screens":            u["screens"][:6],
                "payments":           u["bill_payments_made"],
            }
            for u in signups_preview
        ],
    }

    prompt = f"""You are a sharp product analyst writing a daily brief for the two founders of BON Credit — a consumer fintech app that helps users manage and pay credit card debt.

Today is {date_str}. Here's yesterday's complete data:

{json.dumps(data_for_claude, indent=2)}

Write three sections:

---
EXECUTIVE SUMMARY
2-3 paragraphs. Lead with the most important thing that happened. Cover the growth funnel, activation health, and anything that needs founder attention today. Be direct. Use specific numbers. End with one forward-looking sentence about what to watch.

---
KEY HIGHLIGHTS
5-7 bullet points, each a concrete observation. Include: funnel conversion analysis, activation patterns in the new signup cohort, payment behaviour, engagement bright spots, and any positive signals worth noting. Each bullet = 1-2 sentences max.

---
WATCH LIST
3-4 items that need attention today. Include: drop-offs, failures, churn, fraud, anything where rates are poor or counts are surprising. For each, say what it is and what action to take. Be specific — not "monitor this", but "check X because Y".

---
Rules:
- Use actual numbers from the data, not vague language.
- Don't soften bad news. If something is bad, say it's bad.
- Never say "it's important to note", "it's worth mentioning", "leveraging", or "delve".
- Write in second person ("you had", "your funnel").
- If churned > 0, that goes first or second in the Watch List.
- If fraud_blocked > 0, call it out explicitly.
"""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text
    sections = _parse_sections(raw_text)

    return {
        "executive_summary": sections.get("EXECUTIVE SUMMARY", raw_text),
        "highlights":        sections.get("KEY HIGHLIGHTS", ""),
        "watch_list":        sections.get("WATCH LIST", ""),
        "full_text":         raw_text,
    }


def _parse_sections(text: str) -> dict:
    sections      = {}
    current       = None
    current_lines = []
    known         = {"EXECUTIVE SUMMARY", "KEY HIGHLIGHTS", "WATCH LIST"}

    for line in text.split("\n"):
        stripped = line.strip().lstrip("*# ").rstrip("*# ").strip()
        if stripped in known:
            if current:
                sections[current] = "\n".join(current_lines).strip()
            current       = stripped
            current_lines = []
        elif line.strip() == "---":
            continue
        else:
            current_lines.append(line)

    if current:
        sections[current] = "\n".join(current_lines).strip()

    return sections

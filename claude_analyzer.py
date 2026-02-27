"""
Analyzed by LLM
Uses the Anthropic API to generate an executive narrative from raw report data.
"""

import os
import json
import anthropic
from datetime import datetime


def analyze_with_claude(report_data: dict, report_date: datetime) -> dict:
    """
    Sends structured Amplitude data to Claude and returns a rich narrative analysis.
    Returns a dict with 'executive_summary', 'highlights', and 'watch_list'.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    date_str = report_date.strftime("%A, %B %d, %Y")

    # Trim user list to avoid hitting token limits — top 50 is enough for context
    signups_for_claude = report_data["new_signups"][:50]

    # Build a compact representation of the data
    data_summary = {
        "date": date_str,
        "summary_metrics": {
            "daily_active_users": report_data["total_active_users"],
            "new_signups": report_data["new_signup_count"],
            "users_who_linked_card": report_data["card_linked_count"],
            "users_who_linked_bank": report_data["bank_linked_count"],
            "avg_session_duration_mins": report_data["avg_session_mins"],
        },
        "new_signup_details": [
            {
                "user_id": u["user_id"],
                "card_linked": u["card_linked"],
                "bank_linked": u["bank_linked"],
                "cards_count": u["cards_count"],
                "banks_count": u["banks_count"],
                "screens_visited": u["screens"],
                "time_spent_mins": u["time_spent_mins"],
                "sessions": u["session_count"],
            }
            for u in signups_for_claude
        ],
    }

    prompt = f"""You are a senior product analyst at BON Credit, a consumer fintech company.
You are writing a daily report email for the founders. Your tone should be clear, direct, and data-driven — like a smart colleague briefing them before their morning coffee.

Here is yesterday's data ({date_str}):

{json.dumps(data_summary, indent=2)}

Write three sections:

---

**EXECUTIVE SUMMARY**
2-3 paragraphs. Cover what happened yesterday at a high level. Highlight what was good, what was concerning, and one key question the data raises. Be specific with numbers.

---

**KEY HIGHLIGHTS**
3-5 bullet points. Each one should be a concrete, actionable observation from the data. For example: which users completed the full onboarding funnel (signup + card + bank), any drop-off patterns you see, average engagement depth, etc.

---

**WATCH LIST**
2-3 items that need attention or follow-up. These are things that could become problems or opportunities. Be brief and specific.

---

Rules:
- Use actual numbers from the data, not vague language.
- Don't pad. If something isn't notable, skip it.
- Never say "it's important to note" or "it's worth mentioning".
- Write in second person ("you had X signups") not third person.
"""

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text

    # Parse sections from the response
    sections = _parse_sections(raw_text)

    return {
        "executive_summary": sections.get("EXECUTIVE SUMMARY", raw_text),
        "highlights": sections.get("KEY HIGHLIGHTS", ""),
        "watch_list": sections.get("WATCH LIST", ""),
        "full_text": raw_text,
    }


def _parse_sections(text: str) -> dict:
    """Split the Claude response into named sections."""
    sections = {}
    current_section = None
    current_lines = []

    for line in text.split("\n"):
        stripped = line.strip().lstrip("*# ").rstrip("*# ")

        if stripped in ("EXECUTIVE SUMMARY", "KEY HIGHLIGHTS", "WATCH LIST"):
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = stripped
            current_lines = []
        elif line.strip() == "---":
            continue
        else:
            current_lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections

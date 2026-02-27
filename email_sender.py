"""
Email Sender
Builds a comprehensive founder-grade HTML brief and sends via SendGrid.
"""

import os
import markdown
import sendgrid
from sendgrid.helpers.mail import Mail, To
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# Colour palette
# ─────────────────────────────────────────────────────────────────────────────
GREEN  = "#10b981"
RED    = "#ef4444"
AMBER  = "#f59e0b"
BLUE   = "#3b82f6"
INDIGO = "#6366f1"
SLATE  = "#64748b"


def _pct_color(pct_str: str, good_above: int = 50) -> str:
    if pct_str == "—":
        return SLATE
    try:
        val = int(pct_str.replace("%", ""))
        if val >= good_above:   return GREEN
        elif val >= good_above // 2: return AMBER
        else:                   return RED
    except ValueError:
        return SLATE


# ─────────────────────────────────────────────────────────────────────────────
# Daily summary — human-readable paragraph, generated from data (no Claude)
# ─────────────────────────────────────────────────────────────────────────────

def _build_daily_summary(d: dict) -> str:
    """
    Auto-generated plain-English snapshot. Readable in under 30 seconds.
    Shows up right under the header so founders get the gist before anything else.
    """
    signups   = d["new_signup_count"]
    installs  = d["installs"]
    dau       = d["dau"]
    avg_sess  = d["avg_session_mins"]

    # Full activation = card + bank linked
    full_activation = sum(
        1 for u in d["new_signups"]
        if u["card_linked"] and u["bank_linked"]
    )

    # Sentences
    parts = []

    # Growth
    if installs > 0:
        parts.append(
            f"You had <strong>{signups:,} new signup{'s' if signups != 1 else ''}</strong> "
            f"from {installs:,} app install{'s' if installs != 1 else ''} "
            f"({d['install_to_signup_rate']} install-to-signup rate)."
        )
    else:
        parts.append(f"You had <strong>{signups:,} new signup{'s' if signups != 1 else ''}</strong> yesterday.")

    # Activation
    if signups > 0:
        card_pct = round(d["card_success"] / signups * 100) if signups else 0
        bank_pct = round(d["bank_success"] / signups * 100) if signups else 0
        parts.append(
            f"Of those, <strong>{d['card_success']} linked a card</strong> ({card_pct}%) "
            f"and <strong>{d['bank_success']} linked a bank</strong> ({bank_pct}%) — "
            f"<strong>{full_activation} fully activated</strong> (card + bank)."
        )

    # DAU & session
    parts.append(
        f"<strong>{dau:,} users</strong> were active in total, "
        f"averaging <strong>{avg_sess} min</strong> per session."
    )

    # Payments
    if d["bill_pay_initiated"] > 0:
        parts.append(
            f"Bill payments: <strong>{d['bill_pay_success']:,} succeeded</strong> "
            f"out of {d['bill_pay_initiated']:,} initiated ({d['bill_pay_success_rate']} rate)."
        )

    # Engagement bright spots
    eng_bits = []
    if d["credgpt_users"] > 0:
        eng_bits.append(f"CredGPT used by {d['credgpt_users']:,}")
    if d["spinwheel_users"] > 0:
        eng_bits.append(f"spinwheel played by {d['spinwheel_users']:,}")
    if d["autopay_setups"] > 0:
        eng_bits.append(f"{d['autopay_setups']:,} autopay setup{'s' if d['autopay_setups'] != 1 else ''}")
    if eng_bits:
        parts.append(", ".join(eng_bits).capitalize() + ".")

    # Churn
    if d["churned"] > 0:
        parts.append(
            f"⚠️ <strong style='color:#ef4444;'>{d['churned']} user{'s' if d['churned'] > 1 else ''} "
            f"deleted their membership.</strong>"
        )
    else:
        parts.append("No churn.")

    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Component helpers
# ─────────────────────────────────────────────────────────────────────────────

def _section_header(title: str, emoji: str = "") -> str:
    return f"""
    <div style="margin:32px 0 12px 0;">
      <span style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                   color:#94a3b8;">{emoji}&nbsp; {title}</span>
      <div style="border-top:1px solid #1e293b;margin-top:8px;"></div>
    </div>
    """


def _big_metric(label: str, value, sub: str = "", color: str = SLATE, emoji: str = "") -> str:
    return f"""
    <div style="background:#0f172a;border-radius:12px;padding:20px 18px;border:1px solid #1e293b;min-width:120px;flex:1;">
      <div style="font-size:20px;margin-bottom:4px;">{emoji}</div>
      <div style="font-size:26px;font-weight:800;color:{color};line-height:1.1;">{value}</div>
      <div style="font-size:12px;color:#94a3b8;margin-top:5px;font-weight:500;">{label}</div>
      {f'<div style="font-size:11px;color:#475569;margin-top:3px;">{sub}</div>' if sub else ''}
    </div>
    """


def _funnel_step(label: str, value: int, rate: str = "", is_last: bool = False) -> str:
    arrow = "" if is_last else '<div style="color:#334155;font-size:20px;padding:0 8px;align-self:center;">→</div>'
    return f"""
    <div style="display:flex;align-items:center;">
      <div style="background:#0f172a;border-radius:10px;padding:14px 18px;border:1px solid #1e293b;text-align:center;min-width:90px;">
        <div style="font-size:22px;font-weight:800;color:#f1f5f9;">{value:,}</div>
        <div style="font-size:11px;color:#64748b;margin-top:3px;">{label}</div>
        {f'<div style="font-size:11px;color:{_pct_color(rate)};font-weight:700;margin-top:4px;">{rate}</div>' if rate else ''}
      </div>
      {arrow}
    </div>
    """


def _rate_bar(label: str, success: int, failed: int, rate: str) -> str:
    color = _pct_color(rate, good_above=70)
    return f"""
    <div style="margin-bottom:14px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
        <span style="font-size:13px;color:#cbd5e1;">{label}</span>
        <span style="font-size:13px;font-weight:700;color:{color};">{rate}</span>
      </div>
      <div style="flex:1;display:flex;justify-content:space-between;background:#1e293b;border-radius:6px;padding:6px 10px;">
        <span style="font-size:12px;color:#10b981;">✓ {success:,} success</span>
        <span style="font-size:12px;color:#ef4444;">✗ {failed:,} failed</span>
      </div>
    </div>
    """


def _card(content: str, bg: str = "#0f172a", border: str = "#1e293b") -> str:
    return f'<div style="background:{bg};border-radius:12px;padding:22px 24px;border:1px solid {border};">{content}</div>'


# ─────────────────────────────────────────────────────────────────────────────
# New signups table
# ─────────────────────────────────────────────────────────────────────────────

def _build_signups_table(new_signups: list) -> str:
    if not new_signups:
        return '<p style="color:#475569;font-size:14px;padding:16px 0;">No new signups yesterday.</p>'

    rows = ""
    for u in new_signups:
        def badge(val: bool, yes_text: str = "✓", no_text: str = "✗"):
            if val:
                return f'<span style="background:#052e16;color:#4ade80;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:600;">{yes_text}</span>'
            return f'<span style="background:#1c1917;color:#ef4444;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:600;">{no_text}</span>'

        screens = " → ".join(u["screens"][:6]) if u["screens"] else "—"
        rows += f"""
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:9px 10px;font-size:12px;font-family:monospace;color:#94a3b8;white-space:nowrap;">{str(u['user_id'])[:24]}</td>
          <td style="padding:9px 10px;text-align:center;">{badge(u['onboarding_complete'], "Done", "Incomplete")}</td>
          <td style="padding:9px 10px;text-align:center;">{badge(u['card_linked'], "Linked", "None")}</td>
          <td style="padding:9px 10px;text-align:center;">{badge(u['bank_linked'], "Linked", "None")}</td>
          <td style="padding:9px 10px;text-align:center;color:#64748b;font-size:12px;">{u['cards_count']}/{u['banks_count']}</td>
          <td style="padding:9px 10px;text-align:center;">{badge(u['autopay_setup'], "On", "Off")}</td>
          <td style="padding:9px 10px;text-align:center;">{badge(u['used_credgpt'], "Yes", "No")}</td>
          <td style="padding:9px 10px;font-size:11px;color:#64748b;max-width:200px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;">{screens}</td>
          <td style="padding:9px 10px;text-align:center;color:#64748b;font-size:12px;white-space:nowrap;">{u['time_spent_mins']}m / {u['session_count']}s</td>
          <td style="padding:9px 10px;text-align:center;color:#64748b;font-size:12px;">{u['bill_payments_made']}</td>
        </tr>
        """

    return f"""
    <div style="overflow-x:auto;">
      <table style="width:100%;border-collapse:collapse;min-width:900px;">
        <thead>
          <tr style="background:#0f172a;border-bottom:2px solid #1e293b;">
            <th style="padding:9px 10px;text-align:left;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">User ID</th>
            <th style="padding:9px 10px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">Onboarding</th>
            <th style="padding:9px 10px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">Card</th>
            <th style="padding:9px 10px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">Bank</th>
            <th style="padding:9px 10px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">Cards/Banks</th>
            <th style="padding:9px 10px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">Autopay</th>
            <th style="padding:9px 10px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">CredGPT</th>
            <th style="padding:9px 10px;text-align:left;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">Screens Visited</th>
            <th style="padding:9px 10px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">Time / Sessions</th>
            <th style="padding:9px 10px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.06em;">Payments</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """


# ─────────────────────────────────────────────────────────────────────────────
# Main HTML builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_html(report_date: datetime, d: dict, analysis: dict) -> str:
    date_str = report_date.strftime("%A, %B %d, %Y")

    exec_html       = markdown.markdown(analysis.get("executive_summary", ""))
    highlights_html = markdown.markdown(analysis.get("highlights", ""))
    watchlist_html  = markdown.markdown(analysis.get("watch_list", ""))
    daily_summary   = _build_daily_summary(d)
    signups_table   = _build_signups_table(d["new_signups"])

    # ── Churn alert ─────────────────────────────────────────────────────────
    churn_banner = ""
    if d["churned"] > 0:
        churn_banner = f"""
        <div style="background:#450a0a;border:1px solid #ef4444;border-radius:10px;
                    padding:14px 20px;margin-bottom:20px;display:flex;align-items:center;gap:12px;">
          <span style="font-size:20px;">🚨</span>
          <span style="color:#fca5a5;font-weight:700;font-size:14px;">
            {d['churned']} user{'s' if d['churned'] > 1 else ''} deleted their membership yesterday. Check immediately.
          </span>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body {{ margin:0;padding:0;background:#020617; }}
  * {{ box-sizing:border-box; }}
  .metrics-row {{ display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px; }}
  .two-col {{ display:flex;gap:16px;flex-wrap:wrap; }}
  .col {{ flex:1;min-width:260px; }}
</style>
</head>
<body>
<div style="max-width:920px;margin:0 auto;padding:28px 16px;
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
            color:#f1f5f9;background:#020617;">

  <!-- ── HEADER ──────────────────────────────────────────────────────────── -->
  <div style="background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);border-radius:16px;
              padding:28px 32px;margin-bottom:16px;border:1px solid #1e293b;">
    <div style="color:#475569;font-size:11px;font-weight:700;letter-spacing:0.1em;
                text-transform:uppercase;margin-bottom:6px;">
      BON Credit · Daily Intelligence Brief
    </div>
    <div style="color:#f8fafc;font-size:22px;font-weight:800;">{date_str}</div>
    <div style="color:#334155;font-size:12px;margin-top:4px;">
      Delivered 8:00 AM PST · Data from Amplitude · Analysis by Claude
    </div>
  </div>

  <!-- ── DAILY SUMMARY ───────────────────────────────────────────────────── -->
  <div style="background:#0c1829;border-radius:12px;border:1px solid #1e3a5f;
              padding:20px 24px;margin-bottom:20px;">
    <div style="font-size:10px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                color:#3b82f6;margin-bottom:10px;">Yesterday at a Glance</div>
    <p style="margin:0;font-size:15px;line-height:1.9;color:#cbd5e1;">{daily_summary}</p>
  </div>

  {churn_banner}

  <!-- ── EXECUTIVE SUMMARY (Claude) ─────────────────────────────────────── -->
  {_section_header("Executive Summary", "📋")}
  {_card(f'<div style="color:#cbd5e1;font-size:14px;line-height:1.8;">{exec_html}</div>')}

  <!-- ── GROWTH FUNNEL ───────────────────────────────────────────────────── -->
  {_section_header("Growth Funnel", "📈")}
  {_card(f'''
    <div style="font-size:12px;color:#475569;margin-bottom:14px;">
      Install → signup → onboarded → activated
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
      {_funnel_step("Installs", d["installs"])}
      {_funnel_step("Started", d["signup_started"])}
      {_funnel_step("Signed Up", d["signup_completed"], d["started_to_completed_rate"])}
      {_funnel_step("Onboarded", d["onboarding_complete"], d["signup_to_onboarding_rate"])}
      {_funnel_step("Card Linked", d["card_success"])}
      {_funnel_step("Bank Linked", d["bank_success"], "", is_last=True)}
    </div>
    <div style="margin-top:14px;display:flex;gap:20px;flex-wrap:wrap;">
      <span style="font-size:12px;color:#475569;">
        Install → signup: <strong style="color:{_pct_color(d["install_to_signup_rate"])}">{d["install_to_signup_rate"]}</strong>
      </span>
      <span style="font-size:12px;color:#475569;">
        Signup failed: <strong style="color:{"#ef4444" if d["signup_failed"] > 0 else "#475569"}">{d["signup_failed"]:,}</strong>
      </span>
      <span style="font-size:12px;color:#475569;">
        Onboarding drop-offs: <strong style="color:{"#f59e0b" if d["onboarding_dropoff"] > 0 else "#475569"}">{d["onboarding_dropoff"]:,}</strong>
      </span>
    </div>
  ''')}

  <!-- ── KEY METRICS ─────────────────────────────────────────────────────── -->
  {_section_header("Daily Metrics", "📊")}
  <div class="metrics-row">
    {_big_metric("Daily Active Users", f"{d['dau']:,}", f"Avg {d['avg_session_mins']} min/session", BLUE, "📱")}
    {_big_metric("New Signups", f"{d['new_signup_count']:,}", "", INDIGO, "👤")}
    {_big_metric("Cards Linked", f"{d['card_success']:,}", f"{d['card_success_rate']} success rate", GREEN, "💳")}
    {_big_metric("Banks Linked", f"{d['bank_success']:,}", f"{d['bank_success_rate']} success rate", GREEN, "🏦")}
    {_big_metric("Autopay Setups", f"{d['autopay_setups']:,}", "", AMBER, "🔁")}
    {_big_metric("Churned", f"{d['churned']:,}", "deleted membership", RED if d['churned'] > 0 else SLATE, "⚠️")}
  </div>

  <!-- ── ACTIVATION HEALTH ───────────────────────────────────────────────── -->
  {_section_header("Activation Health", "⚡")}
  <div class="two-col">
    <div class="col">
      {_card(f'''
        <div style="font-size:13px;font-weight:700;color:#94a3b8;margin-bottom:14px;">Card Linking</div>
        {_rate_bar("Add Card Flow", d["card_success"], d["card_failed"], d["card_success_rate"])}
        <div style="font-size:12px;color:#475569;">Initiated: {d["card_initiated"]:,} attempts</div>
      ''')}
    </div>
    <div class="col">
      {_card(f'''
        <div style="font-size:13px;font-weight:700;color:#94a3b8;margin-bottom:14px;">Bank Linking</div>
        {_rate_bar("Add Bank Flow", d["bank_success"], d["bank_failed"], d["bank_success_rate"])}
        <div style="font-size:12px;color:#475569;">Initiated: {d["bank_initiated"]:,} attempts</div>
      ''')}
    </div>
  </div>

  <!-- ── PAYMENTS ────────────────────────────────────────────────────────── -->
  {_section_header("Payments", "💰")}
  <div class="metrics-row">
    {_big_metric("Initiated", f"{d['bill_pay_initiated']:,}", "", SLATE, "🧾")}
    {_big_metric("Successful", f"{d['bill_pay_success']:,}", f"{d['bill_pay_success_rate']} rate", GREEN, "✅")}
    {_big_metric("Failed", f"{d['bill_pay_failed']:,}", "", RED if d["bill_pay_failed"] > 0 else SLATE, "❌")}
    {_big_metric("Extra Payments Set", f"{d['extra_payment_set']:,}", "above minimum", AMBER, "➕")}
    {_big_metric("Payer Verified", f"{d['payer_verified']:,}", "", SLATE, "🔐")}
  </div>

  <!-- ── ENGAGEMENT ──────────────────────────────────────────────────────── -->
  {_section_header("Engagement", "🔥")}
  <div class="metrics-row">
    {_big_metric("CredGPT Users", f"{d['credgpt_users']:,}", "used AI advisor", INDIGO, "🤖")}
    {_big_metric("Spinwheel", f"{d['spinwheel_users']:,}", "played the wheel", AMBER, "🎡")}
    {_big_metric("Rewards Redeemed", f"{d['reward_redeemed']:,}", "", GREEN, "🎁")}
    {_big_metric("Notif Clicks", f"{d['notif_clicks']:,}", "push tap-throughs", BLUE, "🔔")}
    {_big_metric("Debt Selectors", f"{d['select_debts']:,}", "engaged with debts", SLATE, "📋")}
    {_big_metric("Income Added", f"{d['income_added']:,}", "", SLATE, "💵")}
  </div>

  <!-- ── HIGHLIGHTS + WATCH LIST ────────────────────────────────────────── -->
  {_section_header("Analysis", "🔍")}
  <div class="two-col" style="margin-bottom:24px;">
    <div class="col">
      {_card(f'''
        <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;
                    color:#94a3b8;margin-bottom:12px;">⚡ Key Highlights</div>
        <div style="color:#cbd5e1;font-size:14px;line-height:1.75;">{highlights_html}</div>
      ''')}
    </div>
    <div class="col">
      {_card(f'''
        <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;
                    color:#c2410c;margin-bottom:12px;">🔍 Watch List</div>
        <div style="color:#fdba74;font-size:14px;line-height:1.75;">{watchlist_html}</div>
      ''', bg="#1c0a00", border="#7c2d12")}
    </div>
  </div>

  <!-- ── NEW SIGNUPS TABLE ──────────────────────────────────────────────── -->
  {_section_header("New User Breakdown", "👤")}
  <div style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;
              margin-bottom:32px;overflow:hidden;">
    <div style="padding:16px 20px;border-bottom:1px solid #1e293b;
                display:flex;align-items:baseline;gap:12px;">
      <span style="font-size:22px;font-weight:800;color:#f1f5f9;">{d['new_signup_count']:,}</span>
      <span style="font-size:14px;color:#475569;">new signups yesterday</span>
    </div>
    {signups_table}
  </div>

  <!-- ── FOOTER ─────────────────────────────────────────────────────────── -->
  <div style="text-align:center;color:#1e293b;font-size:11px;padding:8px 0 16px 0;">
    BON Credit · Automated Daily Report · Amplitude + Claude
  </div>

</div>
</body>
</html>"""
    return html


# ─────────────────────────────────────────────────────────────────────────────
# Plain-text fallback
# ─────────────────────────────────────────────────────────────────────────────

def _build_plaintext(report_date: datetime, d: dict, analysis: dict) -> str:
    date_str = report_date.strftime("%b %d, %Y")
    full_activation = sum(
        1 for u in d["new_signups"] if u["card_linked"] and u["bank_linked"]
    )
    return f"""BON Credit Daily Report — {date_str}

YESTERDAY AT A GLANCE
{d['new_signup_count']} new signups from {d['installs']} installs ({d['install_to_signup_rate']} rate).
{d['card_success']} cards linked, {d['bank_success']} banks linked, {full_activation} fully activated.
{d['dau']} active users, avg {d['avg_session_mins']} min/session.
Bill payments: {d['bill_pay_success']}/{d['bill_pay_initiated']} ({d['bill_pay_success_rate']}).
Churn: {d['churned']}.

GROWTH FUNNEL
Installs {d['installs']} → Started {d['signup_started']} → Signed up {d['new_signup_count']} ({d['started_to_completed_rate']}) → Onboarded {d['onboarding_complete']} ({d['signup_to_onboarding_rate']})
Failed: {d['signup_failed']} | Drop-offs: {d['onboarding_dropoff']}

ACTIVATION
Cards: {d['card_success']} linked / {d['card_failed']} failed ({d['card_success_rate']})
Banks: {d['bank_success']} linked / {d['bank_failed']} failed ({d['bank_success_rate']})
Autopay: {d['autopay_setups']}

PAYMENTS
{d['bill_pay_success']} / {d['bill_pay_initiated']} succeeded ({d['bill_pay_success_rate']}) | Failed: {d['bill_pay_failed']}

ENGAGEMENT
DAU: {d['dau']} | Avg session: {d['avg_session_mins']} min
CredGPT: {d['credgpt_users']} | Spinwheel: {d['spinwheel_users']} | Rewards: {d['reward_redeemed']} | Notif clicks: {d['notif_clicks']}

CHURN: {d['churned']}

EXECUTIVE SUMMARY
{analysis.get('executive_summary', '')}

HIGHLIGHTS
{analysis.get('highlights', '')}

WATCH LIST
{analysis.get('watch_list', '')}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Send
# ─────────────────────────────────────────────────────────────────────────────

def send_report(report_date: datetime, d: dict, analysis: dict):
    api_key    = os.environ["SENDGRID_API_KEY"]
    from_email = os.environ["FROM_EMAIL"]
    to_emails  = [e.strip() for e in os.environ["TO_EMAILS"].split(",") if e.strip()]

    date_str   = report_date.strftime("%b %d, %Y")
    subject    = f"BON Credit Daily Brief — {date_str}"
    if d["churned"] > 0:
        subject += " 🚨 CHURN ALERT"

    sg      = sendgrid.SendGridAPIClient(api_key=api_key)
    message = Mail(
        from_email=from_email,
        to_emails=[To(email=e) for e in to_emails],
        subject=subject,
        plain_text_content=_build_plaintext(report_date, d, analysis),
        html_content=_build_html(report_date, d, analysis),
    )

    resp = sg.send(message)
    if 200 <= resp.status_code < 300:
        print(f"[INFO] Email sent to {', '.join(to_emails)} (HTTP {resp.status_code})")
    else:
        raise RuntimeError(f"SendGrid returned {resp.status_code}: {resp.body}")

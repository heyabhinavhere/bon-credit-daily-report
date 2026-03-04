"""
Email Sender
Builds a Gmail-compatible HTML brief using table-based layout and sends via SendGrid.
Light theme, minimal and clean.
"""

import os
import sendgrid
from sendgrid.helpers.mail import Mail, To
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# Colour palette — light theme
# ─────────────────────────────────────────────────────────────────────────────
GREEN  = "#16a34a"
RED    = "#dc2626"
AMBER  = "#d97706"
BLUE   = "#2563eb"
INDIGO = "#4f46e5"
SLATE  = "#64748b"

BG     = "#f1f5f9"
CARD   = "#ffffff"
BORDER = "#e2e8f0"
TEXT   = "#0f172a"
MUTED  = "#64748b"
HEADER = "#f8fafc"


def _pct_color(pct_str: str, good_above: int = 50) -> str:
    if pct_str == "—":
        return SLATE
    try:
        val = int(pct_str.replace("%", ""))
        if val >= good_above:        return GREEN
        elif val >= good_above // 2: return AMBER
        else:                        return RED
    except ValueError:
        return SLATE


# ─────────────────────────────────────────────────────────────────────────────
# Component helpers — all table-based for Gmail compatibility
# ─────────────────────────────────────────────────────────────────────────────

def _section_header(title: str, emoji: str = "") -> str:
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:32px 0 12px 0;">
      <tr>
        <td style="font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
                   color:{MUTED};padding-bottom:8px;border-bottom:1px solid {BORDER};">
          {emoji}&nbsp; {title}
        </td>
      </tr>
    </table>"""


def _metric_card(label: str, value, sub: str = "", color: str = SLATE, emoji: str = "") -> str:
    sub_html = f'<div style="font-size:11px;color:{MUTED};margin-top:3px;">{sub}</div>' if sub else ""
    return f"""
    <table cellpadding="0" cellspacing="0" width="100%"
           style="background:{CARD};border-radius:12px;border:1px solid {BORDER};">
      <tr><td style="padding:20px 18px;">
        <div style="font-size:16px;margin-bottom:4px;">{emoji}</div>
        <div style="font-size:26px;font-weight:800;color:{color};line-height:1.1;">{value}</div>
        <div style="font-size:12px;color:{MUTED};margin-top:5px;font-weight:500;">{label}</div>
        {sub_html}
      </td></tr>
    </table>"""


def _metrics_row(cards: list) -> str:
    """Render a row of metric cards using table layout. Cards = list of _metric_card() strings."""
    cols = ""
    n = len(cards)
    for i, card in enumerate(cards):
        pad = "padding-right:12px;" if i < n - 1 else ""
        cols += f'<td width="{100 // n}%" style="{pad}vertical-align:top;">{card}</td>'
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
      <tr>{cols}</tr>
    </table>"""


def _two_col(left: str, right: str) -> str:
    """Side-by-side two column layout."""
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
      <tr>
        <td width="49%" style="vertical-align:top;padding-right:8px;">{left}</td>
        <td width="49%" style="vertical-align:top;">{right}</td>
      </tr>
    </table>"""


def _funnel_row(steps: list) -> str:
    """steps = list of (label, value, rate) tuples."""
    cells = ""
    for i, (label, value, rate) in enumerate(steps):
        rate_html = ""
        if rate:
            c = _pct_color(rate)
            rate_html = f'<div style="font-size:11px;color:{c};font-weight:700;margin-top:4px;">{rate}</div>'
        arrow = "" if i == len(steps) - 1 else \
            '<td style="color:#94a3b8;font-size:20px;padding:0 6px;vertical-align:middle;">→</td>'
        cells += f"""
        <td style="vertical-align:top;">
          <table cellpadding="0" cellspacing="0"
                 style="background:{CARD};border-radius:10px;border:1px solid {BORDER};">
            <tr><td style="padding:14px 18px;text-align:center;min-width:80px;">
              <div style="font-size:22px;font-weight:800;color:{TEXT};">{value:,}</div>
              <div style="font-size:11px;color:{MUTED};margin-top:3px;">{label}</div>
              {rate_html}
            </td></tr>
          </table>
        </td>
        {arrow}"""
    return f'<table cellpadding="0" cellspacing="4"><tr>{cells}</tr></table>'


def _rate_bar(label: str, success: int, failed: int, rate: str) -> str:
    color = _pct_color(rate, good_above=70)
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:14px;">
      <tr>
        <td style="font-size:13px;color:{TEXT};">{label}</td>
        <td align="right" style="font-size:13px;font-weight:700;color:{color};">{rate}</td>
      </tr>
    </table>
    <table width="100%" cellpadding="6" cellspacing="0"
           style="background:{BG};border-radius:6px;margin-bottom:4px;">
      <tr>
        <td style="font-size:12px;color:{GREEN};">✓ {success:,} success</td>
        <td align="right" style="font-size:12px;color:{RED};">✗ {failed:,} failed</td>
      </tr>
    </table>"""


def _card(content: str) -> str:
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:{CARD};border-radius:12px;border:1px solid {BORDER};margin-bottom:8px;">
      <tr><td style="padding:22px 24px;">{content}</td></tr>
    </table>"""


# ─────────────────────────────────────────────────────────────────────────────
# New signups table
# ─────────────────────────────────────────────────────────────────────────────

def _build_signups_table(new_signups: list) -> str:
    if not new_signups:
        return f'<p style="color:{MUTED};font-size:14px;padding:16px 0;">No new signups yesterday.</p>'

    rows = ""
    for u in new_signups:
        def badge(val: bool, yes_text: str = "✓", no_text: str = "✗"):
            if val:
                return f'<span style="background:#dcfce7;color:#15803d;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:600;">{yes_text}</span>'
            return f'<span style="background:#fee2e2;color:#b91c1c;padding:2px 7px;border-radius:10px;font-size:11px;font-weight:600;">{no_text}</span>'

        screens = " → ".join(u["screens"][:6]) if u["screens"] else "—"
        rows += f"""
        <tr style="border-bottom:1px solid {BORDER};">
          <td style="padding:9px 10px;font-size:12px;font-family:monospace;color:{MUTED};white-space:nowrap;">{str(u['user_id'])[:24]}</td>
          <td style="padding:9px 10px;text-align:center;">{badge(u['card_linked'], "Linked", "None")}</td>
          <td style="padding:9px 10px;text-align:center;">{badge(u['bank_linked'], "Linked", "None")}</td>
          <td style="padding:9px 10px;text-align:center;color:{MUTED};font-size:12px;">{u['cards_count']}/{u['banks_count']}</td>
          <td style="padding:9px 10px;text-align:center;">{badge(u['autopay_setup'], "On", "Off")}</td>
          <td style="padding:9px 10px;text-align:center;">{badge(u['used_credgpt'], "Yes", "No")}</td>
          <td style="padding:9px 10px;font-size:11px;color:{MUTED};max-width:200px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;">{screens}</td>
          <td style="padding:9px 10px;text-align:center;color:{MUTED};font-size:12px;white-space:nowrap;">{u['time_spent_mins']}m · {u['session_count']} sess</td>
          <td style="padding:9px 10px;text-align:center;color:{MUTED};font-size:12px;">{u['bill_payments_made']}</td>
        </tr>"""

    return f"""
    <div style="overflow-x:auto;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;min-width:800px;">
        <thead>
          <tr style="background:{BG};border-bottom:2px solid {BORDER};">
            <th style="padding:9px 10px;text-align:left;font-size:10px;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:0.06em;">User ID</th>
            <th style="padding:9px 10px;text-align:center;font-size:10px;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:0.06em;">Card</th>
            <th style="padding:9px 10px;text-align:center;font-size:10px;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:0.06em;">Bank</th>
            <th style="padding:9px 10px;text-align:center;font-size:10px;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:0.06em;">Cards/Banks</th>
            <th style="padding:9px 10px;text-align:center;font-size:10px;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:0.06em;">Autopay</th>
            <th style="padding:9px 10px;text-align:center;font-size:10px;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:0.06em;">CredGPT</th>
            <th style="padding:9px 10px;text-align:left;font-size:10px;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:0.06em;">Screens Visited</th>
            <th style="padding:9px 10px;text-align:center;font-size:10px;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:0.06em;">Time / Sessions</th>
            <th style="padding:9px 10px;text-align:center;font-size:10px;font-weight:700;color:{MUTED};text-transform:uppercase;letter-spacing:0.06em;">Payments</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# Main HTML builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_html(report_date: datetime, d: dict, analysis: dict) -> str:
    date_str    = report_date.strftime("%A, %B %d, %Y")
    signups_table = _build_signups_table(d["new_signups"])

    # ── Churn alert ─────────────────────────────────────────────────────────
    churn_banner = ""
    if d["churned"] > 0:
        churn_banner = f"""
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#fef2f2;border:1px solid #fca5a5;border-radius:10px;margin-bottom:20px;">
          <tr><td style="padding:14px 20px;">
            <span style="font-size:20px;">🚨</span>&nbsp;
            <span style="color:#991b1b;font-weight:700;font-size:14px;">
              {d['churned']} user{'s' if d['churned'] > 1 else ''} deleted their membership yesterday. Check immediately.
            </span>
          </td></tr>
        </table>"""

    # ── Funnel steps ─────────────────────────────────────────────────────────
    funnel = _funnel_row([
        ("Started",     d["signup_started"],   ""),
        ("Signed Up",   d["signup_completed"], d["started_to_completed_rate"]),
        ("Card Linked", d["card_success"],     ""),
        ("Bank Linked", d["bank_success"],     ""),
    ])

    fail_color = RED   if d["signup_failed"] > 0       else MUTED
    drop_color = AMBER if d["onboarding_dropoff"] > 0  else MUTED

    # ── Metric rows ──────────────────────────────────────────────────────────
    daily_row1 = _metrics_row([
        _metric_card("Daily Active Users", f"{d['dau']:,}",             "",                                         BLUE,   "📱"),
        _metric_card("New Signups",        f"{d['new_signup_count']:,}","",                                         INDIGO, "👤"),
        _metric_card("Cards Linked",       f"{d['card_success']:,}",    f"{d['card_success_rate']} success rate",   GREEN,  "💳"),
    ])
    daily_row2 = _metrics_row([
        _metric_card("Banks Linked",   f"{d['bank_success']:,}",  f"{d['bank_success_rate']} success rate",                         GREEN,                                  "🏦"),
        _metric_card("Autopay Setups", f"{d['autopay_setups']:,}","",                                                                AMBER,                                  "🔁"),
        _metric_card("Churned",        f"{d['churned']:,}",        "deleted membership", RED if d['churned'] > 0 else SLATE,         "⚠️"),
    ])

    pay_row1 = _metrics_row([
        _metric_card("Initiated",  f"{d['bill_pay_initiated']:,}", "",                                SLATE, "🧾"),
        _metric_card("Successful", f"{d['bill_pay_success']:,}",   f"{d['bill_pay_success_rate']} rate", GREEN, "✅"),
        _metric_card("Failed",     f"{d['bill_pay_failed']:,}",    "", RED if d["bill_pay_failed"] > 0 else SLATE, "❌"),
    ])
    pay_row2 = _metrics_row([
        _metric_card("Extra Payments Set", f"{d['extra_payment_set']:,}", "above minimum", AMBER, "➕"),
        _metric_card("Payer Verified",     f"{d['payer_verified']:,}",    "",               SLATE, "🔐"),
        _metric_card("",                   "",                             "",               SLATE, ""),   # spacer
    ])

    eng_row = _metrics_row([
        _metric_card("CredGPT / AI Chat Users", f"{d['credgpt_users']:,}", "unique users engaged with AI", INDIGO, "🤖"),
        _metric_card("AI Users % of DAU",
                     f"{round(d['credgpt_users'] / d['dau'] * 100) if d['dau'] else 0}%",
                     f"{d['credgpt_users']:,} of {d['dau']:,} active users", BLUE, "📊"),
        _metric_card("", "", "", SLATE, ""),  # spacer
    ])

    # ── Activation health ─────────────────────────────────────────────────────
    card_col = _card(f"""
        <div style="font-size:13px;font-weight:700;color:{MUTED};margin-bottom:14px;">Card Linking</div>
        {_rate_bar("Add Card Flow", d["card_success"], d["card_failed"], d["card_success_rate"])}
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;">
          <tr>
            <td style="font-size:12px;color:{MUTED};">Initiated: <strong style="color:{TEXT};">{d["card_initiated"]:,}</strong> users</td>
            <td align="right" style="font-size:12px;color:{MUTED};">
              <strong style="color:{GREEN};">{d["card_success"]:,} users</strong> linked
              &nbsp;·&nbsp;
              <strong style="color:{TEXT};">{d["total_cards_linked"]:,} total cards</strong>
            </td>
          </tr>
        </table>
    """)
    bank_col = _card(f"""
        <div style="font-size:13px;font-weight:700;color:{MUTED};margin-bottom:14px;">Bank Linking</div>
        {_rate_bar("Add Bank Flow", d["bank_success"], d["bank_failed"], d["bank_success_rate"])}
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;">
          <tr>
            <td style="font-size:12px;color:{MUTED};">Initiated: <strong style="color:{TEXT};">{d["bank_initiated"]:,}</strong> users</td>
            <td align="right" style="font-size:12px;color:{MUTED};">
              <strong style="color:{GREEN};">{d["bank_success"]:,} users</strong> linked
              &nbsp;·&nbsp;
              <strong style="color:{TEXT};">{d["total_banks_linked"]:,} total banks</strong>
            </td>
          </tr>
        </table>
    """)

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:{BG};">
<table width="100%" cellpadding="0" cellspacing="0" style="background:{BG};">
<tr><td align="center">
<table width="920" cellpadding="0" cellspacing="0"
       style="max-width:920px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
              color:{TEXT};background:{BG};padding:28px 16px;">

  <!-- ── HEADER ──────────────────────────────────────────────────────────── -->
  <tr><td style="padding-bottom:16px;">
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:{CARD};border-radius:16px;border:1px solid {BORDER};">
      <tr><td style="padding:28px 32px;">
        <div style="color:{MUTED};font-size:11px;font-weight:700;letter-spacing:0.1em;
                    text-transform:uppercase;margin-bottom:6px;">
          BON Credit · Daily Intelligence Brief
        </div>
        <div style="color:{TEXT};font-size:22px;font-weight:800;">{date_str}</div>
        <div style="color:#94a3b8;font-size:12px;margin-top:4px;">
          Delivered 8:00 AM PST · Data from Amplitude
        </div>
      </td></tr>
    </table>
  </td></tr>

  <!-- ── CHURN ALERT ──────────────────────────────────────────────────────── -->
  <tr><td>{churn_banner}</td></tr>

  <!-- ── GROWTH FUNNEL ───────────────────────────────────────────────────── -->
  <tr><td>{_section_header("Growth Funnel", "📈")}</td></tr>
  <tr><td>
    {_card(f'''
      <div style="font-size:12px;color:{MUTED};margin-bottom:14px;">
        Signup → activated
      </div>
      {funnel}
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:14px;">
        <tr><td style="font-size:12px;color:{MUTED};line-height:1.8;">
          Signup failed: <strong style="color:{fail_color};">{d["signup_failed"]:,}</strong>
          &nbsp;&nbsp;·&nbsp;&nbsp;
          Onboarding drop-offs: <strong style="color:{drop_color};">{d["onboarding_dropoff"]:,}</strong>
          &nbsp;&nbsp;·&nbsp;&nbsp;
          CredGPT / AI chat: <strong style="color:{INDIGO};">{d["credgpt_users"]:,} users engaged</strong>
        </td></tr>
      </table>
    ''')}
  </td></tr>

  <!-- ── DAILY METRICS ───────────────────────────────────────────────────── -->
  <tr><td>{_section_header("Daily Metrics", "📊")}</td></tr>
  <tr><td>{daily_row1}</td></tr>
  <tr><td>{daily_row2}</td></tr>

  <!-- ── ACTIVATION HEALTH ───────────────────────────────────────────────── -->
  <tr><td>{_section_header("Activation Health", "⚡")}</td></tr>
  <tr><td>{_two_col(card_col, bank_col)}</td></tr>

  <!-- ── PAYMENTS ────────────────────────────────────────────────────────── -->
  <tr><td>{_section_header("Payments", "💰")}</td></tr>
  <tr><td>{pay_row1}</td></tr>
  <tr><td>{pay_row2}</td></tr>

  <!-- ── ENGAGEMENT ──────────────────────────────────────────────────────── -->
  <tr><td>{_section_header("Engagement", "🔥")}</td></tr>
  <tr><td>{eng_row}</td></tr>

  <!-- ── NEW SIGNUPS TABLE ──────────────────────────────────────────────── -->
  <tr><td>{_section_header("New User Breakdown", "👤")}</td></tr>
  <tr><td>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:{CARD};border-radius:12px;border:1px solid {BORDER};margin-bottom:32px;">
      <tr>
        <td style="padding:16px 20px;border-bottom:1px solid {BORDER};">
          <span style="font-size:22px;font-weight:800;color:{TEXT};">{d['new_signup_count']:,}</span>
          <span style="font-size:14px;color:{MUTED};margin-left:8px;">new signups yesterday</span>
        </td>
      </tr>
      <tr><td>{signups_table}</td></tr>
    </table>
  </td></tr>

  <!-- ── FOOTER ─────────────────────────────────────────────────────────── -->
  <tr><td style="text-align:center;color:#94a3b8;font-size:11px;padding:8px 0 16px 0;">
    BON Credit · Automated Daily Report · Amplitude
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
    return html


# ─────────────────────────────────────────────────────────────────────────────
# Plain-text fallback
# ─────────────────────────────────────────────────────────────────────────────

def _build_plaintext(report_date: datetime, d: dict, analysis: dict) -> str:
    date_str = report_date.strftime("%b %d, %Y")
    return f"""BON Credit Daily Report — {date_str}

GROWTH FUNNEL
Installs {d['installs']} → Started {d['signup_started']} → Signed up {d['new_signup_count']} ({d['started_to_completed_rate']}) → Card linked {d['card_success']} → Bank linked {d['bank_success']}
Failed: {d['signup_failed']} | Drop-offs: {d['onboarding_dropoff']}
CredGPT / AI chat: {d['credgpt_users']} users engaged

ACTIVATION
Cards: {d['card_success']} linked / {d['card_failed']} failed ({d['card_success_rate']})
Banks: {d['bank_success']} linked / {d['bank_failed']} failed ({d['bank_success_rate']})
Autopay: {d['autopay_setups']}

PAYMENTS
{d['bill_pay_success']} / {d['bill_pay_initiated']} succeeded ({d['bill_pay_success_rate']}) | Failed: {d['bill_pay_failed']}

ENGAGEMENT
DAU: {d['dau']} | Avg session: {d['avg_session_mins']} min
CredGPT / AI Chat: {d['credgpt_users']} users ({round(d['credgpt_users'] / d['dau'] * 100) if d['dau'] else 0}% of DAU)

CHURN: {d['churned']}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Send
# ─────────────────────────────────────────────────────────────────────────────

def send_report(report_date: datetime, d: dict, analysis: dict):
    api_key    = os.environ["SENDGRID_API_KEY"]
    from_email = os.environ["FROM_EMAIL"]
    to_emails  = [e.strip() for e in os.environ["TO_EMAILS"].split(",") if e.strip()]

    date_str = report_date.strftime("%b %d, %Y")
    subject  = f"BON Credit Daily Brief — {date_str}"
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

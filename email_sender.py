"""
Email Sender
Builds a clean HTML email and delivers it via SendGrid.
"""

import os
import markdown
import sendgrid
from sendgrid.helpers.mail import Mail, To
from datetime import datetime


# ---------------------------------------------------------------------------
# HTML email template — inline styles for email client compatibility
# ---------------------------------------------------------------------------

def _build_html(
    report_date: datetime,
    summary_metrics: dict,
    analysis: dict,
    new_signups: list,
) -> str:
    date_str = report_date.strftime("%A, %B %d, %Y")
    dau = summary_metrics["total_active_users"]
    signups = summary_metrics["new_signup_count"]
    cards = summary_metrics["card_linked_count"]
    banks = summary_metrics["bank_linked_count"]
    avg_session = summary_metrics["avg_session_mins"]

    # Convert Claude markdown to HTML
    exec_html = markdown.markdown(analysis.get("executive_summary", ""))
    highlights_html = markdown.markdown(analysis.get("highlights", ""))
    watchlist_html = markdown.markdown(analysis.get("watch_list", ""))

    # Build new signups table rows
    table_rows = ""
    for u in new_signups:
        card_badge = (
            '<span style="background:#d1fae5;color:#065f46;padding:2px 8px;border-radius:12px;font-size:12px;">✓ Linked</span>'
            if u["card_linked"]
            else '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:12px;font-size:12px;">✗ None</span>'
        )
        bank_badge = (
            '<span style="background:#d1fae5;color:#065f46;padding:2px 8px;border-radius:12px;font-size:12px;">✓ Linked</span>'
            if u["bank_linked"]
            else '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:12px;font-size:12px;">✗ None</span>'
        )
        screens = ", ".join(u["screens"]) if u["screens"] else "—"
        table_rows += f"""
        <tr style="border-bottom:1px solid #f1f5f9;">
          <td style="padding:10px 12px;font-size:13px;font-family:monospace;color:#475569;">{u['user_id']}</td>
          <td style="padding:10px 12px;text-align:center;">{card_badge}</td>
          <td style="padding:10px 12px;text-align:center;">{bank_badge}</td>
          <td style="padding:10px 12px;font-size:12px;color:#64748b;">{u['cards_count']}</td>
          <td style="padding:10px 12px;font-size:12px;color:#64748b;">{u['banks_count']}</td>
          <td style="padding:10px 12px;font-size:12px;color:#64748b;max-width:220px;overflow:hidden;">{screens}</td>
          <td style="padding:10px 12px;font-size:12px;color:#64748b;">{u['time_spent_mins']} min</td>
          <td style="padding:10px 12px;font-size:12px;color:#64748b;">{u['session_count']}</td>
        </tr>
        """

    if not table_rows:
        table_rows = '<tr><td colspan="8" style="padding:20px;text-align:center;color:#94a3b8;">No new signups yesterday.</td></tr>'

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">

  <div style="max-width:860px;margin:0 auto;padding:32px 16px;">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1e293b 0%,#334155 100%);border-radius:16px;padding:32px 36px;margin-bottom:24px;">
      <div style="color:#94a3b8;font-size:13px;font-weight:500;letter-spacing:0.05em;text-transform:uppercase;margin-bottom:8px;">BON Credit · Daily Intelligence Report</div>
      <div style="color:#f1f5f9;font-size:24px;font-weight:700;">{date_str}</div>
      <div style="color:#64748b;font-size:13px;margin-top:6px;">Delivered 8:00 AM PST · Powered by Claude</div>
    </div>

    <!-- Key Metrics Row -->
    <div style="display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap;">
      {_metric_card("New Signups", signups, "#6366f1", "👤")}
      {_metric_card("Daily Active Users", dau, "#0ea5e9", "📱")}
      {_metric_card("Cards Linked", cards, "#10b981", "💳")}
      {_metric_card("Banks Linked", banks, "#f59e0b", "🏦")}
      {_metric_card("Avg Session", f"{avg_session} min", "#8b5cf6", "⏱")}
    </div>

    <!-- Executive Summary -->
    <div style="background:#ffffff;border-radius:12px;padding:28px 32px;margin-bottom:20px;border:1px solid #e2e8f0;">
      <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#94a3b8;margin-bottom:16px;">Executive Summary</div>
      <div style="color:#1e293b;font-size:15px;line-height:1.75;">{exec_html}</div>
    </div>

    <!-- Two-column: Highlights + Watch List -->
    <div style="display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap;">

      <div style="flex:1;min-width:280px;background:#ffffff;border-radius:12px;padding:24px 28px;border:1px solid #e2e8f0;">
        <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#94a3b8;margin-bottom:14px;">⚡ Key Highlights</div>
        <div style="color:#1e293b;font-size:14px;line-height:1.7;">{highlights_html}</div>
      </div>

      <div style="flex:1;min-width:280px;background:#fff7ed;border-radius:12px;padding:24px 28px;border:1px solid #fed7aa;">
        <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#c2410c;margin-bottom:14px;">🔍 Watch List</div>
        <div style="color:#431407;font-size:14px;line-height:1.7;">{watchlist_html}</div>
      </div>

    </div>

    <!-- New Signups Table -->
    <div style="background:#ffffff;border-radius:12px;border:1px solid #e2e8f0;margin-bottom:24px;overflow:hidden;">
      <div style="padding:20px 28px;border-bottom:1px solid #f1f5f9;">
        <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#94a3b8;margin-bottom:4px;">New User Breakdown</div>
        <div style="font-size:22px;font-weight:700;color:#1e293b;">{signups} new signups yesterday</div>
      </div>
      <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr style="background:#f8fafc;">
              <th style="padding:10px 12px;text-align:left;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;">User ID</th>
              <th style="padding:10px 12px;text-align:center;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;">Card</th>
              <th style="padding:10px 12px;text-align:center;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;">Bank</th>
              <th style="padding:10px 12px;text-align:left;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;"># Cards</th>
              <th style="padding:10px 12px;text-align:left;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;"># Banks</th>
              <th style="padding:10px 12px;text-align:left;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;">Screens Visited</th>
              <th style="padding:10px 12px;text-align:left;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;">Time Spent</th>
              <th style="padding:10px 12px;text-align:left;font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;">Sessions</th>
            </tr>
          </thead>
          <tbody>
            {table_rows}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Footer -->
    <div style="text-align:center;color:#94a3b8;font-size:12px;padding:16px;">
      BON Credit · Automated Daily Report · Data from Amplitude
    </div>

  </div>
</body>
</html>"""
    return html


def _metric_card(label: str, value, color: str, emoji: str) -> str:
    return f"""
    <div style="flex:1;min-width:140px;background:#ffffff;border-radius:12px;padding:20px 20px;border:1px solid #e2e8f0;border-top:3px solid {color};">
      <div style="font-size:22px;margin-bottom:8px;">{emoji}</div>
      <div style="font-size:28px;font-weight:800;color:#1e293b;line-height:1;">{value}</div>
      <div style="font-size:12px;color:#94a3b8;margin-top:6px;font-weight:500;">{label}</div>
    </div>
    """


# ---------------------------------------------------------------------------
# Send via SendGrid
# ---------------------------------------------------------------------------

def send_report(
    report_date: datetime,
    summary_metrics: dict,
    analysis: dict,
    new_signups: list,
):
    api_key = os.environ["SENDGRID_API_KEY"]
    from_email = os.environ["FROM_EMAIL"]
    to_emails_raw = os.environ["TO_EMAILS"]  # comma-separated
    to_emails = [e.strip() for e in to_emails_raw.split(",") if e.strip()]

    date_str = report_date.strftime("%b %d, %Y")
    subject = f"BON Credit Daily Report — {date_str}"

    html_content = _build_html(report_date, summary_metrics, analysis, new_signups)

    # Plain-text fallback
    plain_text = f"""
BON Credit Daily Report — {date_str}

METRICS
New Signups: {summary_metrics['new_signup_count']}
Daily Active Users: {summary_metrics['total_active_users']}
Cards Linked: {summary_metrics['card_linked_count']}
Banks Linked: {summary_metrics['bank_linked_count']}
Avg Session: {summary_metrics['avg_session_mins']} min

--- EXECUTIVE SUMMARY ---
{analysis.get('executive_summary', '')}

--- KEY HIGHLIGHTS ---
{analysis.get('highlights', '')}

--- WATCH LIST ---
{analysis.get('watch_list', '')}
"""

    sg = sendgrid.SendGridAPIClient(api_key=api_key)

    message = Mail(
        from_email=from_email,
        to_emails=[To(email=e) for e in to_emails],
        subject=subject,
        plain_text_content=plain_text,
        html_content=html_content,
    )

    response = sg.send(message)
    status = response.status_code

    if 200 <= status < 300:
        print(f"[INFO] Email sent successfully to {', '.join(to_emails)} (status {status})")
    else:
        print(f"[ERROR] SendGrid returned status {status}: {response.body}")
        raise RuntimeError(f"Email delivery failed with status {status}")

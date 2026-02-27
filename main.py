"""
BON Credit Daily Amplitude Report
----------------------------------
Entry point. Run this script daily (Railway cron) to:
  1. Pull yesterday's data from Amplitude
  2. Analyze it with Claude
  3. Email the report via SendGrid

Usage:
  python main.py               # analyzes yesterday
  python main.py --date 2025-03-15  # analyzes a specific date (for testing/backfill)
"""

import sys
import argparse
from datetime import datetime, timedelta

from amplitude_client import AmplitudeClient
from claude_analyzer import analyze_with_claude
from email_sender import send_report


def main():
    parser = argparse.ArgumentParser(description="BON Credit Daily Report")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date to analyze in YYYY-MM-DD format. Defaults to yesterday.",
    )
    args = parser.parse_args()

    if args.date:
        try:
            report_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"[ERROR] Invalid date format '{args.date}'. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        report_date = datetime.now() - timedelta(days=1)

    date_str = report_date.strftime("%Y-%m-%d")
    print(f"\n{'='*55}")
    print(f"  BON Credit Daily Report — {date_str}")
    print(f"{'='*55}\n")

    # ------------------------------------------------------------------ #
    # Step 1: Fetch raw events from Amplitude
    # ------------------------------------------------------------------ #
    print("[STEP 1/3] Fetching data from Amplitude...")
    client = AmplitudeClient()

    try:
        raw_events = client.export_events(report_date)
    except Exception as e:
        print(f"[ERROR] Amplitude export failed: {e}")
        print("[INFO]  Check your AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY.")
        print("[INFO]  Also verify that the Export API is enabled on your Amplitude plan.")
        sys.exit(1)

    if not raw_events:
        print(f"[WARN] No events found for {date_str}. Was it a holiday or an outage?")
        # Still send the email so founders know
        report_data = {
            "total_active_users": 0,
            "new_signup_count": 0,
            "card_linked_count": 0,
            "bank_linked_count": 0,
            "avg_session_mins": 0,
            "new_signups": [],
            "all_users": [],
        }
    else:
        report_data = client.process_events(raw_events)

    print(f"  → Active users:   {report_data['total_active_users']:,}")
    print(f"  → New signups:    {report_data['new_signup_count']:,}")
    print(f"  → Cards linked:   {report_data['card_linked_count']:,}")
    print(f"  → Banks linked:   {report_data['bank_linked_count']:,}")

    # ------------------------------------------------------------------ #
    # Step 2: Analyze with Claude
    # ------------------------------------------------------------------ #
    print("\n[STEP 2/3] Analyzing data with Claude...")
    try:
        analysis = analyze_with_claude(report_data, report_date)
        print("  → Analysis complete.")
    except Exception as e:
        print(f"[ERROR] Claude analysis failed: {e}")
        analysis = {
            "executive_summary": "Analysis unavailable — Claude API error. See logs.",
            "highlights": "",
            "watch_list": "",
        }

    # ------------------------------------------------------------------ #
    # Step 3: Send the email
    # ------------------------------------------------------------------ #
    print("\n[STEP 3/3] Sending email via SendGrid...")
    try:
        send_report(
            report_date=report_date,
            summary_metrics=report_data,
            analysis=analysis,
            new_signups=report_data["new_signups"],
        )
    except Exception as e:
        print(f"[ERROR] Email delivery failed: {e}")
        sys.exit(1)

    print(f"\n✓ Report for {date_str} delivered successfully.\n")


if __name__ == "__main__":
    main()

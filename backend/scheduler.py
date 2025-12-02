from apscheduler.schedulers.background import BackgroundScheduler
from email_summarizer.email_summarizer import (
    authenticate_gmail,
    get_last_24h_emails,
    get_email_details,
    summarize_email,
    analyze_emails_with_ai
)
from database.database import SessionLocal
from database.models import Email
from database.helpers import save_email
import os

def auto_fetch_emails():
    print("⏳ Running auto-fetch job...")

    db = SessionLocal()

    # Get list of all users (unique user_email from Email table)
    users = db.query(Email.user_email).distinct().all()
    db.close()

    for (user_email,) in users:
        print(f"📩 Auto-fetching emails for {user_email}")

        try:
            service = authenticate_gmail(user_email)
        except Exception as e:
            print(f"❌ Failed to authenticate {user_email}: {e}")
            continue

        messages = get_last_24h_emails(service)

        if not messages:
            continue

        for msg in messages:
            sender, subject, body, thread_id = get_email_details(service, msg["id"])
            summary = summarize_email(subject, body)

            save_email(
                email_id=msg["id"],
                user_email=user_email,
                sender=sender,
                subject=subject,
                body=body,
                summary=summary,
                priority="Medium",
                thread_id=thread_id
            )

    print("✅ Auto-fetch cycle completed")


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_fetch_emails, "interval", minutes=5)  # fetch every 5 minutes
    scheduler.start()
    print("🚀 APScheduler Started (fetching every 5 min)")

# server.py
from fastapi import FastAPI, Request, Form, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from email_summarizer.email_summarizer import categorize_email_with_ai 
from scheduler import start_scheduler
from database.helpers import save_email, assign_smart_thread_id
from database.models import Email, EmailAttachment
import os
import json
import requests
import base64

# Gmail summarizer functions
from email_summarizer.email_summarizer import (
    authenticate_gmail,
    get_last_24h_emails,
    get_email_details,
    summarize_email,
    analyze_emails_with_ai
)

# ORM imports
from database.database import Base, engine, get_db, SessionLocal
from database.models import Feedback, Email

# Create tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI()
start_scheduler()

# Gmail scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "mAiL API is running 🚀"}


@app.get("/login-url")
def login_url():
    """Generate Gmail OAuth URL"""
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri='http://localhost:8000/auth/callback'
    )
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    return {"auth_url": auth_url}


@app.get("/auth/callback")
def auth_callback(code: str):
    """Google OAuth callback"""
    flow = Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri='http://localhost:8000/auth/callback'
    )
    flow.fetch_token(code=code)
    creds = flow.credentials

    user_email = None
    try:
        if creds.id_token and "email" in creds.id_token:
            user_email = creds.id_token["email"]
        else:
            response = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {creds.token}"}
            )
            user_email = response.json().get("email", "unknown")
    except Exception as e:
        return {"error": f"Failed to fetch user info: {str(e)}"}

    if not creds.refresh_token:
        print("⚠️ Missing refresh_token. User must re-consent next login.")

    os.makedirs("tokens", exist_ok=True)
    with open(f"tokens/{user_email}.json", "w") as token_file:
        token_file.write(creds.to_json())

    print(f"✅ Logged in as: {user_email}")
    return {"success": True, "user_email": user_email}


def update_email_priority(email_id, new_priority):
    db = SessionLocal()
    email_obj = db.query(Email).filter(Email.email_id == email_id).first()
    if email_obj:
        email_obj.priority = new_priority
        db.commit()
    db.close()


@app.get("/fetch-emails")
def fetch_emails(user_email: str):
    """Fetch last 24h Gmail emails and summarize"""
    token_path = f"tokens/{user_email}.json"
    if not os.path.exists(token_path):
        return {"error": f"No token found for {user_email}. Please re-login."}

    try:
        service = authenticate_gmail(user_email)
    except Exception as e:
        return {"error": "Authentication failed. Please re-login.", "details": str(e)}
    
    messages = get_last_24h_emails(service)
    if not messages:
        return {"overall_summary": "No new emails in last 24 hours", "emails": []}

    emails = []
    for msg in messages[:15]:
        sender, subject, body, thread_id, attachments = get_email_details(service, msg['id'])
        summary = summarize_email(subject, body)
        emails.append({
            "email_id": msg["id"],
            "from": sender,
            "subject": subject,
            "summary": summary
        })

        save_email(
        email_id=msg["id"],
        user_email=user_email,
        sender=sender,
        subject=subject,
        body=body,
        summary=summary,
        priority="Medium", 
        thread_id=thread_id,
        attachments=attachments
        )

    ai_data = analyze_emails_with_ai(emails)

    for email in emails:
        match = next((p for p in ai_data["priorities"] if p["subject"] == email["subject"]), None)
        final_priority = match["priority"] if match else "Medium"
        email["priority"] = final_priority

        update_email_priority(email["email_id"], final_priority)

    return {
        "overall_summary": ai_data["overall_summary"],
        "emails": emails
    }


@app.get("/smart-threads")
def get_smart_threads(user_email: str, db: Session = Depends(get_db)):
    emails = db.query(Email).filter(Email.user_email == user_email).all()

    grouped = {}
    for email in emails:
        if email.smart_thread_id not in grouped:
            grouped[email.smart_thread_id] = []
        grouped[email.smart_thread_id].append({
            "email_id": email.email_id,
            "subject": email.subject,
            "summary": email.summary,
            "priority": email.priority,
            "category": email.category,
            "timestamp": email.timestamp
        })

    thread_list = [
        {"smart_thread_id": tid, "emails": msgs}
        for tid, msgs in grouped.items()
    ]

    return {"smart_threads": thread_list}


@app.get("/threads")
def get_threads(
    user_email: str,
    mode: str = "subject",     # default threading
    db: Session = Depends(get_db)
):
    emails = db.query(Email).filter(Email.user_email == user_email).all()
    if not emails:
        return {"threads": []}

    grouped = {}

    for email in emails:
        if mode == "subject":
            key = assign_smart_thread_id(email.subject)
        elif mode == "category":
            key = email.category or "Uncategorized"
        elif mode == "priority":
            key = email.priority or "Medium"
        elif mode == "sender":
            key = email.sender.split("<")[0].strip()   # clean sender name
        elif mode == "date":
            key = email.timestamp.date()
        else:
            key = "Other"

        if key not in grouped:
            grouped[key] = []

        grouped[key].append({
            "email_id": email.email_id,
            "sender": email.sender,
            "subject": email.subject,
            "summary": email.summary,
            "priority": email.priority,
            "category": email.category,
            "thread_id": email.thread_id,
            "timestamp": email.timestamp
        })

    # Convert dict → list for clean JSON output
    thread_list = [
        {"group_key": str(key), "emails": msgs}
        for key, msgs in grouped.items()
    ]

    return {"threads": thread_list}



@app.get("/category-stats")
def category_stats(user_email: str, db: Session = Depends(get_db)):
    emails = db.query(Email).filter(Email.user_email == user_email).all()

    stats = {}
    for mail in emails:
        cat = mail.category
        stats[cat] = stats.get(cat, 0) + 1

    return stats


@app.get("/attachments")
def list_attachments(email_id: str, db: Session = Depends(get_db)):
    attachments = db.query(EmailAttachment).filter(EmailAttachment.email_id == email_id).all()
    
    return [
        {
            "filename": att.filename,
            "mime_type": att.mime_type,
            "size": att.size,
            "attachment_id": att.attachment_id
        }
        for att in attachments
    ]


@app.get("/search")
def search_emails(
    user_email: str,
    q: str = Query(..., description="Search text"),
    db: Session = Depends(get_db)
):
    """Search emails by subject, sender, body, or summary"""

    query_str = f"%{q.lower()}%"

    results = db.query(Email).filter(
        Email.user_email == user_email,
        (
            Email.subject.ilike(query_str) |
            Email.sender.ilike(query_str) |
            Email.body.ilike(query_str) |
            Email.summary.ilike(query_str) |
            Email.priority.ilike(query_str)
        )
    ).all()

    return [
        {
            "email_id": e.email_id,
            "sender": e.sender,
            "subject": e.subject,
            "summary": e.summary,
            "priority": e.priority,
            "timestamp": e.timestamp
        }
        for e in results
    ]

@app.post("/feedback")
async def feedback(
    email_id: str = Form(None),
    priority: str = Form(None),
    is_correct: str = Form(None),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Save user feedback to ORM database"""
    try:
        data = await request.json()
        email_id = email_id or data.get("email_id") or data.get("id") or data.get("emailId")
        priority = priority or data.get("priority") or data.get("prioritySelected")
        is_correct = is_correct or data.get("is_correct") or data.get("correct")
    except:
        pass

    is_correct = True if str(is_correct).lower() in ["true", "1", "yes"] else False

    if not email_id or not priority:
        return {"success": False, "error": "Missing required fields"}

    feedback = Feedback(email_id=email_id, priority=priority, is_correct=is_correct)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return {"success": True, "message": "Feedback saved successfully"}


@app.get("/feedback")
def feedback_list(db: Session = Depends(get_db)):
    """Return all feedback records"""
    feedbacks = db.query(Feedback).order_by(Feedback.timestamp.desc()).all()
    return [
        {
            "email_id": f.email_id,
            "priority": f.priority,
            "is_correct": f.is_correct,
            "timestamp": f.timestamp
        }
        for f in feedbacks
    ]


@app.get("/feedback-stats")
def feedback_stats(db: Session = Depends(get_db)):
    """Get feedback statistics"""
    total = db.query(Feedback).count()
    correct = db.query(Feedback).filter(Feedback.is_correct == True).count()
    priorities = db.query(Feedback.priority).all()

    priority_count = {}
    for (p,) in priorities:
        priority_count[p] = priority_count.get(p, 0) + 1

    accuracy = round((correct / total * 100) if total > 0 else 0, 2)

    return {
        "total_feedback": total,
        "correct_classifications": correct,
        "accuracy": accuracy,
        "feedback_by_priority": priority_count
    }

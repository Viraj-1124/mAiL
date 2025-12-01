# server.py
from fastapi import FastAPI, Request, Form, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from email_summarizer.email_summarizer import categorize_email_with_ai
from utils.subject_similarity import subject_similarity
import os
import json
import requests

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


def assign_smart_thread_id(user_email, subject):
    db = SessionLocal()

    emails = db.query(Email).filter(Email.user_email == user_email).all()

    best_match = None
    best_score = 0

    for email in emails:
        score = subject_similarity(subject, email.subject)
        if score > 85 and score > best_score:
            best_match = email.smart_thread_id
            best_score = score

    db.close()

    # If no match found → create new smart thread id
    if not best_match:
        return f"smart-{os.urandom(4).hex()}"

    return best_match


def save_email(email_id, user_email, sender, subject, body, summary, priority, thread_id):
    db = SessionLocal()

    # Avoid duplicates
    existing = db.query(Email).filter(Email.email_id == email_id).first()
    if existing:
        db.close()
        return
    
    category = categorize_email_with_ai(subject, body)
    smart_thread_id = assign_smart_thread_id(user_email, subject)

    new_email = Email(
        email_id=email_id,
        user_email=user_email,
        sender=sender,
        subject=subject,
        body=body,
        summary=summary,
        priority=priority,
        category=category,
        thread_id=thread_id,
        smart_thread_id=smart_thread_id
    )

    db.add(new_email)
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
        sender, subject, body, thread_id = get_email_details(service, msg['id'])
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
        thread_id=thread_id
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
def get_threads(user_email: str, db: Session = Depends(get_db)):
    emails = db.query(Email).filter(Email.user_email == user_email).all()

    grouped = {}
    for email in emails:
        if email.thread_id not in grouped:
            grouped[email.thread_id] = []
        grouped[email.thread_id].append({
            "email_id": email.email_id,
            "sender": email.sender,
            "subject": email.subject,
            "summary": email.summary,
            "priority": email.priority,
            "category": email.category,
            "timestamp": email.timestamp
        })

    thread_list = [
        {"thread_id": tid, "emails": msgs}
        for tid, msgs in grouped.items()
    ]

    return {"threads": thread_list}


@app.post("/categorize")
def categorize(email_id: str, db: Session = Depends(get_db)):
    """AI categorizes a stored email and updates DB."""
    
    email = db.query(Email).filter(Email.email_id == email_id).first()
    if not email:
        return {"error": "Email not found"}

    category = categorize_email_with_ai(email.subject, email.body)

    email.category = category
    db.commit()

    return {"success": True, "email_id": email_id, "category": category}


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

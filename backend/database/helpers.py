from database.database import SessionLocal
from database.models import Email
from utils.subject_similarity import subject_similarity
from email_summarizer.email_summarizer import smart_categorize_email
import os

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
    
    category = smart_categorize_email(subject, body, sender)
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
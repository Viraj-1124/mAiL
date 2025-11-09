# main.py
from database.database import SessionLocal
from database.models import Feedback

db = SessionLocal()
feedbacks = db.query(Feedback).all()

for f in feedbacks:
    print(f.id, f.email_id, f.priority, f.is_correct, f.timestamp)

db.close()

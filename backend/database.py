import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "feedback.db"

def init_database():
    """Initialize the feedback database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT NOT NULL,
            priority TEXT NOT NULL,
            is_correct BOOLEAN NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

def save_feedback(email_id: str, priority: str, is_correct: bool):
    """Save user feedback to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO feedback (email_id, priority, is_correct, timestamp) VALUES (?, ?, ?, ?)",
        (email_id, priority, is_correct, datetime.now().isoformat())
    )
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Feedback saved successfully"}

def get_all_feedback():
    """Retrieve all feedback records"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT email_id, priority, is_correct, timestamp FROM feedback ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    
    conn.close()
    
    feedback_list = [
        {
            "email_id": row[0],
            "priority": row[1],
            "is_correct": bool(row[2]),
            "timestamp": row[3]
        }
        for row in rows
    ]
    
    return feedback_list

def get_feedback_stats():
    """Get feedback statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM feedback")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM feedback WHERE is_correct = 1")
    correct = cursor.fetchone()[0]
    
    cursor.execute("SELECT priority, COUNT(*) FROM feedback GROUP BY priority")
    by_priority = dict(cursor.fetchall())
    
    conn.close()
    
    return {
        "total_feedback": total,
        "correct_classifications": correct,
        "accuracy": round((correct / total * 100) if total > 0 else 0, 2),
        "feedback_by_priority": by_priority
    }
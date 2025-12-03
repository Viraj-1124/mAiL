# email_summarizer/email_summarizer.py
import ssl
import requests
import json
import os
import base64
import datetime
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv("/home/sadlin/LinuxData/mAIL/mAiL/.env")
# Ignore SSL verification warnings

ssl._create_default_https_context = ssl._create_unverified_context
requests.packages.urllib3.disable_warnings()

# OpenAI client (uses OpenRouter API)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# Gmail scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]


def authenticate_gmail(user_email: str):
    """Authenticate Gmail for a specific user."""
    os.makedirs("tokens", exist_ok=True)
    token_path = f"tokens/{user_email}.json"

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def get_last_24h_emails(service):
    """Fetch emails received in last 24 hours."""
    now = datetime.datetime.now(datetime.UTC)
    yesterday = now - datetime.timedelta(days=1)
    query = f"after:{int(yesterday.timestamp())}"
    results = service.users().messages().list(userId='me', q=query, maxResults=20).execute()
    return results.get('messages', [])


def get_email_details(service, msg_id):
    msg = service.users().messages().get(
        userId='me',
        id=msg_id,
        format='full'
    ).execute()

    headers = msg['payload']['headers']
    parts = msg['payload'].get('parts', [])

    sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')

    body = ""
    attachments = []

    for part in parts:
        mime_type = part.get("mimeType", "")
        filename = part.get("filename", "")

        # ATTACHMENT detection
        if filename:
            body_info = part.get("body", {})
            attachments.append({
                "filename": filename,
                "mime_type": mime_type,
                "size": body_info.get("size", 0),
                "attachment_id": body_info.get("attachmentId")
            })
            continue

        # Extract body (text/plain or html)
        data = part.get("body", {}).get("data")
        if data:
            try:
                decoded = base64.urlsafe_b64decode(data).decode("utf-8")
                body = decoded
            except:
                pass

    clean_body = body.strip().replace("\r", "").replace("\n", " ")[:2000]
    thread_id = msg.get("threadId")

    return sender, subject, clean_body, thread_id, attachments


def summarize_email(subject, body):
    """Simple text-based summarization."""
    text = body.split('.')
    summary = text[0][:200] if text else body[:200]
    if len(summary.split()) > 25:
        summary = ' '.join(summary.split()[:25]) + '...'
    return summary


def analyze_emails_with_ai(emails):
    """Analyze and prioritize emails using GPT."""
    email_text = "\n".join([
        f"From: {e['from']}\nSubject: {e['subject']}\nSummary: {e['summary']}"
        for e in emails
    ])

    prompt = f"""
    You are an intelligent email assistant. You MUST return a VALID JSON ONLY.

    Based on these emails, produce:
    1. An overall summary.
    2. Priority for each email: High / Medium / Low.

    Return JSON in this EXACT format:
    {{
      "overall_summary": "summary text",
      "priorities": [
        {{"subject": "subject text", "priority": "High"}},
        ...
      ]
    }}

    Emails:
    {email_text}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    raw_output = response.choices[0].message.content.strip()
    try:
        return json.loads(raw_output)
    except:
        return {"overall_summary": raw_output, "priorities": []}


def categorize_email_with_ai(subject, body, sender=None):
    """Advanced intelligent categorization using GPT."""

    prompt = f"""
    Analyze the email and assign the MOST appropriate category.
    
    You MUST choose from these categories ONLY:

    - Work
    - College
    - Personal
    - Bank/Finance
    - Offers/Promotions
    - Travel/Tickets
    - Bills/Payments
    - Security Alert
    - Subscriptions/Newsletters
    - Events/Conferences
    - Important/Deadline
    - LinkedIn
    - Spam

    Email details:
    Sender: {sender}
    Subject: {subject}
    Body: {body[:1000]}

    Return JSON in this exact format:
    {{
        "category": "CategoryName"
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    raw_output = response.choices[0].message.content.strip()

    try:
        data = json.loads(raw_output)
        return data.get("category", "Personal")
    except:
        return "Personal"


def infer_category_from_sender(sender):
    sender = sender.lower()

    if "vit.edu" in sender:
        return "College"
    if "bank" in sender or "hdfc" in sender or "sbi" in sender:
        return "Bank/Finance"
    if "no-reply" in sender or "newsletter" in sender:
        return "Subscriptions/Newsletters"
    if "security" in sender:
        return "Security Alert"
    
    return None


def smart_categorize_email(subject, body, sender):
    # 1️⃣ Domain-based quick classification
    sender_based = infer_category_from_sender(sender)
    if sender_based:
        return sender_based

    # 2️⃣ AI-based classification
    ai_category = categorize_email_with_ai(subject, body, sender)

    return ai_category


def main():
    """Run manual test for local debugging."""
    print("🔑 Authenticating...")
    service = authenticate_gmail("your_email_here@gmail.com")

    print("📬 Fetching last 24h emails...")
    messages = get_last_24h_emails(service)
    if not messages:
        print("No new emails in last 24 hours.")
        return

    print("\n📄 Daily Email Summary\n" + "="*45)
    emails = []
    for i, msg in enumerate(messages[:15], 1):
        sender, subject, body = get_email_details(service, msg['id'])
        summary = summarize_email(subject, body)
        emails.append({"from": sender, "subject": subject, "snippet": summary})
        print(f"\n{i}. 📨 From: {sender}\n   Subject: {subject}\n   Summary: {summary}\n")

    ai_summary = analyze_emails_with_ai(emails)
    print("\n🤖 AI Analysis:\n" + "="*45)
    print(ai_summary)


if __name__ == "__main__":
    main()

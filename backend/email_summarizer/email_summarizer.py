# email_summarizer.py
import ssl
import requests
import json
ssl._create_default_https_context = ssl._create_unverified_context
requests.packages.urllib3.disable_warnings()

#from __future__ import print_function
import os.path
import base64
import datetime
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)
# Scope: read-only Gmail access
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]

def authenticate_gmail(user_email: str):
    """Authenticate Gmail for a specific user (multi-user support)."""
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
    messages = results.get('messages', [])
    return messages


def get_email_details(service, msg_id):
    """Extract sender, subject, and plain body from email."""
    msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    headers = msg['payload']['headers']

    sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')

    # Extract body (may be plain text or HTML)
    parts = msg['payload'].get('parts', [])
    body = ''
    if parts:
        for part in parts:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break
            elif part['mimeType'] == 'text/html':
                data = part['body'].get('data')
                if data:
                    html = base64.urlsafe_b64decode(data).decode('utf-8')
                    soup = BeautifulSoup(html, 'html.parser')
                    body = soup.get_text()
                    break
    else:
        data = msg['payload']['body'].get('data')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8')

    # Clean body
    body = body.strip().replace('\r', '').replace('\n', ' ')
    return sender, subject, body[:1000]  # limit to 1000 chars

def analyze_emails_with_ai(emails):
    """
    Returns:
    {
      "overall_summary": "...",
      "priorities": [
          {"subject": "...", "priority": "High"},
          ...
      ]
    }
    """

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

    # Convert string → dict
    try:
        return json.loads(raw_output)
    except:
        # fallback → wrap output
        return {"overall_summary": raw_output, "priorities": []}

def summarize_email(subject, body):
    """Simple rule-based summarizer."""
    # Naive summary: first sentence or first 20 words
    text = body.split('.')
    summary = text[0][:200] if text else body[:200]
    if len(summary.split()) > 25:
        summary = ' '.join(summary.split()[:25]) + '...'
    return summary


def main():
    print("🔑 Authenticating...")
    service = authenticate_gmail()

    print("📬 Fetching last 24h emails...")
    messages = get_last_24h_emails(service)

    if not messages:
        print("No new emails in last 24 hours.")
        return

    print("\n📄 Daily Email Summary (Last 24 Hours)\n" + "="*45)
    emails = []
    for i, msg in enumerate(messages[:15], 1):
        sender, subject, body = get_email_details(service, msg['id'])
        summary = summarize_email(subject, body)
        emails.append({"from": sender, "subject": subject, "snippet": summary})
        print(f"\n{i}. 📨 From: {sender}\n   Subject: {subject}\n   Summary: {summary}\n")
    ai_summary = analyze_emails_with_ai(emails)
    print("\n🤖 AI Analysis:\n" + "="*45)
    print(ai_summary)

if __name__ == '__main__':
    main()
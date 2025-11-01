# email_summarizer.py
import ssl
import requests
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
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    """Authenticate and return Gmail API service."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no valid credentials, ask user to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)
    return service


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
    """Summarize all emails and classify by priority."""
    all_text = ""
    for e in emails:
        all_text += f"From: {e['from']}\nSubject: {e['subject']}\nSummary: {e['snippet']}\n\n"

    prompt = f"""
    You are an AI email assistant.
    Given the following emails from the last 24 hours, create:
    1. An overall summary of what these emails are about.
    2. For each email, assign a priority: High, Medium, or Low — based on its importance to a working student (like job opportunities, project deadlines, important updates are High).
    
    Emails:
    {all_text}

    Output your result in this format:
    Overall Summary:
    [summary text]

    Priorities:
    1. [Subject] - [Priority]
    2. [Subject] - [Priority]
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # fast and cheap
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content

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

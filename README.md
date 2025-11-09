# 📧 mAiL – AI-Powered Email Summarizer (Backend)
This is the **backend** of *mAiL*, an AI-powered Email Summarizer system built with **FastAPI** and integrated with **Gmail API + AI summarization**.  
It fetches recent emails from a user’s Gmail account, summarizes them intelligently, assigns priority, and allows user feedback storage.

---

## 🚀 Features

- 🔐 **Google OAuth 2.0 Login** (via Gmail API)
- 📥 **Fetch latest 24h Gmail messages**
- 🧠 **AI-generated summaries** for each email
- 🎯 **Priority classification** (High / Medium / Low)
- 💾 **Feedback collection system** (stored in SQLite)
- 📊 **Feedback stats API** (accuracy + classification report)
- 👥 **Multi-user support** – tokens are saved per user

---

## 🧱 Project Structure
backend/
├── server.py # Main FastAPI backend server
├── database.py # SQLite feedback handling
├── email_summarizer/
│ ├── email_summarizer.py # Gmail API + AI logic
├── feedback.db # Local database
├── credentials.json # Google OAuth credentials
├── tokens/ # Stores user access tokens
└── requirements.txt # Python dependencies

---

## ⚙️ Setup Instructions
### 1️⃣ Clone the Repository
```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd mAiL/backend

2️⃣ Create a Virtual Environment
python -m venv venv
venv\Scripts\activate    # (Windows)
# OR
source venv/bin/activate # (Mac/Linux)

3️⃣ Install Dependencies
pip install -r requirements.txt

4️⃣ Run the Backend
uvicorn server:app --reload


The API will start at:
👉 http://127.0.0.1:8000/docs


🔑 Google OAuth Setup
1.Go to Google Cloud Console
2.Enable Gmail API.
3.Create OAuth Client ID (Web).
4.Add these redirect URIs: http://localhost:8000/auth/callback
5.Download credentials.json and place it in the backend/ folder.


🧩 API Endpoints
Endpoint	          Method	                Description
/login-url	           GET	                 Returns Google login URL
/auth/callback	       GET	                 Handles OAuth callback
/fetch-emails	       GET	                 Fetches + summarizes Gmail emails
/feedback	          POST	                 Saves feedback from frontend
/feedback	          GET	                 Lists all feedback
/feedback-stats	      GET	                 Shows accuracy + feedback summary


🧠 Future Plans
Integrate AI summarization directly via Gemini / OpenAI API
Add frontend connection (React)
Deploy backend (Render / Railway)


👨‍💻 Author
Rushikesh Shinde
📍VIT Pune | B.Tech CSE
💡 Passionate about AI, automation, and smart systems.

👨‍💻 Collaborator
Guruprasad Melinkeri
📍VIT Pune | B.Tech CSE
💡Building backends and ML Magic. 

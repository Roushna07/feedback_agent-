# 🩺 Rural Healthcare Multilingual AI Feedback Agent

An AI-powered voice-first healthcare feedback collection system built for rural patients and healthcare camp administrators, supporting **Hindi (हिंदी)** and **Telugu (తెలుగు)**.

---

## 🌟 Key Features

1. **Fully Automated Voice Interview Bot:**
   - Guided spoken interview: staff clicks "Start Bot"; the user taps **Stop Recording** after each answer.
   - Browser Web Speech API (`SpeechSynthesis`) speaks each question in natural Hindi (`hi-IN`) or Telugu (`te-IN`).
   - Web Audio API real-time microphone recording starts automatically once question speech completes.
   - Recording continues until **Stop Recording** is tapped; there is no duration limit or silence-based auto-stop.
   - Deterministic rating extraction for Hindi, Telugu, and English.
   - In-memory mono WAV audio is resampled to 16kHz for transcription; raw audio is never stored on disk.
   - Staff control toolbar: Pause, Resume, Repeat Question, Toggle Manual Correction, End Interview.
2. **English Feedback Storage:**
   - Staff can review and correct each Hindi/Telugu transcript before saving.
   - Answers are translated locally to English before database persistence; source-language answer text is not stored for new submissions.
   - The database records the English answer, source language, and translation status.
   - English answers appear in the administrative dashboard and CSV export.
3. **Local Speech-to-Text:**
   - Runs the multilingual Faster-Whisper `small` model on the local CPU by default; patient audio is not sent to Cloudflare.
   - The model is downloaded once on first use and cached locally.
   - Review and correct recognized text before the English answer is saved.
4. **Structured & Secure Storage:**
   - Local SQLite database (`healthcare_feedback.db`).
   - Anonymous patient identification (`PAT-YYMMDD-XXXXXX`).
   - Full question, response, rating, and timestamp persistence.
5. **Administrative Analytics Dashboard:**
   - Real-time KPIs: total submissions, completion rates, language distribution, average satisfaction rating.
   - Interactive Plotly visualizations for question breakdown, ratings, and language trends.
   - Drill-down session inspector to review all 5 answers of any patient.
   - CSV export of all feedback data.
   - AI-powered feedback analysis and complaint identification (`@cf/zai-org/glm-4.7-flash`).

---

## 🏗️ Architecture

```text
                 PATIENT
                    │
                    ▼
          STREAMLIT APPLICATION
                    │
                    ▼
          LANGUAGE SELECTION
                    │
              Hindi / Telugu
                    │
                    ▼
          AI FEEDBACK AGENT
                    │
                    ▼
       ASK QUESTION (1 to 5)
                    │
                    ▼
           RECORD PATIENT AUDIO
                    │
                    ▼
          LOCAL WHISPER (CPU)
                    │
                    ▼
             SPEECH-TO-TEXT
                    │
                    ▼
         DISPLAY TRANSCRIPTION
                    │
                    ▼
          PATIENT CONFIRMATION
                    │
                    ▼
           SAVE RESPONSE TO DB
                    │
                    ▼
              SQLITE DB
                    │
                    ▼
           ADMIN DASHBOARD
                    │
                    ▼
          FEEDBACK EVALUATION
```

---

## 📁 Project Structure

```text
feedbacksystem/
├── app.py                      # Main Streamlit application
├── requirements.txt            # Python dependencies
├── .env                        # Local environment secrets
├── .env.example                # Example environment template
├── .gitignore                  # Git exclusions
├── plan.md                     # Complete project design blueprint
├── test_system.py              # Automated system test suite
│
├── agent/                      # Conversational agent modules
│   ├── __init__.py
│   ├── conversation.py         # Conversational flow & automated bot loop
│   ├── questions.py            # Multilingual questions and strings
│   ├── rating_extractor.py     # Deterministic rating extractor (HI, TE, EN)
│   ├── state_manager.py        # Streamlit session state management
│   ├── voice_bot.py            # Streamlit custom component wrapper
│   └── voice_bot_component/    # Browser Web Speech & Web Audio recording controls
│       └── index.html
│
├── services/                   # AI & Backend services
│   ├── __init__.py
│   ├── cloudflare_ai.py        # Optional Cloudflare text analysis client
│   ├── local_transcription.py  # Local CPU Whisper engine
│   ├── transcription.py        # Local audio validation & transcription API
│   ├── translation.py          # Offline local bilingual translation engine (HI, TE -> EN)
│   └── feedback_analysis.py    # Analytical summarization & reporting
│
├── database/                   # SQLite database operations
│   ├── __init__.py
│   ├── db.py                   # DB connection & table initialization
│   ├── models.py               # Data models
│   └── repository.py           # CRUD operations & analytics queries
│
├── admin/                      # Healthcare admin dashboard
│   ├── __init__.py
│   └── dashboard.py            # Analytics charts, drill-downs & CSV export
│
└── data/
    └── healthcare_feedback.db  # SQLite persistent storage
```

---

## 🚀 Quickstart Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env`:
```env
DATABASE_PATH=data/healthcare_feedback.db
LOCAL_STT_MODEL=small
ADMIN_PASSWORD=admin123
```
The first recording downloads the selected Whisper model once. The default `small`
model is more accurate than `base` but uses more CPU and memory; set it to `base`
on lower-resource computers. Speech is transcribed locally; answers are reviewed,
translated to English, and only the English text is saved. Raw audio stays in memory
and is discarded. Cloudflare credentials are optional and used only for optional
text analysis.

### 3. Run Automated Tests
```bash
python test_system.py
```
The test script uses a temporary SQLite database and does not add sample records
to the application's database. Translation checks are skipped with a clear
message if the optional NLLB model weights are not installed.

### 4. Launch the Application
```bash
python -m streamlit run app.py
```
On the computer running the app, open `http://localhost:8501`. To use it on a
phone, connect it to the same Wi-Fi network. The Network URL shown in the
Streamlit terminal is plain HTTP; mobile browsers block microphone access over
HTTP. A trusted HTTPS certificate and a hostname that resolves to the computer
on the local network are required.

For local HTTPS, obtain a certificate trusted by the phone, with the local
hostname in its subject alternative names, and configure Streamlit's certificate
and key paths in `.streamlit/config.toml`:

```toml
[server]
sslCertFile = "C:/path/to/fullchain.pem"
sslKeyFile = "C:/path/to/private-key.pem"
```

Keep the private key out of Git. Restart Streamlit and open
`https://<your-local-hostname>:8501` on the phone. The phone must resolve that
hostname to the computer and trust the certificate issuer; a self-signed
certificate won't work unless its issuer is trusted on the phone. The app
remains available only to devices that can reach the computer on the local
network.

Feedback is stored in the local SQLite file at `DATABASE_PATH` (by default,
`data/healthcare_feedback.db`). Voice transcription runs locally; raw audio is
discarded after transcription, while the transcript is saved locally.
Supabase PostgreSQL is used only when `DB_BACKEND=postgres` is explicitly set.

---

## 🧪 5 Healthcare Camp Feedback Questions

| # | Topic | English | Hindi | Telugu | Interaction Type |
|---|---|---|---|---|---|
| 1 | Patient Name & Village | What is your name and which village are you from? | आपका नाम क्या है और आप किस गाँव से आए हैं? | మీ పేరు ఏమిటి మరియు మీరు ఏ గ్రామం నుండి వచ్చారు? | Spoken Voice / Text |
| 2 | Health Problems | What health problems or symptoms do you have? | आपको क्या स्वास्थ्य समस्या या बीमारी है? | మీకు ఎలాంటి ఆరోగ్య సమస్యలు లేదా అనారోగ్య లక్షణాలు ఉన్నాయి? | Spoken Voice / Text |
| 3 | Health Assistant Service | How was the service given by the health assistant? | स्वास्थ्य सहायक (हेल्थ असिस्टेंट) द्वारा दी गई सेवा कैसी थी? | హెల్త్ అసిస్టెంట్ అందించిన సేవ ఎలా ఉంది? | 1–5 Star Rating + Spoken Voice |
| 4 | Treatment Explanation | Did the healthcare worker explain your treatment clearly? | क्या स्वास्थ्यकर्मी ने आपको इलाज अच्छी तरह समझाया? | ఆరోగ్య సిబ్బంది మీ చికిత్స గురించి స్పష్టంగా వివరించారా? | Quick Yes / No / Not sure + Voice |
| 5 | Camp Improvements | What suggestions would you like to give for camp improvements? | स्वास्थ्य शिविर (कैंप) में सुधार के लिए आप क्या सुझाव देना चाहेंगे? | ఆరోగ్య శిబిరంలో (క్యాంప్) మెరుగుదలల కోసం మీరు ఎలాంటి సలహాలు ఇవ్వాలనుకుంటున్నారు? | Spoken Voice / Text |

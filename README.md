# 🩺 Rural Healthcare Multilingual AI Feedback Agent

An AI-powered voice-first healthcare feedback collection system built for rural patients and healthcare camp administrators, supporting **Hindi (हिंदी)** and **Telugu (తెలుగు)**.

---

## 🌟 Key Features

1. **Fully Automated Voice Interview Bot:**
   - Hands-free spoken interview: staff clicks "Start Bot", and the bot conducts the entire 5-question interview.
   - Browser Web Speech API (`SpeechSynthesis`) speaks each question in natural Hindi (`hi-IN`) or Telugu (`te-IN`).
   - Web Audio API real-time microphone recording starts automatically once question speech completes.
   - Automatic silence detection stops recording after 10 seconds of consecutive silence, or at a 20-second cap.
   - Deterministic rating extraction for Hindi, Telugu, and English.
   - In-memory 16kHz mono WAV encoding with zero persistent raw audio files on disk (patient privacy preserved).
   - Staff control toolbar: Pause, Resume, Repeat Question, Toggle Manual Correction, End Interview.
2. **Bilingual Feedback Storage (Original Language + English):**
   - Stores every patient answer in both its original language (Hindi/Telugu) and English.
   - Offline CPU-only translation engine preserving clinical meaning, symptoms, and complaints.
   - Idempotent schema migration: `english_translation`, `translation_status`, `translation_engine`, `source_language`.
   - Side-by-side bilingual view in the administrative dashboard and bilingual CSV export.
3. **Cloudflare Workers AI Speech-to-Text:**
   - Integrates with `@cf/openai/whisper-large-v3-turbo` for multilingual transcription.
   - Live transcription confirmation and optional manual text editing before submitting.
3. **Structured & Secure Storage:**
   - Local SQLite database (`healthcare_feedback.db`).
   - Anonymous patient identification (`PAT-YYMMDD-XXXXXX`).
   - Full question, response, rating, and timestamp persistence.
4. **Administrative Analytics Dashboard:**
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
        CLOUDFLARE WORKERS AI
                    │
                    ▼
              WHISPER MODEL
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
│   └── voice_bot_component/    # Browser Web Speech & Web Audio silence detection
│       └── index.html
│
├── services/                   # AI & Backend services
│   ├── __init__.py
│   ├── cloudflare_ai.py        # Cloudflare REST API client
│   ├── transcription.py        # STT pipeline & fallback handling
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

### 2. Configure Environment (Optional for Live Cloudflare Inference)
Copy `.env.example` to `.env`:
```env
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_api_token
CLOUDFLARE_STT_MODEL=@cf/openai/whisper-large-v3-turbo
CLOUDFLARE_TEXT_MODEL=@cf/zai-org/glm-4.7-flash
DATABASE_PATH=data/healthcare_feedback.db
ADMIN_PASSWORD=admin123
```
*(Note: If credentials are not set, the system runs automatically in **Preview Mode** with simulated Hindi/Telugu transcriptions so you can test end-to-end functionality right away).*

### 3. Run Automated Tests
```bash
python test_system.py
```

### 4. Launch the Application
```bash
python -m streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## 🧪 5 Healthcare Camp Feedback Questions

| # | Topic | English | Hindi | Telugu | Interaction Type |
|---|---|---|---|---|---|
| 1 | Patient Name & Village | What is your name and which village are you from? | आपका नाम क्या है और आप किस गाँव से आए हैं? | మీ పేరు ఏమిటి మరియు మీరు ఏ గ్రామం నుండి వచ్చారు? | Spoken Voice / Text |
| 2 | Health Problems | What health problems or symptoms do you have? | आपको क्या स्वास्थ्य समस्या या बीमारी है? | మీకు ఎలాంటి ఆరోగ్య సమస్యలు లేదా అనారోగ్య లక్షణాలు ఉన్నాయి? | Spoken Voice / Text |
| 3 | Health Assistant Service | How was the service given by the health assistant? | स्वास्थ्य सहायक (हेल्थ असिस्टेंट) द्वारा दी गई सेवा कैसी थी? | హెల్త్ అసిస్టెంట్ అందించిన సేవ ఎలా ఉంది? | 1–5 Star Rating + Spoken Voice |
| 4 | Treatment Explanation | Did the healthcare worker explain your treatment clearly? | क्या स्वास्थ्यकर्मी ने आपको इलाज अच्छी तरह समझाया? | ఆరోగ్య సిబ్బంది మీ చికిత్స గురించి స్పష్టంగా వివరించారా? | Quick Yes / No / Not sure + Voice |
| 5 | Camp Improvements | What suggestions would you like to give for camp improvements? | स्वास्थ्य शिविर (कैंप) में सुधार के लिए आप क्या सुझाव देना चाहेंगे? | ఆరోగ్య శిబిరంలో (క్యాంప్) మెరుగుదలల కోసం మీరు ఎలాంటి సలహాలు ఇవ్వాలనుకుంటున్నారు? | Spoken Voice / Text |

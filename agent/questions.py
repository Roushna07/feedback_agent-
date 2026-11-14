"""
Healthcare feedback questions and multilingual UI strings.
Supports Hindi (hi), Telugu (te), and English (en) with bilingual English annotations throughout.
Updated 5 Specific Health Camp Evaluation Questions.
"""

UI_STRINGS = {
    "hi": {
        "title": "ग्रामीण स्वास्थ्य सेवा प्रतिक्रिया प्रणाली (Rural Healthcare AI Feedback System)",
        "subtitle": "आपकी प्रतिक्रिया से हमारी स्वास्थ्य सेवाएँ और बेहतर बन सकती हैं। (Your feedback helps us continuously improve community healthcare services.)",
        "welcome": "नमस्ते! आपके स्वास्थ्य शिविर (कैंप) के अनुभव के बारे में हम 5 छोटे सवाल पूछना चाहते हैं। इसमें लगभग 2 मिनट लगेंगे। क्या आप अपनी प्रतिक्रिया देना चाहेंगे?\n\n*(Welcome! We would like to ask you 5 quick questions regarding your health camp experience. It takes about 2 minutes. Would you like to share your feedback?)*",
        "consent_question": "क्या आप अपनी आवाज़ रिकॉर्ड करके प्रतिक्रिया देने के लिए सहमत हैं? (Do you consent to voice recording to provide feedback?)",
        "consent_yes": "हाँ, मैं सहमत हूँ (Yes, I Agree — Start Feedback)",
        "consent_no": "नहीं (No / Decline)",
        "consent_required": "आगे बढ़ने के लिए कृपया सहमति दें। (Please provide your consent to continue.)",
        "question_progress": "सवाल {current} का {total} (Question {current} of {total})",
        "record_instruction": "माइक दबाकर बोलें या नीचे टेक्स्ट में टाइप करें (Press mic button to speak, or type below):",
        "transcription_heading": "आपकी बात का अनुवाद / प्रतिलेखन (Transcribed Spoken Words):",
        "confirm_btn": "यह सही है (Confirm & Next) ->",
        "retry_btn": "फिर से रिकॉर्ड करें (Re-record)",
        "manual_edit_hint": "यदि कोई शब्द गलत है, तो आप इसे यहाँ सुधार सकते हैं (You can review or edit the text manually):",
        "thank_you_title": "धन्यवाद! (Thank You!)",
        "thank_you_msg": "आपने अपना महत्वपूर्ण सुझाव साझा किया। आपकी प्रतिक्रिया हमारी स्वास्थ्य सेवाओं को बेहतर बनाने में मदद करेगी।\n\n*(Thank you for sharing your valuable feedback. Your input helps us continuously improve healthcare services.)*",
        "new_session_btn": "नयी प्रतिक्रिया दर्ज करें (Submit Another Feedback)",
        "yes": "हाँ (Yes)",
        "no": "नहीं (No)",
        "not_sure": "निश्चित नहीं (Not sure)",
        "rating_label": "सेवा रेटिंग (Service Rating: 1 = Very Poor / बहुत खराब, 5 = Excellent / उत्कृष्ट)",
        "optional_explanation": "अतिरिक्त विवरण या कारण (Additional details or comments):",
        "voice_input": "आवाज़ रिकॉर्ड करें (Voice Recording)",
        "text_input_fallback": "या टेक्स्ट में लिखें (Or Type Manually)",
        "processing_audio": "आवाज़ को प्रोसेस किया जा रहा है... (Transcribing audio...)",
        "audio_error": "ऑडियो रिकॉर्ड नहीं हो सका या खाली है। कृपया फिर से प्रयास करें। (Could not record audio or audio is empty. Please try again.)",
        "patient_code_label": "रोगी पहचान कोड (Patient Anonymous Code)"
    },
    "te": {
        "title": "గ్రామీణ ఆరోగ్య సంరక్షణ అభిప్రాయ సేకరణ (Rural Healthcare AI Feedback System)",
        "subtitle": "మీ విలువైన అభిప్రాయం మా ఆరోగ్య సేవలను మెరుగుపరచడంలో సహాయపడుతుంది. (Your feedback helps us continuously improve community healthcare services.)",
        "welcome": "నమస్కారం! మీ ఆరోగ్య శిబిరం (క్యాంప్) అనుభవం గురించి 5 చిన్న ప్రశ్నలు అడగాలనుకుంటున్నాము. దీనికి సుమారు 2 నిమిషాలు పడుతుంది. మీరు మీ అభిప్రాయాన్ని తెలియజేయాలనుకుంటున్నారా?\n\n*(Welcome! We would like to ask you 5 quick questions regarding your health camp experience. It takes about 2 minutes. Would you like to share your feedback?)*",
        "consent_question": "మీరు మీ స్వరాన్ని రికార్డ్ చేయడం ద్వారా అభిప్రాయాన్ని అందించడానికి అంగీకరిస్తున్నారా? (Do you consent to voice recording to provide feedback?)",
        "consent_yes": "అవును, నేను అంగీకరిస్తున్నాను (Yes, I Agree — Start Feedback)",
        "consent_no": "వద్దు (No / Decline)",
        "consent_required": "ముందుకు సాగడానికి దయచేసి సమ్మతి తెలపండి. (Please provide your consent to continue.)",
        "question_progress": "ప్రశ్న {current} / {total} (Question {current} of {total})",
        "record_instruction": "మైక్ బటన్ నొక్కి మాట్లాడండి లేదా కింద టైప్ చేయండి (Press mic button to speak, or type below):",
        "transcription_heading": "మీరు మాట్లాడిన మాటలు (Transcribed Spoken Words):",
        "confirm_btn": "ఇది సరైనదే (Confirm & Next) ->",
        "retry_btn": "మళ్ళీ రికార్డ్ చేయండి (Re-record)",
        "manual_edit_hint": "ఏదైనా తప్పుగా ఉంటే ఇక్కడ సరిదిద్దుకోవచ్చు (You can review or edit the text manually):",
        "thank_you_title": "ధన్యవాదాలు! (Thank You!)",
        "thank_you_msg": "మీ విలువైన అభిప్రాయాన్ని పంచుకున్నందుకు కృతజ్ఞతలు. మీ అభిప్రాయం మా ఆరోగ్య సేవలను మెరుగుపరచడంలో సహాయపడుతుంది.\n\n*(Thank you for sharing your valuable feedback. Your input helps us improve healthcare services for everyone.)*",
        "new_session_btn": "కొత్త అభిప్రాయాన్ని ప్రారంభించండి (Submit Another Feedback)",
        "yes": "అవును (Yes)",
        "no": "కాదు (No)",
        "not_sure": "ఖచ్చితంగా తెలియదు (Not sure)",
        "rating_label": "సేవ రేటింగ్ (Service Rating: 1 = చాలా అసంతృప్తి / Very Poor, 5 = చాలా సంతృప్తి / Excellent)",
        "optional_explanation": "అదనపు వివరణ లేదా సలహా (Additional details or comments):",
        "voice_input": "స్వర రికార్డింగ్ (Voice Recording)",
        "text_input_fallback": "లేదా టైప్ చేయండి (Or Type Manually)",
        "processing_audio": "స్వరాన్ని మార్పిడి చేస్తోంది... (Transcribing audio...)",
        "audio_error": "ఆడియో రికార్డ్ కాలేదు లేదా ఖాళీగా ఉంది. దయచేసి మళ్ళీ ప్రయత్నించండి. (Could not record audio or audio is empty. Please try again.)",
        "patient_code_label": "రోగి గుర్తింపు సంఖ్య (Patient Anonymous Code)"
    },
    "en": {
        "title": "Rural Healthcare Multilingual AI Feedback Agent",
        "subtitle": "Your feedback helps us continuously improve community healthcare services.",
        "welcome": "Welcome! We would like to ask you 5 quick questions regarding your health camp experience. It takes only 2 minutes. Would you like to share your feedback?",
        "consent_question": "Do you consent to voice recording to provide your feedback?",
        "consent_yes": "Yes, I Agree (Start Feedback)",
        "consent_no": "No / Decline",
        "consent_required": "Please provide your consent to continue.",
        "question_progress": "Question {current} of {total}",
        "record_instruction": "Press the microphone button and speak, or enter text below:",
        "transcription_heading": "Transcribed Response:",
        "confirm_btn": "Confirm & Next ->",
        "retry_btn": "Re-record",
        "manual_edit_hint": "You can review or correct the text before submitting:",
        "thank_you_title": "Thank You!",
        "thank_you_msg": "Thank you for sharing your valuable feedback. Your input helps us improve healthcare services for everyone.",
        "new_session_btn": "Submit Another Feedback",
        "yes": "Yes",
        "no": "No",
        "not_sure": "Not sure",
        "rating_label": "Service Rating (1 = Very Poor, 5 = Excellent)",
        "optional_explanation": "Additional details or comments (spoken or typed):",
        "voice_input": "Voice Recording",
        "text_input_fallback": "Or Type Manually",
        "processing_audio": "Transcribing audio...",
        "audio_error": "Could not record audio or audio is empty. Please try again.",
        "patient_code_label": "Patient Anonymous Code"
    }
}

QUESTIONS_DATA = [
    {
        "number": 1,
        "key": "patient_name_and_village",
        "type": "open_response",
        "en": "What is your name and which village are you from?",
        "hi": "आपका नाम क्या है और आप किस गाँव से आए हैं?",
        "te": "మీ పేరు ఏమిటి మరియు మీరు ఏ గ్రామం నుండి వచ్చారు?"
    },
    {
        "number": 2,
        "key": "health_problems",
        "type": "open_response",
        "en": "What health problems or symptoms do you have?",
        "hi": "आपको क्या स्वास्थ्य समस्या या बीमारी है?",
        "te": "మీకు ఎలాంటి ఆరోగ్య సమస్యలు లేదా అనారోగ్య లక్షణాలు ఉన్నాయి?"
    },
    {
        "number": 3,
        "key": "health_assistant_service",
        "type": "rating_and_comment",
        "en": "How was the service given by the health assistant?",
        "hi": "स्वास्थ्य सहायक (हेल्थ असिस्टेंट) द्वारा दी गई सेवा कैसी थी?",
        "te": "హెల్త్ అసిస్టెంట్ అందించిన సేవ ఎలా ఉంది?"
    },
    {
        "number": 4,
        "key": "treatment_explanation",
        "type": "boolean_choice",
        "en": "Did the healthcare worker explain your treatment clearly?",
        "hi": "क्या स्वास्थ्यकर्मी ने आपको इलाज अच्छी तरह समझाया?",
        "te": "ఆరోగ్య సిబ్బంది మీ చికిత్స గురించి స్పష్టంగా వివరించారా?"
    },
    {
        "number": 5,
        "key": "camp_improvement_suggestions",
        "type": "open_response",
        "en": "What suggestions would you like to give for camp improvements?",
        "hi": "स्वास्थ्य शिविर (कैंप) में सुधार के लिए आप क्या सुझाव देना चाहेंगे?",
        "te": "ఆరోగ్య శిబిరంలో (క్యాంప్) మెరుగుదలల కోసం మీరు ఎలాంటి సలహాలు ఇవ్వాలనుకుంటున్నారు?"
    }
]

def get_question(question_number: int, language: str = "hi") -> dict:
    for q in QUESTIONS_DATA:
        if q["number"] == question_number:
            return {
                "number": q["number"],
                "key": q["key"],
                "type": q["type"],
                "text": q.get(language, q["hi"]),
                "en_text": q["en"]
            }
    return {}

def get_total_questions() -> int:
    return len(QUESTIONS_DATA)

def get_ui_string(key: str, language: str = "hi", **kwargs) -> str:
    lang_dict = UI_STRINGS.get(language, UI_STRINGS["hi"])
    template = lang_dict.get(key, UI_STRINGS["en"].get(key, key))
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template

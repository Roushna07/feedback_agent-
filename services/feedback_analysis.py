"""
Feedback analysis service.
Enforces Free-Tier-Only architecture:
- Core analytics, complaint identification, and issue breakdown run locally via Python & Pandas (Zero AI cost/neurons).
- Optional text intelligence uses Cloudflare Workers AI free allocation (@cf/zai-org/glm-4.7-flash).
- Guaranteed 100% operational reliability even when the text model is unconfigured or quota-exhausted.
Adapted for the 5 Camp Feedback Questions:
1. Patient Name & Village
2. Health Problems & Symptoms
3. Health Assistant Service Quality
4. Treatment Explanation Clarity
5. Camp Improvement Suggestions
"""
from typing import List, Dict, Any
from .cloudflare_ai import run_text_model, is_configured

def analyze_session_feedback(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Summarize a single patient's session.
    First attempts Cloudflare Workers AI (@cf/zai-org/glm-4.7-flash) if configured,
    and seamlessly falls back to Python rule-based evaluation on any failure or quota exhaustion.
    """
    answers = session_data.get("answers", [])
    if not answers:
        return {"summary": "No answers provided.", "sentiment": "Neutral", "is_ai": False}

    # 1. Rule-based baseline evaluation
    q3_rating = None
    q4_explained = True
    health_issue = ""
    patient_info = ""
    camp_suggestion = ""

    for a in answers:
        q_num = a.get("question_number")
        txt = (a.get("transcript") or "").strip()
        resp = a.get("response_type")

        if q_num == 1:
            patient_info = txt
        elif q_num == 2:
            health_issue = txt
        elif q_num == 3:
            q3_rating = a.get("rating")
        elif q_num == 4:
            if resp == "no":
                q4_explained = False
        elif q_num == 5:
            camp_suggestion = txt

    if (q3_rating and q3_rating <= 2) or not q4_explained:
        sentiment = "Service Attention Needed"
    elif q3_rating and q3_rating >= 4 and q4_explained:
        sentiment = "Highly Satisfied / Positive Experience"
    else:
        sentiment = "Satisfactory / Moderate"

    rule_summary = (
        f"Patient Feedback: {patient_info or 'Anonymous'}. "
        f"Symptoms reported: '{health_issue or 'None specified'}'. "
        f"Health Assistant Rating: {q3_rating or 'N/A'}/5 ⭐. "
        f"Treatment explained clearly: {'Yes' if q4_explained else 'No'}. "
        f"Camp Suggestion: '{camp_suggestion or 'No specific suggestions'}'."
    )

    # 2. Optional Workers AI text intelligence if configured
    if is_configured():
        transcripts = [f"Q{a['question_number']}: {a['transcript']} (Response: {a['response_type']}, Rating: {a.get('rating')})" for a in answers]
        full_context = "\n".join(transcripts)

        system_prompt = (
            "You are an objective rural healthcare evaluation assistant. Summarize the patient's camp feedback in 2 concise sentences. "
            "Include their village/symptoms, how they rated the health assistant, and their main improvement suggestion. "
            "Do NOT invent medical diagnoses. Base findings strictly on the patient's words."
        )
        prompt = f"Patient Feedback Context:\n{full_context}\n\nPlease provide a 2-sentence administrative evaluation summary:"

        ai_res = run_text_model(prompt, system_prompt=system_prompt)
        if ai_res["success"] and ai_res["response"]:
            return {
                "summary": ai_res["response"],
                "sentiment": sentiment,
                "is_ai": True,
                "model_used": "@cf/zai-org/glm-4.7-flash (Cloudflare Workers AI)"
            }
        else:
            err_msg = ai_res.get("error", "AI service unavailable")
            return {
                "summary": f"{rule_summary} (Note: Cloudflare Text AI could not be reached: {err_msg})",
                "sentiment": sentiment,
                "is_ai": False
            }

    return {
        "summary": rule_summary,
        "sentiment": sentiment,
        "is_ai": False
    }

def generate_admin_report_summary(all_answers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Synthesizes overall complaints and suggestions across patient submissions.
    Runs entirely locally using question mapping - zero API consumption.
    """
    if not all_answers:
        return {
            "issues_breakdown": {},
            "top_complaints": ["No responses submitted yet."],
            "recent_suggestions": ["Awaiting community feedback."],
            "reported_health_problems": []
        }

    issues_by_category = {
        "Unclear Treatment Explanation": 0,
        "Low Health Assistant Service Rating (<= 2)": 0,
        "Common Symptoms / Health Complaints Logged": 0
    }

    suggestions = []
    health_problems = []

    for ans in all_answers:
        q_num = ans.get("question_number")
        resp = ans.get("response_type")
        txt = (ans.get("transcript") or "").strip()
        rating = ans.get("rating")

        # Q2: Health Problems
        if q_num == 2 and txt and not txt.startswith("[SIMULATED PREVIEW") and not txt.startswith("[సిమ్యులేటెడ్"):
            issues_by_category["Common Symptoms / Health Complaints Logged"] += 1
            if txt not in health_problems:
                health_problems.append(txt)

        # Q3: Assistant Rating
        elif q_num == 3 and rating is not None and rating <= 2:
            issues_by_category["Low Health Assistant Service Rating (<= 2)"] += 1

        # Q4: Treatment explanation
        elif q_num == 4 and resp == "no":
            issues_by_category["Unclear Treatment Explanation"] += 1

        # Q5: Camp Improvement Suggestions
        elif q_num == 5 and txt and not txt.startswith("[SIMULATED PREVIEW") and not txt.startswith("[సిమ్యులేటెడ్"):
            suggestions.append(txt)

    sorted_issues = sorted(issues_by_category.items(), key=lambda x: x[1], reverse=True)
    top_complaints = [f"{cat}: {cnt} reported concern(s)" for cat, cnt in sorted_issues if cnt > 0]
    if not top_complaints:
        top_complaints = ["No recurring service complaints recorded."]

    return {
        "issues_breakdown": issues_by_category,
        "top_complaints": top_complaints,
        "recent_suggestions": suggestions[-6:] if suggestions else ["No specific camp suggestions recorded yet."],
        "reported_health_problems": health_problems[-6:] if health_problems else ["No specific health problems logged yet."]
    }

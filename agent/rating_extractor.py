"""
Deterministic Rating Extractor for Patient Feedback.
Extracts 1 to 5 numerical ratings from Hindi, Telugu, and English spoken or typed transcripts.
Handles Unicode boundary semantics for Devanagari and Telugu scripts accurately.
"""
import re
from typing import Optional, Tuple

RATING_TOKENS = {
    5: {
        "numbers": ["5", "5/5", "5 स्टार", "5 star", "5 stars", "5 స్టార్", "5 నక్షత్రాలు"],
        "hi": ["पांच", "पाँच", "फाइव", "उत्कृष्ट", "बहुत अच्छा", "बहुत बढ़िया", "शानदार", "सुपर", "बेहतरीन"],
        "te": ["ఐదు", "ఫైవ్", "చాలా బాగుంది", "అద్భుతం", "చాలా మంచిది", "ఉత్తమం"],
        "en": ["five", "excellent", "very good", "great", "outstanding", "superb"]
    },
    4: {
        "numbers": ["4", "4/5", "4 स्टार", "4 star", "4 stars", "4 స్టార్", "4 నక్షత్రాలు"],
        "hi": ["चार", "फोर", "अच्छा", "बढ़िया", "ठीक-ठाक अच्छा"],
        "te": ["నాలుగు", "ఫోర్", "బాగుంది", "మంచిది"],
        "en": ["four", "good", "satisfactory"]
    },
    3: {
        "numbers": ["3", "3/5", "3 स्टार", "3 star", "3 stars", "3 స్టార్"],
        "hi": ["तीन", "थ्री", "सामान्य", "औसत", "कामचलाऊ", "ठीक-ठाक", "मध्यम"],
        "te": ["మూడు", "త్రీ", "సగటు", "పర్వాలేదు", "మధ్యస్థం"],
        "en": ["three", "average", "moderate", "neutral", "so so", "okay"]
    },
    2: {
        "numbers": ["2", "2/5", "2 स्टार", "2 star", "2 stars", "2 స్టార్"],
        "hi": ["दो", "टू", "खराब", "कम अच्छा", "असंतोषजनक"],
        "te": ["రెండు", "టూ", "బాగాలేదు", "సంతృప్తి లేదు"],
        "en": ["two", "poor", "bad", "unsatisfactory"]
    },
    1: {
        "numbers": ["1", "1/5", "1 स्टार", "1 star", "1 stars", "1 స్టార్"],
        "hi": ["एक", "वन", "बहुत खराब", "बेहद खराब", "बिलकुल अच्छा नहीं", "घटिया"],
        "te": ["ఒకటి", "వన్", "చాలా బాగాలేదు", "అసలు బాగాలేదు"],
        "en": ["one", "very poor", "terrible", "horrible", "awful"]
    }
}

def contains_token(text: str, token: str) -> bool:
    """Check if token exists as an isolated token in Unicode text."""
    if token.isascii() and token.isalnum():
        return bool(re.search(r"\b" + re.escape(token) + r"\b", text, re.IGNORECASE))
    pattern = r"(?:^|[\s,.\-!?;:()]|\b)" + re.escape(token) + r"(?:$|[\s,.\-!?;:()]|\b)"
    return bool(re.search(pattern, text, re.IGNORECASE))

def extract_rating(transcript: str, language: str = "hi") -> Tuple[Optional[int], str]:
    """
    Deterministically scan the transcript for rating expressions.
    Returns:
      (rating: Optional[int], match_source: str)
      match_source is 'explicit_scale', 'number_token', 'word_match', or 'none'.
    """
    if not transcript or not transcript.strip():
        return None, "none"

    text = transcript.lower().strip()

    # 1. Explicit scale mentions: "4 out of 5", "5 में से 4", "4/5", etc.
    out_of_five = re.search(r"(\d)\s*(?:/|out of|में से|లో|నుండి)\s*5", text, re.IGNORECASE)
    if out_of_five:
        val = int(out_of_five.group(1))
        if 1 <= val <= 5:
            return val, "explicit_scale"

    # 2. Number expressions (from 5 down to 1)
    for rating in [5, 4, 3, 2, 1]:
        for token in RATING_TOKENS[rating]["numbers"]:
            if contains_token(text, token):
                return rating, "number_token"

    # 3. Language-specific word tokens (sorted by length descending so compound phrases like 'बहुत खराब' take precedence over 'खराब')
    lang_key = "hi" if language == "hi" else ("te" if language == "te" else "en")
    candidates = []
    for rating in [5, 4, 3, 2, 1]:
        for token in RATING_TOKENS[rating][lang_key]:
            candidates.append((token, rating))
        if lang_key != "en":
            for token in RATING_TOKENS[rating]["en"]:
                candidates.append((token, rating))

    # Longest match first prevents single sub-word false positives
    candidates.sort(key=lambda x: (len(x[0]), x[1]), reverse=True)

    for token, rating in candidates:
        if contains_token(text, token):
            return rating, "word_match"

    return None, "none"

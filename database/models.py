"""
Data models and dataclasses for feedback sessions and answers.
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class FeedbackSession:
    id: Optional[int]
    patient_code: str
    language: str
    consent_given: bool
    status: str  # 'in_progress', 'completed'
    created_at: datetime
    patient_name: Optional[str] = None
    village: Optional[str] = None
    completed_at: Optional[datetime] = None

@dataclass
class FeedbackAnswer:
    id: Optional[int]
    session_id: int
    question_number: int
    question_text: str
    transcript: str
    response_type: str  # 'open_response', 'rating', 'yes', 'no', 'not_sure'
    rating: Optional[int] = None
    english_translation: Optional[str] = None
    translation_status: str = "pending"  # 'translated', 'pending', 'failed', 'not_required'
    translation_engine: Optional[str] = None
    source_language: Optional[str] = None
    created_at: Optional[datetime] = None

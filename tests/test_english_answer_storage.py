from agent import conversation


def test_answer_is_translated_before_english_only_storage(monkeypatch):
    source_text = "मेरा नाम राधा है"
    english_text = "My name is Radha."
    saved = {}

    def fake_translate(text, source_language):
        assert text == source_text
        assert source_language == "hi"
        return {
            "success": True,
            "english_translation": english_text,
            "translation_status": "translated",
            "translation_engine": "test-engine",
        }

    monkeypatch.setattr(conversation, "translate_patient_transcript", fake_translate)
    monkeypatch.setattr(conversation, "save_feedback_answer", lambda **kwargs: saved.update(kwargs))

    result = conversation._translate_and_save_english_answer(
        session_id=1,
        question_number=1,
        question_text="What is your name?",
        answer_text=source_text,
        response_type="open_response",
        rating=None,
        source_language="hi",
    )

    assert result["success"] is True
    assert saved["transcript"] == english_text
    assert saved["english_translation"] == english_text
    assert saved["source_language"] == "hi"
    assert source_text not in saved.values()


def test_failed_translation_does_not_save_source_text(monkeypatch):
    saved = []

    monkeypatch.setattr(
        conversation,
        "translate_patient_transcript",
        lambda *_args, **_kwargs: {
            "success": False,
            "english_translation": "",
            "error": "Translation model unavailable.",
        },
    )
    monkeypatch.setattr(
        conversation,
        "save_feedback_answer",
        lambda **kwargs: saved.append(kwargs),
    )

    result = conversation._translate_and_save_english_answer(
        session_id=1,
        question_number=2,
        question_text="What symptoms do you have?",
        answer_text="मुझे बुखार है",
        response_type="open_response",
        rating=None,
        source_language="hi",
    )

    assert result == {
        "success": False,
        "error": "Translation model unavailable.",
    }
    assert saved == []

import pytest
from app import pronunciation_dictionary as dictionary
from app.nlp_engine import analyze_text, apply_pronunciation_choices

ENTRY={"word":"атлас","options":[{"id":"maps","display":"а́тлас","tts_text":"+атлас","meaning":"Сборник карт"},{"id":"fabric","display":"атла́с","tts_text":"атл+ас","meaning":"Ткань"}]}

def test_dictionary_crud_and_nlp_integration(tmp_path, monkeypatch):
    monkeypatch.setattr(dictionary,"PATH",tmp_path/"dictionary.json")
    clean=dictionary.validate_entry(ENTRY); dictionary.save_entries([clean])
    assert dictionary.load_entries()==[clean]
    ambiguity=analyze_text("атлас")["ambiguities"][0]
    assert ambiguity["word"]=="атлас"
    assert apply_pronunciation_choices("атлас",{"amb_0":"fabric"})["text_used"]=="атл+ас"
    dictionary.save_entries([]); assert dictionary.load_entries()==[]

@pytest.mark.parametrize("entry", [{}, {"word":"x","options":[]}, {"word":"атлас","options":[{"id":"a","display":"а","tts_text":"атлас","meaning":"x"},{"id":"a","display":"б","tts_text":"+атлас","meaning":"y"}]}])
def test_dictionary_rejects_invalid_entries(entry):
    with pytest.raises(ValueError): dictionary.validate_entry(entry)

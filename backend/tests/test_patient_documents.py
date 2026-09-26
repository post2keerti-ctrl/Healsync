from healsync_backend.patient_routes import _prescription_lines, _extract_prescription_text


def test_prescription_lines_extract_dosage_lines() -> None:
    text = "Take Amoxicillin 500mg twice daily\nRest and hydrate\nParacetamol 650 mg as needed"
    assert _prescription_lines(text) == [
        "Take Amoxicillin 500mg twice daily",
        "Paracetamol 650 mg as needed",
    ]


def test_text_document_extracts_readable_text() -> None:
    text, mode = _extract_prescription_text("prescription.txt", b"Amoxicillin 500mg")
    assert text == "Amoxicillin 500mg"
    assert mode == "text"


def test_prescription_suggestions_hide_common_printed_prefixes() -> None:
    text = "City Clinic, 42 North Road\nPrescription: Amoxicillin 500mg twice daily\nAddress: 8 West Street"
    assert _prescription_lines(text) == ["Amoxicillin 500mg twice daily"]
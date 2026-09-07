"""
NLP + Medical NER service — layers 7 & 8 of the architecture (spaCy + scispaCy).

Pipeline:
  1. Try to load a scispaCy clinical model (`en_core_sci_sm`) — trained
     specifically to recognize medical entities (drug names, dosages,
     conditions, procedures).
  2. If that model isn't installed (e.g. this sandbox has no route to
     scispaCy's S3 model host), fall back to general-purpose spaCy
     (`en_core_web_sm`) combined with a rule-based dosage/frequency
     matcher, so medicine extraction still works end-to-end.

To enable the real clinical model, run once:
    pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz
No code changes needed — `load_pipeline()` will pick it up automatically.
"""
import re
from functools import lru_cache
from typing import List, Dict

from .. import config

DOSAGE_RE = re.compile(r"\b\d+\s?(mg|mcg|ml|g|IU)\b", re.IGNORECASE)
FREQUENCY_RE = re.compile(
    r"\b(once|twice|1x|2x|3x|\d+\s?times?)\s?(a|per)?\s?(day|daily)\b|\b(daily|OD|BD|TDS|QID)\b",
    re.IGNORECASE,
)
DAYS_RE = re.compile(r"\bfor\s+(\d+)\s+days?\b", re.IGNORECASE)

# Small reference list so the rule-based fallback recognizes common drug names
# even without a clinical NER model. A real deployment relies on scispaCy's
# trained entity recognizer instead of this list.
KNOWN_DRUG_STEMS = [
    "amoxicillin", "ibuprofen", "paracetamol", "acetaminophen", "metformin",
    "amoxil", "azithromycin", "omeprazole", "aspirin", "cephalexin",
    "diclofenac", "tramadol", "ciprofloxacin", "warfarin", "insulin",
]


@lru_cache()
def load_pipeline():
    """Load the best available spaCy pipeline: scispaCy clinical model if present, else general spaCy."""
    import spacy

    try:
        nlp = spacy.load(config.SCISPACY_MODEL_NAME)
        mode = "scispacy-clinical"
    except OSError:
        try:
            nlp = spacy.load("en_core_web_sm")
            mode = "spacy-general+rules"
        except OSError:
            nlp = spacy.blank("en")
            mode = "blank+rules"
    return nlp, mode


def extract_medicines(text: str) -> List[Dict]:
    """
    Extract structured medicine entries {name, dosage, frequency, days} from
    free text (typically OCR output from a discharge summary).
    """
    nlp, mode = load_pipeline()
    doc = nlp(text)

    medicines = []
    seen = set()

    # scispaCy path: use its trained entity labels when available (CHEMICAL / DRUG-like ents)
    if mode == "scispacy-clinical":
        for ent in doc.ents:
            if ent.label_.upper() in {"CHEMICAL", "ENTITY"} and ent.text.lower() not in seen:
                seen.add(ent.text.lower())
                medicines.append(_build_entry(ent.text, text))

    # Rule-based fallback (also runs as a safety net even in clinical mode)
    for stem in KNOWN_DRUG_STEMS:
        if stem in text.lower() and stem not in seen:
            seen.add(stem)
            # find the original-cased span around the stem for a nicer display name
            match = re.search(re.escape(stem), text, re.IGNORECASE)
            span_text = text[match.start(): match.start() + 40] if match else stem
            medicines.append(_build_entry(span_text, text))

    return medicines


def _build_entry(name_fragment: str, full_text: str) -> Dict:
    dosage_match = DOSAGE_RE.search(name_fragment) or DOSAGE_RE.search(full_text)
    freq_match = FREQUENCY_RE.search(full_text)
    days_match = DAYS_RE.search(full_text)

    clean_name = re.split(r"\d", name_fragment)[0].strip().split("\n")[0].strip(" .,;:-")
    dosage = dosage_match.group(0) if dosage_match else ""

    return {
        "name": f"{clean_name} {dosage}".strip() if dosage else clean_name,
        "dosage": dosage or "as directed",
        "frequency": freq_match.group(0) if freq_match else "as directed",
        "days": int(days_match.group(1)) if days_match else 7,
    }


def pipeline_mode() -> str:
    """Report which NLP pipeline is actually active — useful for a status endpoint."""
    _, mode = load_pipeline()
    return mode

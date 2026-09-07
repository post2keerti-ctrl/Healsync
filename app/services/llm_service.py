"""
LLM service — layer 6 of the architecture (Llama 3).

Takes the structured medicines extracted by the NLP/NER stage and asks
Llama 3 to turn them into a day-by-day recovery plan (medicines, meals,
exercises), the same object the Patient app's Recovery Timeline renders.

Production: point LLAMA_BASE_URL at a self-hosted Ollama server (or any
OpenAI-compatible endpoint serving Llama 3) — e.g. run `ollama serve`
and `ollama pull llama3`, then set LLAMA_BASE_URL=http://localhost:11434.

Local/sandbox fallback: when no LLAMA_BASE_URL is reachable, a
deterministic template builder produces the same JSON shape so the
rest of the app (and your frontend) never has to know the difference.
"""
import json
from typing import Dict, List

import httpx

from .. import config

PROMPT_TEMPLATE = """You are a clinical recovery-planning assistant. Given this list of \
prescribed medicines (JSON), produce a 7-day post-surgical recovery plan as a JSON array. \
Each item must have: day (int), time ("H:MM AM/PM"), title (string), description (string), \
category (one of "medicine", "meal", "exercise", "checkup"). Include the medicine doses at \
sensible times, plus supportive meals and light mobility exercises that ramp up gradually. \
Respond with ONLY the JSON array, nothing else.

Medicines: {medicines}
"""


def generate_recovery_plan(medicines: List[Dict], recovery_day: int = 1) -> List[Dict]:
    if config.USE_REAL_LLM:
        try:
            return _call_llama(medicines)
        except Exception as exc:  # network/model errors -> fall back rather than break the request
            print(f"[llm_service] Llama call failed ({exc}); using template fallback.")

    return _template_plan(medicines, recovery_day)


def _call_llama(medicines: List[Dict]) -> List[Dict]:
    prompt = PROMPT_TEMPLATE.format(medicines=json.dumps(medicines))
    resp = httpx.post(
        f"{config.LLAMA_BASE_URL}/api/generate",
        json={"model": config.LLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=60,
    )
    resp.raise_for_status()
    raw = resp.json().get("response", "[]")
    return json.loads(raw)


def _template_plan(medicines: List[Dict], recovery_day: int) -> List[Dict]:
    """Deterministic stand-in used when Llama 3 isn't reachable."""
    plan = []
    med_times = ["8:00 AM", "1:00 PM", "6:00 PM", "9:00 PM"]
    for i, med in enumerate(medicines):
        plan.append({
            "day": recovery_day, "time": med_times[i % len(med_times)],
            "title": med["name"], "description": f"{med['dosage']} · {med['frequency']}",
            "category": "medicine",
        })
    plan.append({
        "day": recovery_day, "time": "1:30 PM", "title": "High-protein recovery meal",
        "description": "Supports tissue healing", "category": "meal",
    })
    plan.append({
        "day": recovery_day, "time": "5:00 PM", "title": "Guided mobility exercise",
        "description": "15 min gentle stretching, increase gradually", "category": "exercise",
    })
    return plan

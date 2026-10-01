"""Check how consistently live Gemini classifies each demo inspo (bypasses the cache; writes nothing).

    python scripts/detect_stability.py [runs]
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["GEMINI_MODE"] = "live"


def main() -> None:
    from google.genai import types

    from wiw import gemini
    from wiw.detection import PROMPT, SYSTEM, Detection, _dedupe
    from wiw.settings import get_settings

    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    s = get_settings()
    for name in ("old_money_summer", "resort_linen"):
        data = (ROOT / f"demo/inspo/generated/{name}.png").read_bytes()
        seen = Counter()
        for _ in range(runs):
            r = gemini.client().models.generate_content(
                model=s.gemini_model, contents=[types.Part.from_bytes(data=data, mime_type="image/png"), PROMPT],
                config=types.GenerateContentConfig(system_instruction=SYSTEM, temperature=0.1, response_mime_type="application/json",
                                                   response_json_schema=gemini.gemini_schema(Detection)))
            d = _dedupe(Detection.model_validate_json(r.text))
            seen[tuple(sorted(p.subcategory for p in d.pieces))] += 1
        print(name, dict(seen))


if __name__ == "__main__":
    main()

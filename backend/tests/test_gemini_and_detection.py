"""Gemini wrapper modes, cache, schema validation, and the detection fallback."""
import json

import pytest
from pydantic import BaseModel, ValidationError

from wiw import gemini
from wiw.detection import Detection, DetectedPieceModel, _dedupe, crop, fallback_detection
from wiw.settings import ROOT, get_settings


class Tiny(BaseModel):
    word: str


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "cache_dir", tmp_path)
    return tmp_path


def test_off_mode_uses_fallback(cache_dir, monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_mode", "off")
    r = gemini.generate_json("t", version="1", parts=["hi"], schema=Tiny, fallback=lambda: Tiny(word="fb"))
    assert (r.value.word, r.source) == ("fb", "fallback")


def test_replay_reads_cache_and_never_calls_network(cache_dir, monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_mode", "replay")
    monkeypatch.setattr(gemini, "client", lambda: (_ for _ in ()).throw(AssertionError("network!")))
    key = gemini.cache_key("t", "1", None, ["hi"])
    gemini.cache_put("t", key, {"word": "cached"})
    r = gemini.generate_json("t", version="1", parts=["hi"], schema=Tiny, fallback=lambda: Tiny(word="fb"))
    assert (r.value.word, r.source) == ("cached", "cache")
    miss = gemini.generate_json("t", version="1", parts=["other"], schema=Tiny, fallback=lambda: Tiny(word="fb"))
    assert miss.source == "fallback"


def test_invalid_cached_output_falls_back(cache_dir, monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_mode", "replay")
    key = gemini.cache_key("t", "1", None, ["hi"])
    gemini.cache_put("t", key, {"nope": 1})
    r = gemini.generate_json("t", version="1", parts=["hi"], schema=Tiny, fallback=lambda: Tiny(word="fb"))
    assert r.source == "fallback"


def test_cache_key_hashes_images_by_content():
    a = gemini.cache_key("d", "1", "s", [gemini.Image(b"abc"), "p"])
    b = gemini.cache_key("d", "1", "s", [gemini.Image(b"abc"), "p"])
    c = gemini.cache_key("d", "1", "s", [gemini.Image(b"abd"), "p"])
    assert a == b != c


def test_live_failure_falls_back(cache_dir, monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_mode", "live")

    class Boom:
        class models:
            @staticmethod
            def generate_content(**kw):
                raise RuntimeError("quota")
    monkeypatch.setattr(gemini, "client", lambda: Boom)
    r = gemini.generate_json("t", version="1", parts=["x"], schema=Tiny, fallback=lambda: Tiny(word="fb"))
    assert r.source == "fallback" and "quota" in r.error


def test_detection_schema_rejects_invented_values():
    good = dict(subcategory="linen_shirt", name="Ivory linen shirt", color="ivory", box_2d=[10, 10, 500, 500], confidence=0.9)
    assert DetectedPieceModel.model_validate(good)
    for bad in ({"subcategory": "spacesuit"}, {"color": "octarine"}, {"fabric": "vibranium"},
                {"box_2d": [500, 10, 100, 900]}, {"box_2d": [1, 2, 3]}, {"confidence": 1.7}):
        with pytest.raises(ValidationError):
            DetectedPieceModel.model_validate({**good, **bad})
    clamped = DetectedPieceModel.model_validate({**good, "box_2d": [-5, 0, 1200, 400]})
    assert clamped.box_2d == [0, 0, 1000, 400]


def test_dedupe_merges_pairs_of_shoes():
    shoe = dict(subcategory="sandals", name="Tan sandals", color="tan", confidence=0.9)
    d = Detection(pieces=[DetectedPieceModel.model_validate({**shoe, "box_2d": [700, 400, 780, 490]}),
                          DetectedPieceModel.model_validate({**shoe, "box_2d": [700, 510, 780, 580]})])
    out = _dedupe(d)
    assert len(out.pieces) == 1 and out.pieces[0].box_2d == [700, 400, 780, 580]


def test_fallback_uses_ground_truth_for_demo_images():
    truth = json.loads((ROOT / "demo/inspo/generated/truth.json").read_text())
    for name, v in truth.items():
        data = (ROOT / "demo/inspo/generated" / v["file"]).read_bytes()
        det = fallback_detection(data)
        assert [p.subcategory for p in det.pieces] == [p["subcategory"] for p in v["pieces"]], name


def test_fallback_on_unknown_image_is_honest_and_empty():
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (400, 400), "white").save(buf, "PNG")
    det = fallback_detection(buf.getvalue())
    assert det.pieces == [] and det.image_quality == "no_outfit"  # a flat image has nothing in it
    blur = io.BytesIO()
    from PIL import ImageFilter
    img = Image.open(ROOT / "demo/inspo/generated/old_money_summer.png").convert("RGB").resize((200, 356))
    img.filter(ImageFilter.GaussianBlur(12)).save(blur, "PNG")
    assert fallback_detection(blur.getvalue()).image_quality == "blurry"


def test_crop_is_png_within_bounds():
    data = (ROOT / "demo/inspo/generated/old_money_summer.png").read_bytes()
    out = crop(data, [200, 300, 450, 700])
    assert out[:8] == b"\x89PNG\r\n\x1a\n"

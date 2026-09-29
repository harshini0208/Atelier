"""Headless browser smoke test of the main shopper flow (Playwright).

    python scripts/ui_smoke.py [base_url] [out_dir] [--desktop]

Creates a folder, uploads the old-money inspo, selects 3 pieces, hangs them, opens matches and a product,
and adds it to the look. Saves screenshots at each step. Exits non-zero on failure.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    base = args[0] if args else "http://localhost:5173"
    out = Path(args[1] if len(args) > 1 else ROOT / "local/smoke")
    out.mkdir(parents=True, exist_ok=True)
    desktop = "--desktop" in sys.argv
    viewport = {"width": 1360, "height": 860} if desktop else {"width": 390, "height": 844}
    def shot(page, name: str) -> None:
        page.wait_for_timeout(450)  # let sheet/modal animations settle
        page.screenshot(path=str(out / f"{'d' if desktop else 'm'}-{name}.png"))
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=viewport, device_scale_factor=1)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.goto(base)
        page.evaluate("localStorage.setItem('wiw.user', 'aanya')")
        page.goto(base)
        expect(page.get_by_role("heading", name="Your wardrobes")).to_be_visible()
        shot(page, "01-home")

        page.get_by_role("button", name="Add folder").first.click()
        name = f"Old-money summer {int(time.time()) % 1000}"
        page.get_by_label("Name").fill(name)
        page.get_by_label("Description").fill("Linen, loafers and long lunches")
        page.get_by_role("button", name="Create folder").click()
        expect(page.get_by_role("heading", name=name)).to_be_visible()
        shot(page, "02-folder-empty")

        page.set_input_files("input[type=file]", str(ROOT / "demo/inspo/generated/old_money_summer.png"))
        expect(page.get_by_text("Pick what you love")).to_be_visible(timeout=60_000)
        shot(page, "03-inspo-detected")

        for label in ("Linen shirt", "Chinos", "Loafers"):
            page.locator(".box").filter(has_text=label).first.click()
        shot(page, "04-inspo-selected")
        page.get_by_role("button", name="Hang 3 pieces").click()
        expect(page.get_by_text("This store covers").first).to_be_visible(timeout=30_000)
        shot(page, "05-folder-hangers")

        page.locator(".hanger").first.click()
        expect(page.get_by_role("heading", name="For you")).to_be_visible(timeout=30_000)
        shot(page, "06-matches")
        page.get_by_role("dialog").locator(".product-card").first.click()
        expect(page.get_by_role("button", name="Add to look")).to_be_visible()
        shot(page, "07-product")
        page.get_by_role("button", name="Add to look").click()
        expect(page.get_by_text("Added to your look")).to_be_visible()
        shot(page, "08-added")
        page.keyboard.press("Escape")  # close the matches drawer

        # stylist chat
        if not desktop:
            page.get_by_role("button", name="Open stylist chat").click()
        page.get_by_label("Message the stylist").fill("Make it work for a beach wedding under ₹5,000")
        page.get_by_role("button", name="Send").click()
        expect(page.get_by_text("Look for beach wedding")).to_be_visible(timeout=60_000)
        shot(page, "09-stylist")
        page.get_by_role("button", name="Try on").click()
        expect(page.get_by_text("Your hangers")).to_be_visible(timeout=30_000)
        page.wait_for_timeout(800)
        shot(page, "10-wardrobe-stylist-look")

        # style it for me + drag and drop
        page.get_by_role("button", name="Style it", exact=True).click()
        expect(page.get_by_text("Look 1")).to_be_visible(timeout=60_000)
        page.get_by_role("button", name="Clear").click()
        card = page.locator("[aria-label^='Drag ']").first
        stage = page.get_by_role("img", name="Empty mannequin")
        box, sb = card.bounding_box(), stage.bounding_box()
        page.mouse.move(box["x"] + 20, box["y"] + 20)
        page.mouse.down()
        page.mouse.move(box["x"] + 40, box["y"] + 40, steps=5)
        page.mouse.move(sb["x"] + sb["width"] / 2, sb["y"] + sb["height"] * 0.35, steps=12)
        page.wait_for_timeout(200)
        shot(page, "11-dragging")
        page.mouse.up()
        expect(page.get_by_role("img", name=__import__("re").compile("Mannequin wearing"))).to_be_visible()
        shot(page, "12-dropped")
        browser.close()
    if errors:
        print("browser errors:\n  " + "\n  ".join(errors))
        sys.exit(1)
    print(f"UI smoke OK ({'desktop' if desktop else 'mobile'}), screenshots in {out}")


if __name__ == "__main__":
    main()

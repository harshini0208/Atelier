"""Headless browser smoke test of the shopper journey (Playwright).

    python scripts/ui_smoke.py [base_url] [out_dir] [--desktop]

A brand-new visitor: onboarding -> folder -> upload inspo -> tap pieces and hang real store products -> style
board (drag, overlap, answer the inside/outside question) -> shop -> add to cart. Screenshots at each step.
"""
from __future__ import annotations

import re
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
    errors: list[str] = []

    def shot(page, name: str) -> None:
        page.wait_for_timeout(450)
        page.screenshot(path=str(out / f"{'d' if desktop else 'm'}-{name}.png"))

    def drag(page, source, target_box, fx=0.5, fy=0.35) -> None:
        box = source.bounding_box()
        page.mouse.move(box["x"] + 20, box["y"] + 20)
        page.mouse.down()
        page.mouse.move(box["x"] + 40, box["y"] + 40, steps=5)
        page.mouse.move(target_box["x"] + target_box["width"] * fx, target_box["y"] + target_box["height"] * fy, steps=12)
        page.wait_for_timeout(150)
        page.mouse.up()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=viewport, device_scale_factor=1)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and "401" not in m.text and errors.append(m.text))
        page.goto(base)

        # 1. a fresh visitor lands on onboarding (no default shopper)
        expect(page).to_have_url(re.compile(r"/welcome$"))
        expect(page.get_by_role("heading", name="Welcome to your walk-in wardrobe")).to_be_visible()
        page.get_by_label("Your name").fill("Smoke Tester")
        page.get_by_label("City").select_option("Bengaluru")
        shot(page, "01-welcome")
        page.get_by_role("button", name="Next").click()
        expect(page.get_by_role("heading", name="Nice to meet you, Smoke.")).to_be_visible()
        for grp, size in (("tops size", "M"), ("bottoms size", "28"), ("footwear size", "5")):
            page.get_by_role("group", name=grp).get_by_role("button", name=size, exact=True).click()
        page.get_by_role("button", name="Next").click()
        page.get_by_role("button", name="Next").click()   # budgets: keep defaults
        page.locator(".field", has_text="Materials I avoid").get_by_role("button", name="Polyester").click()
        page.get_by_role("button", name="Next").click()
        shot(page, "02-onboarding-last")
        page.get_by_role("button", name="Start my wardrobe").click()
        expect(page.get_by_role("heading", name=re.compile("Hi Smoke"))).to_be_visible()
        expect(page.get_by_text("Your wardrobes")).to_be_visible()
        shot(page, "03-home-fresh")

        # 2. upload straight from the landing page (no folder yet), tap pieces BEFORE choosing a folder
        page.set_input_files("input[type=file]", str(ROOT / "demo/inspo/generated/old_money_summer.png"))
        expect(page.get_by_text("Tap a piece you love")).to_be_visible(timeout=60_000)
        shot(page, "04-inspo")
        page.get_by_role("button", name="Done").click()
        expect(page.get_by_text("Tap the pieces you like first")).to_be_visible()   # never leaves empty-handed
        page.locator(".box").filter(has_text="Linen shirt").first.click()
        expect(page.get_by_text("You liked this piece. Choose a folder")).to_be_visible(timeout=30_000)
        page.locator(".box").filter(has_text="Chinos").first.click()
        expect(page.get_by_role("button", name="Save 2 liked pieces")).to_be_visible()
        # 3. create a folder from the picker -> both liked pieces are hung with their best store match
        name = f"Old-money summer {int(time.time()) % 1000}"
        page.get_by_label("Hang pieces in").select_option("new")
        page.get_by_label("Name").fill(name)
        page.get_by_role("button", name="Create folder").click()
        expect(page.get_by_role("button", name=re.compile(r"Done: 2 pieces on hangers"))).to_be_visible(timeout=30_000)
        # a third piece, tapped after the folder exists, is hung immediately; then swap its product
        page.locator(".box").filter(has_text="Loafers").first.click()
        expect(page.get_by_role("button", name=re.compile(r"Done: 3 pieces on hangers"))).to_be_visible(timeout=30_000)
        expect(page.get_by_role("button", name="On your hanger")).to_be_visible(timeout=30_000)
        shot(page, "05-piece-matches")
        swap = page.get_by_role("button", name="Swap to this")
        if swap.count():
            swap.first.click()
            expect(page.get_by_text("is on your hanger").last).to_be_visible()
        shot(page, "06-hung")
        page.get_by_role("button", name=re.compile(r"Done: 3 pieces")).click()
        expect(page.get_by_role("heading", name=name)).to_be_visible(timeout=30_000)
        expect(page.get_by_role("tab", name="Hangers (3)")).to_be_visible()
        expect(page.locator(".hanger-card img").first).to_have_attribute("src", re.compile(r"/media/products/"))
        shot(page, "07-folder-hangers")

        # 4. style board: drag two pieces so they overlap -> inside/outside question
        page.get_by_role("button", name="Style board").click()
        expect(page.get_by_text("Your hangers")).to_be_visible(timeout=30_000)
        page.get_by_role("heading", name="Your hangers").scroll_into_view_if_needed()
        page.evaluate("window.scrollBy(0, -80)")
        board = page.get_by_role("region", name="Empty style board")
        bb = board.bounding_box()
        cards = page.locator("[aria-label^='Drag ']")
        drag(page, cards.nth(0), bb, 0.35, 0.12)
        expect(page.get_by_role("region", name=re.compile("Style board with"))).to_be_visible()
        drag(page, cards.nth(1), page.get_by_role("region", name=re.compile("Style board with")).bounding_box(), 0.37, 0.14)
        expect(page.get_by_role("dialog", name="How should these layer?")).to_be_visible()
        shot(page, "08-layer-question")
        page.get_by_role("dialog").get_by_role("button", name=re.compile(r"^Outside")).click()
        expect(page.get_by_text(re.compile("is outside, over"))).to_be_visible()
        shot(page, "09-board")
        page.get_by_role("button", name="Save look").click()
        expect(page.get_by_text("Look saved")).to_be_visible()

        # 5. shop like a store website, add to cart
        if desktop:
            page.get_by_role("navigation", name="Main").first.get_by_role("link", name="Shop").click()
        else:
            page.locator(".bottom-nav").get_by_role("link", name="Shop").click()
        expect(page.get_by_role("tab", name="Women")).to_be_visible()
        page.locator(".shop-cats").get_by_role("button", name=re.compile("^Tops")).click()
        expect(page.get_by_role("heading", name=re.compile("^Tops"))).to_be_visible()
        shot(page, "10-shop")
        page.locator(".shop-card").first.click()
        page.get_by_role("button", name="Add to cart").click()
        expect(page.get_by_text("Added to cart")).to_be_visible()
        shot(page, "11-added-to-cart")
        # leave no trace: the smoke shopper deletes their own profile and data
        status = page.evaluate("""async () => (await fetch('/api/me', {method: 'DELETE',
            headers: {'X-User-Id': localStorage.getItem('wiw.user')}})).status""")
        assert status == 200, f"cleanup failed: {status}"
        browser.close()
    if errors:
        print("browser errors:\n  " + "\n  ".join(errors))
        sys.exit(1)
    print(f"UI smoke OK ({'desktop' if desktop else 'mobile'}), screenshots in {out}")


if __name__ == "__main__":
    main()

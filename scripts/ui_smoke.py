"""Headless browser smoke test of the shopper journey (Playwright).

    python scripts/ui_smoke.py [base_url] [out_dir] [--desktop] [--no-gemini]

A brand-new visitor: onboarding (mannequin + membership) -> rail -> hang a piece in a new folder -> upload an inspo and
hang store matches -> style board (dress the mannequin) -> stylist -> shop -> cart and checkout -> preferences -> theme.
Screenshots at each step. --no-gemini skips the steps that need live Gemini (mannequin render, stylist reply).
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
    gemini = "--no-gemini" not in sys.argv
    viewport = {"width": 1440, "height": 900} if desktop else {"width": 390, "height": 844}
    errors: list[str] = []

    def shot(page, name: str) -> None:
        page.wait_for_timeout(500)
        page.screenshot(path=str(out / f"{'d' if desktop else 'm'}-{name}.png"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            run(p, browser, base, out, desktop, gemini, viewport, errors, shot)
        except Exception:
            for pg in browser.contexts[0].pages if browser.contexts else []:
                pg.screenshot(path=str(out / f"{'d' if desktop else 'm'}-FAILED.png"))
            raise
        browser.close()
    if errors:
        print("browser errors:\n  " + "\n  ".join(errors))
        sys.exit(1)
    print(f"UI smoke OK ({'desktop' if desktop else 'mobile'}), screenshots in {out}")


def run(p, browser, base, out, desktop, gemini, viewport, errors, shot) -> None:  # noqa: ANN001, PLR0913
    if True:
        page = browser.new_page(viewport=viewport, device_scale_factor=1)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: m.type == "error" and "401" not in m.text and errors.append(m.text))
        page.goto(base)

        # 1. a fresh visitor lands on onboarding
        expect(page).to_have_url(re.compile(r"/welcome$"))
        expect(page.get_by_role("heading", name=re.compile("Welcome to"))).to_be_visible()
        page.get_by_label("Your name").fill("Smoke Tester")
        page.get_by_label("City (for delivery times)").select_option("Bengaluru")
        shot(page, "01-welcome")
        page.get_by_role("button", name="Next").click()
        for grp, size in (("tops size", "M"), ("bottoms size", "28"), ("footwear size", "5")):
            page.get_by_role("group", name=grp).get_by_role("button", name=size, exact=True).click()
        page.get_by_role("button", name="Next").click()
        expect(page.get_by_role("heading", name="Your mannequin")).to_be_visible()
        page.get_by_role("button", name="Curvy").click()
        page.get_by_role("button", name="brown finish").click()
        shot(page, "02-mannequin")
        page.get_by_role("button", name="Next").click()   # -> budgets
        page.get_by_role("button", name="Next").click()   # -> fabrics
        page.get_by_role("button", name="Next").click()   # -> colours and occasions
        expect(page.get_by_text("Bring in my Urban Thread purchases")).to_be_visible()
        page.get_by_role("button", name="Open my wardrobe").click()

        # 2. home: the rail, filled from the (demo) membership
        expect(page.get_by_role("heading", name="Hi Smoke.")).to_be_visible(timeout=30_000)
        expect(page.get_by_text("Membership linked")).to_be_visible()
        expect(page.get_by_role("button", name="Add to folders").first).to_be_visible()
        shot(page, "03-home")

        # 3. hang the first rail piece in a brand-new folder
        page.get_by_role("button", name="Add to folders").first.click()
        name = f"Office edit {int(time.time()) % 1000}"
        page.get_by_label("New folder name").fill(name)
        page.get_by_role("button", name="Add", exact=True).click()
        expect(page.get_by_role("checkbox").first).to_be_checked()
        shot(page, "04-hang-sheet")
        page.get_by_role("button", name="Save").click()
        expect(page.get_by_role("button", name="In 1 folder").first).to_be_visible(timeout=15_000)

        # 4. upload an inspo from home, hang store matches into that folder
        page.set_input_files("input[type=file]", str(ROOT / "demo/inspo/generated/old_money_summer.png"))
        expect(page.get_by_text("Tap a piece you love")).to_be_visible(timeout=90_000)
        page.get_by_label("Hang pieces in").select_option(label=name)
        chips = page.locator("button[aria-pressed]").filter(has=page.locator("img"))
        chips.first.click()
        expect(page.get_by_role("button", name="On your hanger").first).to_be_visible(timeout=30_000)
        shot(page, "05-inspo-matches")
        page.get_by_role("button", name=re.compile(r"^Done")).click()
        expect(page.get_by_role("heading", name=name)).to_be_visible(timeout=30_000)
        expect(page.get_by_text("From inspo").first).to_be_visible()
        expect(page.get_by_text("From your rail").first).to_be_visible()
        shot(page, "06-folder")

        # 5. style board: put two pieces on and dress the mannequin
        page.get_by_role("link", name="Style board").click()
        expect(page.get_by_role("heading", name="Layers")).to_be_visible(timeout=15_000)
        adds = page.locator("li button", has_text=re.compile(r"^Add$"))   # tray "Add" buttons
        expect(adds.first).to_be_visible(timeout=15_000)
        for _ in range(min(2, adds.count())):
            adds.first.click()
            page.wait_for_timeout(300)
        if gemini:
            page.get_by_role("button", name=re.compile("Dress mannequin|Update the mannequin")).click()
            expect(page.locator("img[alt^='Your mannequin wearing']")).to_have_attribute("src", re.compile("/media/tryon/"), timeout=90_000)
            expect(page.get_by_text("Dressing your mannequin")).to_have_count(0, timeout=90_000)
        shot(page, "07-board")
        page.get_by_role("button", name="Save look").click()
        expect(page.get_by_role("heading", name="Saved looks")).to_be_visible()

        # 6. stylist (desktop column, or the mobile sheet)
        if gemini:
            if not desktop:
                page.get_by_role("button", name="Stylist").click()
            page.get_by_label("Message your stylist").fill("Style an outfit for a weekend brunch")
            page.get_by_role("button", name="Send").click()
            expect(page.get_by_text("Styling…")).to_have_count(0, timeout=120_000)
            expect(page.get_by_role("button", name="Open on board").last).to_be_visible(timeout=30_000)
            shot(page, "08-stylist")
            if not desktop:
                page.keyboard.press("Escape")

        # 7. shop: heart a piece, open one, add to cart; checkout
        page.goto(base + "/shop")
        expect(page.get_by_role("heading", name="Shop")).to_be_visible(timeout=30_000)
        page.get_by_role("button", name=re.compile("^Add .* to wishlist")).first.click()
        shot(page, "09-shop")
        page.locator(".shop-card img").first.click()
        page.locator("button[aria-label]").filter(has_text=re.compile(r"^(S|M|L|26|28|30)$")).first.click()
        page.get_by_role("button", name="Add to cart").click()
        expect(page.get_by_text("Added to your bag")).to_be_visible(timeout=15_000)
        shot(page, "10-product")
        page.keyboard.press("Escape")
        page.goto(base + "/cart")
        page.get_by_role("button", name="Place order").click()
        expect(page.get_by_text(re.compile(r"Order #\d+ placed"))).to_be_visible(timeout=15_000)
        shot(page, "11-cart")

        # 8. preferences save, then try a theme
        page.goto(base + "/preferences")
        page.get_by_role("button", name="Save changes").first.click()
        expect(page.get_by_text("Saved. Your matches are updated.")).to_be_visible(timeout=15_000)
        page.get_by_role("button", name="Profile menu").click()
        page.get_by_role("radio", name="Rose Gold Noir").click()
        page.keyboard.press("Escape")
        page.goto(base + "/")
        expect(page.locator("html")).to_have_attribute("data-theme", "rose-gold-noir")
        shot(page, "12-rose-gold-noir")

        # leave no trace: the smoke shopper deletes their own profile and data
        # (a separate request, after leaving the app: once the profile is gone the app redirects to onboarding)
        uid = page.evaluate("localStorage.getItem('wiw.user')")
        page.goto("about:blank")
        status = page.request.delete(base + "/api/me", headers={"X-User-Id": uid}).status
        assert status == 200, f"cleanup failed: {status}"


if __name__ == "__main__":
    main()

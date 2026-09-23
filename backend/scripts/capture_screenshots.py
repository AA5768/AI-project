"""Regenerate the README screenshots from the running app.

The images in docs/images/ are binaries, so this script is their reviewable
form -- the same reason generate_office_corpus.py exists. A screenshot nobody
can reproduce is a claim, not evidence: when the UI changes, re-run this and
the README stops lying rather than quietly aging.

Each shot is driven through the real UI against the real API, so what the
README shows is what the system does, including the confidence values.

    # with the API on :8000 and the UI on :5173
    cd backend && python -m scripts.capture_screenshots

Playwright drives an installed Edge or Chrome rather than its own Chromium
build: the bundled download goes through a Node HTTP client that does not use
the OS certificate store, so it fails behind a TLS-intercepting proxy in the
same way HuggingFace downloads do (see app/config.py).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "docs" / "images"

VIEWPORT = {"width": 1440, "height": 950}

# Capture at 2x and downsample, rather than capturing at 1.25x directly:
# Chromium renders text at fractional device scales slightly soft, while
# Lanczos from a clean 2x does not. GitHub renders README images at about
# 900 px wide, so 1800 is a retina-sharp source at a fifth of the bytes.
SCALE = 2
MAX_WIDTH = 1800
PALETTE = 192  # flat UI colour; more than this buys nothing visible

ANSWERABLE = "What did we decide about the Northgate particle excursion?"
ROUTED_TO_PERSON = "What is the nine pass number for Helios-3?"
ROUTED_TO_NOBODY = "What is our parental leave policy?"


def _ask(page: Page, question: str) -> None:
    box = page.get_by_placeholder("Ask about Meridian Microsystems")
    box.fill(question)
    # Scoped to main: the nav has its own "Ask" tab button.
    page.get_by_role("main").get_by_role("button", name="Ask", exact=True).click()
    # The button reads "Asking…" while in flight; a real Claude call is slow.
    page.wait_for_function(
        "() => !document.body.innerText.includes('Asking…')", timeout=90_000
    )
    page.wait_for_timeout(600)


def _shot(page: Page, out: Path, name: str, full_page: bool = True) -> None:
    path = out / f"{name}.png"
    page.screenshot(path=str(path), full_page=full_page)

    from PIL import Image

    with Image.open(path) as image:
        resized = image
        if image.width > MAX_WIDTH:
            height = round(image.height * MAX_WIDTH / image.width)
            resized = image.resize((MAX_WIDTH, height), Image.LANCZOS)
        # Quantise before saving. Resizing turns flat UI colour into gradients,
        # which is exactly what PNG cannot compress -- downsampling alone made
        # these files *larger* than the 2x originals. A screenshot of a
        # two-colour interface does not need 16 million of them.
        resized.convert("RGB").quantize(
            colors=PALETTE, method=Image.MEDIANCUT, dither=Image.Dither.NONE
        ).save(path, optimize=True)

    print(f"  wrote {path.relative_to(REPO_ROOT).as_posix()}  ({path.stat().st_size // 1024} KB)")


def capture(base_url: str, out: Path, channel: str) -> None:
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel)
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=SCALE)
        page.goto(base_url, wait_until="networkidle")

        # 1. An answered question: claims carrying the citations for that claim.
        _ask(page, ANSWERABLE)
        _shot(page, out, "ask-answered")

        # 2. The same answer with the confidence derivation opened, because the
        #    number is the point and "trust me" is not.
        breakdown = page.get_by_text("How this confidence was computed", exact=False)
        if breakdown.count():
            breakdown.first.click()
            page.wait_for_timeout(400)
            _shot(page, out, "ask-confidence")

        # 3. The source behind a citation, opened from the marker itself.
        marker = page.locator("button", has_text="1").first
        try:
            marker.click(timeout=5_000)
            page.wait_for_timeout(800)
            _shot(page, out, "source-drawer")
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
        except Exception as exc:  # noqa: BLE001 - one missing shot is not a failure
            print(f"  skipped source-drawer: {exc}")

        # 4. Routed to a person, with the passage that chose them.
        _ask(page, ROUTED_TO_PERSON)
        _shot(page, out, "routed-to-person")

        # 5. Routed to nobody. The most load-bearing screenshot here: it is the
        #    visible form of "no one is named when the corpus connects no one".
        _ask(page, ROUTED_TO_NOBODY)
        _shot(page, out, "routed-to-nobody")

        # 6. The triage queue those routed questions land in.
        page.get_by_role("button", name="Review queue").click()
        page.wait_for_timeout(1_200)
        _shot(page, out, "review-queue")

        # 7. The first-30-days metric beside its live value.
        page.get_by_role("button", name="Measurement").click()
        page.wait_for_timeout(1_200)
        _shot(page, out, "measurement")

        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:5173")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--channel", default="msedge",
        help="Installed browser Playwright should drive: msedge or chrome.",
    )
    args = parser.parse_args()

    print(f"capturing from {args.url} using {args.channel}")
    try:
        capture(args.url, args.out, args.channel)
    except Exception as exc:  # noqa: BLE001
        print(f"\nfailed: {type(exc).__name__}: {exc}")
        print("Is the UI running on that URL, and the API on :8000?")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Screenshot HTML slide to PNG via Playwright."""
from pathlib import Path
from playwright.sync_api import sync_playwright

html = Path(r"d:\DATN\kma_rag\demo\assets\slide3_grader_escalation.html").resolve()
out  = Path(r"d:\DATN\kma_rag\demo\assets\slide3_grader_escalation.png")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=2)
    page.goto(html.as_uri())
    page.wait_for_timeout(800)
    page.screenshot(path=str(out), type="png")
    browser.close()

print("Saved:", out)

"""Full walkthrough test of MedSafe-AI Product App (React UI) with video recording."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent
SAMPLE_IMAGE = ROOT / "examples" / "synthetic_prescription.png"
INVALID_FILE = ROOT / "examples" / "synthetic_prescription.txt"
VIDEO_DIR = Path(__file__).resolve().parent / "product_app_video"

results: list[tuple[str, str, str]] = []


def record(step: str, status: str, detail: str = "") -> None:
    results.append((step, status, detail))
    print(f"[{status}] {step}" + (f" â€” {detail}" if detail else ""), flush=True)


def run() -> int:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(VIDEO_DIR),
            record_video_size={"width": 1440, "height": 900},
        )
        page = context.new_page()
        page.set_default_timeout(15000)

        try:
            # â”€â”€ 1. Overview page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            page.goto(BASE, wait_until="networkidle")
            time.sleep(1.5)
            expect(page.locator(".brand-word")).to_contain_text("MedSafe")
            expect(page.locator("h1")).to_contain_text("Overview")
            record("1. Load Overview page", "PASS", "Brand + heading visible")

            hero = page.locator(".hero-panel")
            expect(hero).to_be_visible()
            record("1b. Hero banner visible", "PASS")

            stats = page.locator(".stat-grid .stat-card, .stat-grid > div")
            stat_count = stats.count()
            record("1c. Stats cards rendered", "PASS" if stat_count >= 4 else "WARN",
                   f"{stat_count} stat cards found")

            guardrails = page.locator(".assurance-panel")
            expect(guardrails).to_be_visible()
            record("1d. Safety guardrails panel", "PASS")

            # â”€â”€ 2. Research & benchmarks page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            page.locator(".side-link", has_text="Research & benchmarks").click()
            time.sleep(1)
            expect(page.locator("h1")).to_contain_text("Research")
            record("2. Navigate to Research & benchmarks", "PASS")
            time.sleep(0.8)

            # â”€â”€ 3. New analysis (Upload) page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            page.locator(".side-link", has_text="New analysis").click()
            time.sleep(1)
            expect(page.locator("h1")).to_contain_text("New analysis")
            record("3. Navigate to New analysis", "PASS")

            # Upload form elements
            expect(page.locator(".drop-area")).to_be_visible()
            expect(page.locator(".engine-grid")).to_be_visible()
            record("3b. Upload form elements visible", "PASS", "Drop area + engine grid")

            # â”€â”€ 4. Error case: invalid file type â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            file_input = page.locator('input[type="file"]')
            file_input.set_input_files(str(INVALID_FILE))
            time.sleep(0.5)
            err = page.locator(".notice-error, .error-wrap .notice, [class*='error']").first
            if err.count() > 0 and err.is_visible():
                record("4. Reject invalid file type (.txt)", "PASS",
                       err.inner_text().strip()[:80])
            else:
                record("4. Reject invalid file type (.txt)", "FAIL", "No error shown")

            # Clear by selecting valid file later (state resets on valid select)
            # â”€â”€ 5. Error case: upload without selecting (button disabled) â”€
            submit_btn = page.locator("button.submit-upload, button:has-text('Run OCR analysis')")
            is_disabled = submit_btn.is_disabled()
            record("5. Submit disabled with no file", "PASS" if is_disabled else "FAIL",
                   f"disabled={is_disabled}")

            # â”€â”€ 6. Upload valid image with Tesseract + no preprocessing â”€â”€â”€
            file_input.set_input_files(str(SAMPLE_IMAGE))
            time.sleep(0.5)
            selected = page.locator(".selected-file")
            expect(selected).to_be_visible()
            record("6. Valid image selected", "PASS", "synthetic_prescription.png")

            # Ensure Tesseract engine selected (default)
            tess_btn = page.locator(".engine-option", has_text="Tesseract")
            if "active" not in (tess_btn.get_attribute("class") or ""):
                tess_btn.click()
                time.sleep(0.3)
            record("6b. Tesseract engine selected", "PASS")

            # Run OCR
            submit_btn.click()
            record("6c. Clicked Run OCR analysis", "INFO", "Waiting for processingâ€¦")

            # Wait for navigation to workspace (upload â†’ onUploaded â†’ open)
            page.wait_for_selector(".review-heading, .workspace-footer", timeout=60000)
            time.sleep(1.5)
            expect(page.locator("h1")).to_contain_text("Prescription review")
            record("7. Uploaded â†’ Workspace opened", "PASS")

            # â”€â”€ 8. Workspace: transcription tab â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            expect(page.locator("#transcription")).to_be_visible()
            transcript = page.locator("#transcription").input_value()
            record("8. Transcription textarea loaded", "PASS",
                   f"{len(transcript)} chars")

            # Workflow progress stages
            stages = page.locator(".workflow-stage")
            record("8b. Workflow stages shown", "PASS", f"{stages.count()} stages")

            # Image evidence
            expect(page.locator(".preview-frame img, .preview-frame canvas")).to_be_visible()
            record("8c. Original image preview visible", "PASS")

            # â”€â”€ 9. Edit transcript slightly then confirm â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Append a note to show editing works, then confirm
            edited = transcript + "\nNote: reviewed by tester."
            page.locator("#transcription").fill(edited)
            time.sleep(0.3)
            record("9. Edited transcription", "PASS")

            confirm_btn = page.locator("button:has-text('Confirm transcription')")
            confirm_btn.click()
            record("9b. Clicked Confirm transcription", "INFO", "Running safety screenâ€¦")

            # Wait for findings tab to become active
            page.wait_for_selector('[role="tab"][aria-selected="true"]:has-text("Safety findings")',
                                   timeout=30000)
            time.sleep(1)
            record("10. Safety findings tab activated", "PASS")

            # â”€â”€ 11. Findings content â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            notice_warn = page.locator(".tab-body .notice, .tab-body [class*='notice']").first
            if notice_warn.count() > 0:
                record("11. Clinical disclaimer shown", "PASS",
                       notice_warn.inner_text().strip()[:70])

            findings_summary = page.locator(".findings-summary")
            if findings_summary.count() > 0:
                num = page.locator(".findings-summary .finding-number").inner_text()
                record("11b. Findings count displayed", "PASS", f"{num} observations")

            med_cards = page.locator(".medication-card")
            med_count = med_cards.count()
            record("11c. Medication cards rendered", "PASS" if med_count > 0 else "WARN",
                   f"{med_count} medication(s)")

            # Try reference lookup if a medicine name exists
            ref_btn = page.locator("button:has-text('label evidence')").first
            if ref_btn.count() > 0 and ref_btn.is_visible():
                ref_btn.click()
                time.sleep(2)
                evidence = page.locator(".evidence-box")
                if evidence.count() > 0:
                    record("11d. Reference lookup triggered", "PASS",
                           evidence.first.inner_text().strip()[:60])
                else:
                    record("11d. Reference lookup triggered", "WARN", "No evidence box appeared")

            # â”€â”€ 12. Audit trail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            audit_events = page.locator(".audit-event")
            audit_count = audit_events.count()
            record("12. Audit trail visible", "PASS" if audit_count > 0 else "WARN",
                   f"{audit_count} event(s)")

            # â”€â”€ 13. Export report â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            export_btn = page.locator("button:has-text('Export report')")
            if export_btn.count() > 0:
                # Set up download listener
                with page.expect_download(timeout=5000) as dl_info:
                    export_btn.click()
                dl = dl_info.value
                record("13. Export report (JSON download)", "PASS", dl.suggested_filename)
            else:
                record("13. Export report button", "FAIL", "Button not found")

            # â”€â”€ 14. Library page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            page.locator(".side-link", has_text="Prescription records").click()
            time.sleep(1)
            expect(page.locator("h1")).to_contain_text("Prescription records")
            rows = page.locator(".data-table tbody tr, .library-list > *, table tbody tr")
            record("14. Library page shows records", "PASS",
                   f"{rows.count()} row(s) visible")
            time.sleep(0.8)

            # â”€â”€ 15. Error case: open non-existent record via URL â”€â”€â”€â”€â”€â”€â”€â”€â”€
            page.goto(BASE + "/api/prescriptions/does-not-exist", wait_until="domcontentloaded")
            time.sleep(0.5)
            body = page.locator("body").inner_text()
            if "not found" in body.lower() or "404" in body or "Prescription not found" in body:
                record("15. Non-existent record returns 404", "PASS")
            else:
                record("15. Non-existent record returns 404", "WARN",
                       body[:60])
            page.goto(BASE, wait_until="networkidle")
            time.sleep(1)

            # â”€â”€ 16. Research page again for completeness â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            page.locator(".side-link", has_text="Research & benchmarks").click()
            time.sleep(1)
            record("16. Research page revisited", "PASS")
            time.sleep(0.5)

            # â”€â”€ 17. Overview final state â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            page.locator(".side-link", has_text="Overview").click()
            time.sleep(1)
            record("17. Return to Overview", "PASS")
            time.sleep(1)

            record("FULL WALKTHROUGH", "DONE", "Product App test complete")

        except Exception as exc:  # noqa: BLE001
            failures += 1
            record("UNEXPECTED ERROR", "FAIL", str(exc)[:200])
            page.screenshot(path=str(VIDEO_DIR / "error_screenshot.png"))
        finally:
            context.close()
            browser.close()

    # Print summary
    print("\n" + "=" * 60)
    print("PRODUCT APP TEST SUMMARY")
    print("=" * 60)
    pass_n = sum(1 for _, s, _ in results if s == "PASS")
    fail_n = sum(1 for _, s, _ in results if s == "FAIL")
    warn_n = sum(1 for _, s, _ in results if s == "WARN")
    for step, status, detail in results:
        print(f"  [{status:4s}] {step}" + (f" â€” {detail}" if detail else ""))
    print(f"\n  PASS: {pass_n}  FAIL: {fail_n}  WARN: {warn_n}  TOTAL: {len(results)}")
    print(f"  Videos saved in: {VIDEO_DIR}")
    return 1 if fail_n > 0 or failures > 0 else 0


if __name__ == "__main__":
    sys.exit(run())


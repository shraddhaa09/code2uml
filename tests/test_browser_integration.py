import io
import os
import time
import zipfile
import threading
import pytest

playwright_module = pytest.importorskip("playwright.sync_api", reason="Playwright is required for browser integration tests")
from playwright.sync_api import sync_playwright
import uvicorn
from backend.main import app


class ServerThread(threading.Thread):
    def __init__(self, app, host="127.0.0.1", port=8001):
        super().__init__()
        self.host = host
        self.port = port
        self.config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(self.config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


def test_browser_sample_project_workflow(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GEMMA_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    
    # 1. Start test server in background thread
    server = ServerThread(app, port=8001)
    server.start()
    time.sleep(1)

    screenshot_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1400, "height": 900})

            # 2. Navigate to frontend
            page.goto("http://127.0.0.1:8001")
            page.wait_for_selector("#sampleBtn")

            # 3. Click Sample Project Button
            page.click("#sampleBtn")

            # 4. Wait for results section to become visible
            page.wait_for_selector("#resultsSection:not(.hidden)", timeout=10000)
            page.wait_for_selector("#mermaidOutput svg", timeout=10000)

            # 5. Assert summary stats cards
            assert page.inner_text("#statTotalTypes").strip() == "7"
            sub_text = page.inner_text("#statTypesSubtitle").strip()
            assert "5 classes" in sub_text and "2 interfaces" in sub_text
            assert page.inner_text("#statControllers").strip() == "1"
            assert page.inner_text("#statServices").strip() == "1"
            assert "(+1 service interface)" in page.inner_text("#statServicesSublabel").strip()
            assert page.inner_text("#statRepositories").strip() == "1"
            assert page.inner_text("#statEntities").strip() == "1"
            assert page.inner_text("#statDTOs").strip() == "1"
            assert page.inner_text("#statApplications").strip() == "1"
            assert page.inner_text("#statEndpoints").strip() == "4"
            assert page.inner_text("#statRelationships").strip() == "10"

            # 6. Assert Observations Banner
            page.wait_for_selector("#observationsSection:not(.hidden)", timeout=5000)
            obs_text = page.inner_text("#observationsSection")
            assert "UserController exposes the User entity directly in 3 endpoints" in obs_text

            # 7. Check Initial Mermaid Diagram (Architecture View: Default structural + DTO edges)
            svg_content = page.inner_html("#mermaidOutput")
            assert "UserController" in svg_content
            assert "UserService" in svg_content
            assert "UserServiceImpl" in svg_content
            assert "UserRepository" in svg_content
            assert "User" in svg_content
            assert "UserDTO" in svg_content
            assert "DemoApplication" in svg_content
            assert "Application Entry Point" in svg_content
            assert "GET" in svg_content and "/api/users" in svg_content
            assert "POST" in svg_content
            assert "DELETE" in svg_content
            assert "+1 more" not in svg_content

            # Capture Screenshot: Default Structural View
            page.screenshot(path=os.path.join(screenshot_dir, "diagram_default.png"))
            page.screenshot(path=os.path.join(screenshot_dir, "architecture_view.png"))

            # 8. Perform 5 Toggles of "Show 'uses' edges" and Assert Negative Constraints
            for i in range(5):
                page.click(".toggle-control")
                page.wait_for_timeout(300)

                page_text = page.content()
                # Assert NO "Syntax error" text exists anywhere in the DOM
                assert "Syntax error in text" not in page_text
                assert "Syntax error" not in page_text

                # Assert NO stray error SVG exists outside .app-container
                stray_errors = page.query_selector_all("body > svg[id^='dmermaid'], body > #dmermaid, body > svg[aria-roledescription='error']")
                assert len(stray_errors) == 0

                caption_text = page.inner_text("#diagramCaption")
                assert "Showing" in caption_text and "of 10 relationships" in caption_text

            # Capture Screenshot: Full View with Uses Edges
            page.screenshot(path=os.path.join(screenshot_dir, "diagram_full.png"))

            # 9. Test UML Class View Tab
            page.click("button[data-tab='umlTab']")
            page.wait_for_selector("#mermaidUmlOutput svg", timeout=10000)
            uml_svg_content = page.inner_html("#mermaidUmlOutput")
            assert "UserController" in uml_svg_content
            assert "UserService" in uml_svg_content
            assert "UserServiceImpl" in uml_svg_content
            assert "UserRepository" in uml_svg_content
            assert "User" in uml_svg_content
            assert "UserDTO" in uml_svg_content
            assert "DemoApplication" in uml_svg_content

            # Assert NO "Syntax error" text in UML view
            page_text_uml = page.content()
            assert "Syntax error in text" not in page_text_uml
            assert "Syntax error" not in page_text_uml

            # Capture Screenshot: UML Class View
            page.screenshot(path=os.path.join(screenshot_dir, "uml_class_view.png"))

            # Switch back to Architecture View tab
            page.click("button[data-tab='diagramTab']")

            # 10. Check Component Catalog formatting
            page.click("button[data-tab='catalogTab']")
            page.wait_for_selector("#componentsList .component-card")
            catalog_html = page.inner_html("#componentsList")

            # Check Implements wording: "Implements: UserService" without duplicate "implements"
            assert "implements implements" not in catalog_html
            assert "<b>Implements:</b> <span class=\"tag tag-impl\">UserService</span>" in catalog_html

            # Check Extends and Manages on separate lines
            assert "<div><b>Extends:</b> <code>JpaRepository&lt;User, Long&gt;</code></div>" in catalog_html
            assert "<div><b>Manages:</b> <span class=\"tag tag-dep\">User</span></div>" in catalog_html

            # Check annotation attribute formatting:
            # @Table(name = "users") has quotes
            assert "@Table(name = &quot;users&quot;)" in catalog_html or '@Table(name = "users")' in catalog_html
            # @GeneratedValue(strategy = GenerationType.IDENTITY) has no quotes
            assert "@GeneratedValue(strategy = GenerationType.IDENTITY)" in catalog_html

            # 11. Test Chat queries
            chat_input = page.locator("#chatInput")
            chat_form = page.locator("#chatForm")

            # Query 0: Architectural observations / issues
            chat_input.fill("What architectural issues or code smells exist?")
            chat_form.evaluate("form => form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }))")
            page.wait_for_selector(".bot-bubble:has-text('UserController exposes the User entity directly')", timeout=10000)
            last_bot_msg0 = page.locator(".bot-bubble").last.inner_text()
            assert "UserController exposes the User entity directly" in last_bot_msg0

            # Query 1: Database vendor
            chat_input.fill("Which database vendor is used?")
            chat_form.evaluate("form => form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }))")
            page.wait_for_selector(".bot-bubble:has-text('database vendor')", timeout=10000)
            last_bot_msg = page.locator(".bot-bubble").last.inner_text()
            assert "database vendor" in last_bot_msg.lower() and ("not determinable" in last_bot_msg.lower() or "not provide enough information" in last_bot_msg.lower())

            # Query 2: Authentication
            chat_input.fill("Is there an authentication component?")
            chat_form.evaluate("form => form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }))")
            page.wait_for_selector(".bot-bubble:has-text('authentication component')", timeout=10000)
            last_bot_msg2 = page.locator(".bot-bubble").last.inner_text()
            assert "authentication component" in last_bot_msg2.lower() and ("no authentication" in last_bot_msg2.lower() or "not detected" in last_bot_msg2.lower() or "no such component" in last_bot_msg2.lower())

            # Query 3: UserController direct dependency
            chat_input.fill("Does UserController directly depend on UserRepository?")
            chat_form.evaluate("form => form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }))")
            page.wait_for_selector(".bot-bubble:has-text('UserController')", timeout=10000)
            last_bot_msg3 = page.locator(".bot-bubble").last.inner_text()
            assert "UserController" in last_bot_msg3 and "UserRepository" in last_bot_msg3 and ("not" in last_bot_msg3.lower() or "indirect" in last_bot_msg3.lower())

            # Query 4: Request flow
            chat_input.fill("Explain the overall request flow from controller to database.")
            chat_form.evaluate("form => form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }))")
            page.wait_for_selector(".bot-bubble:has-text('Request Flow')", timeout=10000)
            last_bot_msg4 = page.locator(".bot-bubble").last.inner_text()
            assert "UserController" in last_bot_msg4 and "UserService" in last_bot_msg4

            # 12. Test UI Error States and Verify Previous Diagram is Preserved
            # Create test zip fixtures
            empty_zip_path = os.path.join(screenshot_dir, "empty_test.zip")
            with zipfile.ZipFile(empty_zip_path, "w") as z:
                pass

            no_java_zip_path = os.path.join(screenshot_dir, "no_java_test.zip")
            with zipfile.ZipFile(no_java_zip_path, "w") as z:
                z.writestr("notes.txt", "hello world")

            corrupt_zip_path = os.path.join(screenshot_dir, "corrupt_test.zip")
            with open(corrupt_zip_path, "wb") as f:
                f.write(b"not a valid zip binary content")

            # Error State 1: Upload Empty ZIP
            page.set_input_files("#fileInput", empty_zip_path)
            page.wait_for_selector("#errorMessage:not(.hidden)", timeout=5000)
            assert "empty" in page.inner_text("#errorText").lower()
            # Crucial: Assert resultsSection is STILL visible (diagram not hidden)
            assert not page.locator("#resultsSection").is_hidden()

            # Error State 2: Upload ZIP with no Java files
            page.set_input_files("#fileInput", no_java_zip_path)
            page.wait_for_selector("#errorMessage:not(.hidden)", timeout=5000)
            assert "no java source files" in page.inner_text("#errorText").lower()
            assert not page.locator("#resultsSection").is_hidden()

            # Error State 3: Upload Corrupted ZIP
            page.set_input_files("#fileInput", corrupt_zip_path)
            page.wait_for_selector("#errorMessage:not(.hidden)", timeout=5000)
            assert "corrupted" in page.inner_text("#errorText").lower() or "invalid" in page.inner_text("#errorText").lower()
            assert not page.locator("#resultsSection").is_hidden()

            # Clean up temp test files
            for pth in [empty_zip_path, no_java_zip_path, corrupt_zip_path]:
                if os.path.exists(pth):
                    os.remove(pth)

            browser.close()
    finally:
        server.stop()

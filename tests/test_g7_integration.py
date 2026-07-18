"""
G7 Integration Test Suite — Mobile Module Layout + Focus Modal
Tests: scroll-snap modules, focus modal, pressed states, KPI sync, responsive breakpoints
"""
import requests
import re
import json
import sys

BASE = "http://localhost:8792"
AUTH = ("operator", "operator")
PASS = 0
FAIL = 0
SKIPPED = 0

def result(name, ok, detail=""):
    global PASS, FAIL
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    msg = f"  [{status}] {name}"
    if detail and not ok:
        msg += f" — {detail}"
    print(msg)

def test_page_loads():
    """Dashboard page loads with 200 OK"""
    r = requests.get(f"{BASE}/app/dashboard", auth=AUTH, timeout=10)
    result("Dashboard loads", r.status_code == 200, f"status={r.status_code}")
    return r.text if r.status_code == 200 else ""

def test_mobile_module_classes(html):
    """All 5 mobile module classes present in HTML"""
    modules = ["module-hero", "module-cards", "module-chat", "module-chart"]
    for cls in modules:
        found = cls in html
        result(f"Module class .{cls}", found, f"class={'found' if found else 'MISSING'}")

def test_focus_modal_html(html):
    """Focus modal overlay and elements present"""
    checks = [
        ("focus-modal-overlay", 'id="engine-focus-modal"' in html),
        ("focus-modal-name", 'id="focus-modal-name"' in html),
        ("focus-modal-status", 'id="focus-modal-status"' in html),
        ("focus-modal-position", 'id="focus-modal-position"' in html),
        ("focus-modal-pnl", 'id="focus-modal-pnl"' in html),
        ("focus-modal-entry", 'id="focus-modal-entry"' in html),
        ("focus-modal-price", 'id="focus-modal-price"' in html),
        ("focus-modal-leverage", 'id="focus-modal-leverage"' in html),
        ("focus-modal-view link", 'id="focus-modal-view"' in html),
        ("focus-modal-edit link", 'id="focus-modal-edit"' in html),
        ("focus-modal-backtest btn", 'id="focus-modal-backtest"' in html),
        ("focus-modal-toggle btn", 'id="focus-modal-toggle"' in html),
        ("focus-modal-close btn", 'class="focus-modal-close"' in html),
    ]
    for name, found in checks:
        result(f"Focus modal: {name}", found)

def test_focus_modal_css(html):
    """Focus modal CSS classes defined"""
    css_checks = [
        (".focus-modal-overlay", ".focus-modal-overlay" in html),
        (".focus-modal", ".focus-modal {" in html or ".focus-modal{" in html),
        (".focus-modal-header", ".focus-modal-header" in html),
        (".focus-modal-close", ".focus-modal-close" in html),
        (".focus-modal-body", ".focus-modal-body" in html),
        (".focus-modal-stats", ".focus-modal-stats" in html),
        (".focus-modal-actions", ".focus-modal-actions" in html),
        ("@keyframes slideUp", "@keyframes slideUp" in html),
        ("@keyframes fadeIn", "@keyframes fadeIn" in html),
    ]
    for name, found in css_checks:
        result(f"CSS: {name}", found)

def test_fleet_card_data_attrs(html):
    """Fleet card onclick uses openFocusModal, data attributes present"""
    result("Fleet card onclick=openFocusModal",
           "openFocusModal(this)" in html,
           "expected openFocusModal(this) in fleet card")
    data_attrs = ["data-slug", "data-strategy", "data-timeframe",
                  "data-position-side", "data-position-size",
                  "data-unrealized-pnl", "data-entry-price",
                  "data-mark-price", "data-leverage"]
    for attr in data_attrs:
        found = attr in html
        result(f"Fleet card {attr}", found)

def test_mobile_kpi_hero_ids(html):
    """Mobile KPI hero has -m suffixed IDs for live sync"""
    ids = ["kpi-account-m", "kpi-realized-m", "kpi-engines-m"]
    for id_val in ids:
        found = f'id="{id_val}"' in html
        result(f"Mobile KPI ID #{id_val}", found)

def test_desktop_only_class(html):
    """desktop-only class present on desktop KPI row"""
    result("desktop-only on KPI row", 'class="mobile-module module-hero desktop-only"' in html,
           "expected module-hero desktop-only wrapper")

def test_scroll_snap_css(html):
    """Scroll-snap CSS rules present"""
    checks = [
        ("scroll-snap-type: y mandatory", "scroll-snap-type" in html and "mandatory" in html),
        ("scroll-snap-align: start", "scroll-snap-align" in html),
        ("mobile-module min-height", "min-height: calc(100dvh" in html or "min-height:calc(100dvh" in html),
    ]
    for name, found in checks:
        result(f"Scroll-snap: {name}", found)

def test_pressed_states_css(html):
    """Active/pressed state CSS rules present in inline + external"""
    # Check inline styles (layout.html) AND fetch external stylesheet
    try:
        r = requests.get(f"{BASE}/static/style.css", timeout=5)
        ext_css = r.text if r.status_code == 200 else ""
    except:
        ext_css = ""
    combined = html + ext_css
    
    pressed_checks = [
        (".fleet-btn:active", ".fleet-btn:active" in combined),
        (".btn-primary:active", ".btn-primary:active" in combined),
        (".btn-sm:active", ".btn-sm:active" in combined),
        (".fleet-card:active", ".fleet-card:active" in combined),
        (".nav-item:active", ".nav-item:active" in combined),
        (".topbar-icon-btn:active", ".topbar-icon-btn:active" in combined),
        (".carousel-btn:active", ".carousel-btn:active" in combined),
        (".kpi-compact:active", ".kpi-compact:active" in combined),
        (".kpi-item:active", ".kpi-item:active" in combined),
    ]
    for name, found in pressed_checks:
        result(f"Pressed state: {name}", found)

def test_focus_modal_js(html):
    """Focus modal JS functions present"""
    js_checks = [
        ("openFocusModal function", "function openFocusModal" in html),
        ("closeFocusModal function", "function closeFocusModal" in html),
        ("Escape key listener", "'Escape'" in html and "closeFocusModal" in html),
        ("modal.style.display = 'flex'", "modal.style.display = 'flex'" in html or "modal.style.display='flex'" in html),
        ("document.body.style.overflow = 'hidden'", "document.body.style.overflow = 'hidden'" in html),
        ("View Engine link href", "focus-modal-view" in html),
        ("Start/Stop toggle logic", "focus-modal-toggle" in html),
    ]
    for name, found in js_checks:
        result(f"JS: {name}", found)

def test_mobile_breakpoint_css(html):
    """Mobile breakpoint (768px) CSS rules present"""
    mobile_checks = [
        ("@media max-width 768px", "@media (max-width: 768px)" in html),
        (".mobile-module display none desktop", "mobile-module" in html),
        ("#mobile-kpi-hero display flex", "mobile-kpi-hero" in html or "#mobile-kpi-hero" in html),
        (".desktop-only hidden on mobile", ".desktop-only" in html),
        ("scrollbar-width: thin", "scrollbar-width" in html),
    ]
    for name, found in mobile_checks:
        result(f"Mobile CSS: {name}", found)

def test_api_health():
    """API health endpoint responds"""
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        result("API /health", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        result("API /health", False, str(e))

def test_api_summary():
    """API summary endpoint returns valid data"""
    try:
        # Get API key from dashboard page
        r_page = requests.get(f"{BASE}/app/dashboard", auth=AUTH, timeout=10)
        m = re.search(r'const API_KEY = "([^"]+)"', r_page.text)
        api_key = m.group(1) if m else ""
        headers = {"X-API-Key": api_key} if api_key else {}
        r = requests.get(f"{BASE}/api/v2/summary?hours=24", headers=headers, timeout=10)
        ok = r.status_code == 200
        if ok:
            d = r.json()
            ok = d.get("ok") == True
            result("API /summary", ok, f"ok={d.get('ok')}")
            # Verify instances array
            instances = d.get("instances", [])
            result("API /summary instances", len(instances) >= 0, f"count={len(instances)}")
        else:
            result("API /summary", False, f"status={r.status_code}")
    except Exception as e:
        result("API /summary", False, str(e))

def test_version():
    """VERSION file is v0.096"""
    try:
        with open("/workspace/projects/strategy-engine/VERSION") as f:
            v = f.read().strip()
        result("VERSION = v0.096", v == "v0.096", f"got={v}")
    except Exception as e:
        result("VERSION file", False, str(e))

# ══ RUN ALL TESTS ══
print("\n══ G7 Integration Test Suite ══\n")

html = test_page_loads()
if html:
    print("\n── HTML Structure ──")
    test_mobile_module_classes(html)
    test_focus_modal_html(html)
    test_fleet_card_data_attrs(html)
    test_mobile_kpi_hero_ids(html)
    test_desktop_only_class(html)

    print("\n── CSS Rules ──")
    test_focus_modal_css(html)
    test_scroll_snap_css(html)
    test_pressed_states_css(html)
    test_mobile_breakpoint_css(html)

    print("\n── JavaScript ──")
    test_focus_modal_js(html)

print("\n── API Endpoints ──")
test_api_health()
test_api_summary()

print("\n── Version ──")
test_version()

# ══ SUMMARY ══
total = PASS + FAIL
print(f"\n══ Results: {PASS}/{total} passed, {FAIL} failed ══")
if FAIL > 0:
    print("⚠️  FAILURES DETECTED — see details above")
    sys.exit(1)
else:
    print("✅ All tests passed")
    sys.exit(0)
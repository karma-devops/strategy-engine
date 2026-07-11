# Fund Manager — Test Suite

## Purpose

This test suite verifies security, integrity, and robustness **before production**.

These are not "happy path" tests. These are **attack vectors** and **edge cases** that will murder you in production if untested.

---

## Installation

```bash
# Create test venv
python -m venv venv-test
source venv-test/bin/activate  # Linux/Mac
# or: venv-test\Scripts\activate  # Windows

# Install test dependencies
pip install pytest pytest-asyncio httpx
```

---

## Running Tests

```bash
# Run all tests
pytest tests/test_hardening.py -v

# Run only P0 critical vuln tests
pytest tests/test_hardening.py -v -m p0

# Run only high concern tests
pytest tests/test_hardening.py -v -m high

# Run specific test
pytest tests/test_hardening.py -v -k "rate_limit"

# Run with coverage
pytest tests/test_hardening.py -v --cov=app --cov-report=html

# Run and stop on first failure
pytest tests/test_hardening.py -v -x
```

---

## Test Categories

| Marker | Purpose | Must Pass Before |
|--------|---------|------------------|
| `p0` | Critical vulns | Any live capital |
| `high` | High concerns | Production deploy |
| `edge` | Edge cases | Production deploy |
| `integration` | Full flows | Production deploy |

---

## Interpreting Results

| Result | Action |
|--------|--------|
| **All P0 tests pass** | Safe to proceed with dry-run testing |
| **Any P0 test fails** | Fix before any live capital |
| **High tests skipped** | Feature not implemented yet (acceptable during dev) |
| **High tests fail** | Fix before production deploy |
| **Edge tests fail** | Document as known limitation, fix ASAP |

---

## Adding New Tests

1. Add test to appropriate class (P0, High, Edge, Integration)
2. Add marker decorator (`@pytest.mark.p0`, etc.)
3. Include "WHAT THIS PROVES" and "WHY IT MATTERS" docstrings
4. Update this README if test category changes

---

## CI/CD Integration

```yaml
# Example GitHub Actions snippet
- name: Run Hardening Tests
  run: |
    pytest tests/test_hardening.py -v -m p0 --tb=short
```

---

## Notes

- Tests are written for `localhost:8788` by default
- Adjust `BASE_URL` in `test_hardening.py` for different environments
- Tests assume `TEST_API_KEY` is configured in test environment
- Clean up test engines after each run (fixtures handle most of this)

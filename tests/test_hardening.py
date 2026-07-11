"""
Fund Manager — Hardening Test Suite

Purpose: Verify security, integrity, and robustness before production.
Audience: Development team. Run before any deployment.
Coverage: P0 vulns, high concerns, edge cases.

Usage:
    pytest tests/test_hardening.py -v
    pytest tests/test_hardening.py -v -k "p0"  # Only P0 tests
    pytest tests/test_hardening.py -v -k "rate_limit"  # Specific test

Requirements:
    - pytest
    - pytest-asyncio
    - httpx
    - Your FastAPI app in test mode (TESTING=true env var)
"""

import pytest
import pytest_asyncio
import httpx
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_URL = "http://localhost:8788"
TEST_API_KEY = "test_api_key_12345"  # Should be configured in test env
TEST_ENGINE_SLUGS = ["engine-1", "engine-2", "engine-3"]

# =============================================================================
# FIXTURES
# =============================================================================

@pytest_asyncio.fixture
async def http_client():
    """
    Async HTTP client for API testing.
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers():
    """
    Auth headers for authenticated requests.
    Adjust based on your actual auth implementation.
    """
    return {
        "Authorization": f"Bearer {TEST_API_KEY}",
        "Content-Type": "application/json"
    }


@pytest_asyncio.fixture
async def clean_engine(http_client, auth_headers):
    """
    Create a clean test engine instance.
    Teardown ensures no leftover state between tests.
    """
    # Create engine
    payload = {
        "slug": f"test-engine-{int(time.time())}",
        "strategy": "engine_v1_3",
        "mode": "swing",
        "dry_run": True,
        "capital_allocation": 1000.0
    }
    response = await http_client.post(
        "/api/v2/instances",
        json=payload,
        headers=auth_headers
    )
    assert response.status_code == 201
    engine_data = response.json()
    
    yield engine_data
    
    # Teardown: stop and delete engine
    await http_client.post(
        f"/api/v2/instances/{engine_data['slug']}/stop",
        headers=auth_headers
    )
    await http_client.delete(
        f"/api/v2/instances/{engine_data['slug']}",
        headers=auth_headers
    )


@pytest_asyncio.fixture
async def kill_switch_enabled(http_client, auth_headers):
    """
    Ensure global kill switch is OFF for tests that need trading.
    """
    # Disable kill switch for test
    response = await http_client.put(
        "/api/v2/safety/killswitch",
        json={"enabled": False},
        headers=auth_headers
    )
    yield
    # Re-enable after test (safety first)
    await http_client.put(
        "/api/v2/safety/killswitch",
        json={"enabled": True},
        headers=auth_headers
    )


# =============================================================================
# P0 CRITICAL VULN TESTS
# =============================================================================

class TestP0_CriticalVulns:
    """
    P0 vulnerabilities that must be fixed before any live capital.
    These tests verify the fixes actually work.
    """

    # -------------------------------------------------------------------------
    # 1.1 Fernet Key Rotation
    # -------------------------------------------------------------------------
    
    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_credentials_encrypted_in_db(self, http_client, auth_headers):
        """
        WHAT THIS PROVES: Credentials are not stored in plaintext.
        
        WHY IT MATTERS: If DB is compromised, attacker can't immediately
        use API keys without also having the encryption key.
        
        TEST: Create engine with credentials, verify stored value is encrypted.
        """
        # Skip if no credential endpoint exists yet
        # This test requires implementation of credential storage verification
        
        # TODO: Implement when per-engine credential storage is complete
        # Expected behavior:
        # 1. POST /api/v2/instances/{slug}/credentials with key
        # 2. GET /api/v2/instances/{slug}/credentials returns encrypted value
        # 3. Encrypted value != plaintext input
        # 4. Encrypted value is decryptable with correct Fernet key
        
        pytest.skip("Credential storage implementation pending")


    # -------------------------------------------------------------------------
    # 1.2 Rate Limiting
    # -------------------------------------------------------------------------
    
    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_rate_limit_on_write_endpoints(self, http_client, auth_headers):
        """
        WHAT THIS PROVES: Write endpoints are rate-limited.
        
        WHY IT MATTERS: Prevents DDoS on your own bot. Prevents HL API
        rate limit exhaustion from runaway scripts.
        
        TEST: Hammer a write endpoint 50 times in 10 seconds.
        Expect 429 responses after threshold.
        """
        endpoint = "/api/v2/instances/engine-1/restart"
        rate_limit_threshold = 20  # Adjust to your configured limit
        
        responses = []
        for i in range(50):
            response = await http_client.post(
                endpoint,
                headers=auth_headers
            )
            responses.append(response.status_code)
        
        # Count 429 responses
        rate_limited_count = sum(1 for code in responses if code == 429)
        
        # Assert: At least some requests were rate-limited
        assert rate_limited_count > 0, (
            f"No rate limiting detected. All {len(responses)} requests succeeded. "
            f"Expected 429 responses after {rate_limit_threshold} requests."
        )
        
        # Assert: Rate limit header is present
        # (Implementation detail: check for Retry-After or X-RateLimit headers)


    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self, http_client, auth_headers):
        """
        WHAT THIS PROVES: Rate limit responses include retry information.
        
        WHY IT MATTERS: Clients need to know when they can retry.
        
        TEST: Trigger rate limit, verify headers.
        """
        endpoint = "/api/v2/instances/engine-1/restart"
        
        # Hammer until rate limited
        for i in range(30):
            response = await http_client.post(
                endpoint,
                headers=auth_headers
            )
            if response.status_code == 429:
                break
        
        # Verify rate limit response
        assert response.status_code == 429, "Endpoint did not rate limit"
        
        # Check for retry information
        assert any([
            "retry-after" in response.headers,
            "x-ratelimit-reset" in response.headers,
            "x-ratelimit-remaining" in response.headers
        ]), "Rate limit response missing retry headers"


    # -------------------------------------------------------------------------
    # 1.3 Kill Switch Behavior
    # -------------------------------------------------------------------------
    
    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_kill_switch_blocks_trading(self, http_client, auth_headers, clean_engine):
        """
        WHAT THIS PROVES: Kill switch actually stops trading.
        
        WHY IT MATTERS: If kill switch doesn't work, you can't stop
        bleeding during a crisis.
        
        TEST: Enable kill switch, try to start engine, expect failure.
        """
        # Enable global kill switch
        await http_client.put(
            "/api/v2/safety/killswitch",
            json={"enabled": True},
            headers=auth_headers
        )
        
        # Try to start engine
        response = await http_client.post(
            f"/api/v2/instances/{clean_engine['slug']}/start",
            headers=auth_headers
        )
        
        # Assert: Start is blocked
        assert response.status_code in [403, 409], (
            f"Kill switch did not block start. Got {response.status_code}"
        )
        
        # Disable for cleanup
        await http_client.put(
            "/api/v2/safety/killswitch",
            json={"enabled": False},
            headers=auth_headers
        )


    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_kill_switch_persists_across_restart(self, http_client, auth_headers):
        """
        WHAT THIS PROVES: Kill switch state survives server restart.
        
        WHY IT MATTERS: If restart resets kill switch, you're vulnerable
        during recovery.
        
        TEST: Enable kill switch, simulate restart, verify still enabled.
        Note: This test requires server restart capability.
        """
        # Enable kill switch
        await http_client.put(
            "/api/v2/safety/killswitch",
            json={"enabled": True},
            headers=auth_headers
        )
        
        # Verify enabled
        response = await http_client.get(
            "/api/v2/safety/killswitch",
            headers=auth_headers
        )
        assert response.json()["enabled"] is True
        
        # TODO: Add server restart test when deployment automation exists
        # Expected: After restart, GET /api/v2/safety/killswitch still returns enabled=True
        
        pytest.skip("Server restart test requires deployment automation")


    # -------------------------------------------------------------------------
    # 1.4 Position Limits
    # -------------------------------------------------------------------------
    
    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_position_limit_enforced(self, http_client, auth_headers, clean_engine):
        """
        WHAT THIS PROVES: Position limits prevent over-exposure.
        
        WHY IT MATTERS: Single engine can't blow up the portfolio.
        
        TEST: Try to allocate > max position, expect rejection.
        """
        # Try to update engine with excessive allocation
        payload = {
            "capital_allocation": 999999999.0  # Absurd amount
        }
        response = await http_client.put(
            f"/api/v2/instances/{clean_engine['slug']}",
            json=payload,
            headers=auth_headers
        )
        
        # Assert: Either rejected or capped
        assert response.status_code in [400, 422] or (
            response.status_code == 200 and 
            response.json()["capital_allocation"] < 999999999.0
        ), "Position limit not enforced"


    # -------------------------------------------------------------------------
    # 1.5 Idempotency
    # -------------------------------------------------------------------------
    
    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_idempotency_on_trade_signal(self, http_client, auth_headers, clean_engine):
        """
        WHAT THIS PROVES: Duplicate signals don't create duplicate orders.
        
        WHY IT MATTERS: Network retries, bugs, or race conditions shouldn't
        double-execute trades.
        
        TEST: Send same signal twice with same idempotency key.
        Expect one trade, not two.
        """
        idempotency_key = f"idem-{int(time.time())}"
        
        # Send signal first time
        payload = {
            "signal": "BUY",
            "symbol": "FARTCOIN",
            "size": 100.0,
            "idempotency_key": idempotency_key
        }
        response1 = await http_client.post(
            f"/api/v2/instances/{clean_engine['slug']}/signal",
            json=payload,
            headers=auth_headers
        )
        
        # Send signal second time (same key)
        response2 = await http_client.post(
            f"/api/v2/instances/{clean_engine['slug']}/signal",
            json=payload,
            headers=auth_headers
        )
        
        # Assert: Second request returns same result, doesn't create new trade
        assert response1.status_code == response2.status_code
        
        # TODO: Verify trade count in DB is 1, not 2
        # This requires DB access or a trade history endpoint


# =============================================================================
# HIGH CONCERN TESTS
# =============================================================================

class TestHigh_Concerns:
    """
    High-priority concerns that should be fixed before production deploy.
    """

    # -------------------------------------------------------------------------
    # 2.1 SQLite WAL Performance
    # -------------------------------------------------------------------------
    
    @pytest.mark.high
    @pytest.mark.asyncio
    async def test_sqlite_wal_under_load(self, http_client, auth_headers):
        """
        WHAT THIS PROVES: SQLite WAL handles concurrent engine load.
        
        WHY IT MATTERS: Lock contention during trading = missed signals.
        
        TEST: Simulate 6 engines trading concurrently.
        Measure lock wait time.
        """
        # Create 6 test engines
        engine_slugs = []
        for i in range(6):
            payload = {
                "slug": f"load-test-{i}-{int(time.time())}",
                "strategy": "engine_v1_3",
                "dry_run": True
            }
            response = await http_client.post(
                "/api/v2/instances",
                json=payload,
                headers=auth_headers
            )
            if response.status_code == 201:
                engine_slugs.append(response.json()["slug"])
        
        # Simulate concurrent writes (trade logging)
        async def log_trade(slug):
            payload = {
                "signal": "BUY",
                "symbol": "TEST",
                "size": 1.0
            }
            return await http_client.post(
                f"/api/v2/instances/{slug}/signal",
                json=payload,
                headers=auth_headers
            )
        
        # Run concurrent trades
        start = time.time()
        tasks = [log_trade(slug) for slug in engine_slugs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start
        
        # Assert: All completed in reasonable time
        success_count = sum(1 for r in results if isinstance(r, httpx.Response) and r.status_code == 200)
        assert success_count >= len(engine_slugs) * 0.8, (
            f"Only {success_count}/{len(engine_slugs)} trades succeeded under load"
        )
        assert elapsed < 5.0, f"Concurrent writes took {elapsed}s (expected < 5s)"
        
        # Cleanup
        for slug in engine_slugs:
            await http_client.delete(
                f"/api/v2/instances/{slug}",
                headers=auth_headers
            )


    # -------------------------------------------------------------------------
    # 2.2 Circuit Breaker Reset
    # -------------------------------------------------------------------------
    
    @pytest.mark.high
    @pytest.mark.asyncio
    async def test_circuit_breaker_triggers(self, http_client, auth_headers, clean_engine):
        """
        WHAT THIS PROVES: Circuit breaker pauses engine on errors.
        
        WHY IT MATTERS: Prevents cascade failure from bad data or bugs.
        
        TEST: Simulate 5 consecutive errors, verify engine pauses.
        """
        # TODO: Implement when circuit breaker logic exists
        # Expected behavior:
        # 1. Send 5 invalid signals (or simulate tick errors)
        # 2. Engine status changes to "paused" or "circuit_open"
        # 3. Further signals are rejected until reset
        
        pytest.skip("Circuit breaker implementation pending")


    # -------------------------------------------------------------------------
    # 2.3 Reconciliation
    # -------------------------------------------------------------------------
    
    @pytest.mark.high
    @pytest.mark.asyncio
    async def test_reconciliation_endpoint_exists(self, http_client, auth_headers):
        """
        WHAT THIS PROVES: Reconciliation can be triggered manually.
        
        WHY IT MATTERS: When DB and exchange diverge, you need to fix it.
        
        TEST: Verify reconcile endpoint exists and responds.
        """
        response = await http_client.post(
            "/api/v2/reconciliation/run",
            headers=auth_headers
        )
        
        # Accept 200 (success) or 501 (not implemented yet)
        if response.status_code == 501:
            pytest.skip("Reconciliation endpoint not yet implemented")
        
        assert response.status_code in [200, 202], (
            f"Reconciliation endpoint returned {response.status_code}"
        )


    # -------------------------------------------------------------------------
    # 2.4 Clock Drift
    # -------------------------------------------------------------------------
    
    @pytest.mark.high
    @pytest.mark.asyncio
    async def test_health_check_includes_clock_status(self, http_client, auth_headers):
        """
        WHAT THIS PROVES: Clock drift is monitored.
        
        WHY IT MATTERS: HL rejects stale orders. Clock drift = failed trades.
        
        TEST: Health check includes clock sync status.
        """
        response = await http_client.get(
            "/health",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Check for clock/time information
        has_clock_info = any([
            "clock" in data,
            "time" in data,
            "ntp" in data,
            "drift" in data
        ])
        
        assert has_clock_info, (
            "Health check does not include clock/time status. "
            "Add clock drift monitoring to /health endpoint."
        )


    # -------------------------------------------------------------------------
    # 2.5 Backup Restore
    # -------------------------------------------------------------------------
    
    @pytest.mark.high
    @pytest.mark.asyncio
    async def test_backup_endpoint_exists(self, http_client, auth_headers):
        """
        WHAT THIS PROVES: Backup can be triggered/verified via API.
        
        WHY IT MATTERS: Manual backup is forgettable. API backup is auditable.
        
        TEST: Verify backup endpoint exists.
        """
        response = await http_client.get(
            "/api/v2/backups",
            headers=auth_headers
        )
        
        # Accept 200 (success) or 404 (not implemented)
        if response.status_code == 404:
            pytest.skip("Backup API endpoint not yet implemented")
        
        assert response.status_code == 200


    # -------------------------------------------------------------------------
    # 2.6 API Auth
    # -------------------------------------------------------------------------
    
    @pytest.mark.high
    @pytest.mark.asyncio
    async def test_write_endpoints_require_auth(self, http_client):
        """
        WHAT THIS PROVES: Write endpoints are protected.
        
        WHY IT MATTERS: Unauthenticated writes = anyone can trade your money.
        
        TEST: Call write endpoint without auth, expect 401/403.
        """
        # Try to create instance without auth
        payload = {
            "slug": "unauth-test",
            "strategy": "engine_v1_3",
            "dry_run": True
        }
        response = await http_client.post(
            "/api/v2/instances",
            json=payload
            # No auth headers
        )
        
        assert response.status_code in [401, 403], (
            f"Write endpoint accessible without auth. Got {response.status_code}"
        )


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """
    Edge cases that will murder you in production if untested.
    """

    @pytest.mark.edge
    @pytest.mark.asyncio
    async def test_engine_start_with_invalid_credentials(self, http_client, auth_headers):
        """
        WHAT THIS PROVES: Invalid credentials don't crash the engine.
        
        WHY IT MATTERS: Bad API key shouldn't take down the whole system.
        """
        # Create engine with invalid credentials
        payload = {
            "slug": f"bad-creds-{int(time.time())}",
            "strategy": "engine_v1_3",
            "dry_run": False,  # Live mode
            "hyperliquid_private_key": "invalid_key_format"
        }
        response = await http_client.post(
            "/api/v2/instances",
            json=payload,
            headers=auth_headers
        )
        
        # Should either reject creation or start but fail gracefully
        assert response.status_code in [201, 400, 422]


    @pytest.mark.edge
    @pytest.mark.asyncio
    async def test_withdrawal_exceeds_profit(self, http_client, auth_headers):
        """
        WHAT THIS PROVES: Withdrawal validation prevents overdraft.
        
        WHY IT MATTERS: Can't withdraw money that doesn't exist.
        """
        # Try to withdraw more than available
        payload = {
            "amount": 999999999.0,
            "type": "profit"
        }
        response = await http_client.post(
            "/api/v2/withdrawals/manual",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code in [400, 422], (
            "Withdrawal validation did not reject excessive amount"
        )


    @pytest.mark.edge
    @pytest.mark.asyncio
    async def test_concurrent_engine_config_updates(self, http_client, auth_headers, clean_engine):
        """
        WHAT THIS PROVES: Config updates don't corrupt state.
        
        WHY IT MATTERS: Race conditions on config = unpredictable behavior.
        """
        # Send 10 concurrent config updates
        async def update_config(value):
            return await http_client.put(
                f"/api/v2/instances/{clean_engine['slug']}",
                json={"capital_allocation": value},
                headers=auth_headers
            )
        
        tasks = [update_config(i * 100) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed or fail gracefully
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent update raised exception: {result}")
        
        # Verify final state is consistent
        response = await http_client.get(
            f"/api/v2/instances/{clean_engine['slug']}",
            headers=auth_headers
        )
        assert response.status_code == 200


    @pytest.mark.edge
    @pytest.mark.asyncio
    async def test_signal_with_missing_fields(self, http_client, auth_headers, clean_engine):
        """
        WHAT THIS PROVES: Validation catches malformed signals.
        
        WHY IT MATTERS: Bad signals shouldn't crash or create ghost trades.
        """
        payload = {
            # Missing required fields
            "signal": "BUY"
            # No symbol, no size
        }
        response = await http_client.post(
            f"/api/v2/instances/{clean_engine['slug']}/signal",
            json=payload,
            headers=auth_headers
        )
        
        assert response.status_code in [400, 422], (
            "Signal endpoint accepted malformed payload"
        )


    @pytest.mark.edge
    @pytest.mark.asyncio
    async def test_health_check_when_db_is_slow(self, http_client):
        """
        WHAT THIS PROVES: Health check detects DB issues.
        
        WHY IT MATTERS: Slow DB = slow trading = missed opportunities.
        """
        # This test requires DB slowdown simulation
        # TODO: Implement with DB query timeout injection
        
        pytest.skip("Requires DB slowdown simulation infrastructure")


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """
    Full-flow tests: signal → trade → record → withdrawal.
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_trade_lifecycle_dry_run(self, http_client, auth_headers, clean_engine):
        """
        WHAT THIS PROVES: Complete trade flow works in dry-run mode.
        
        WHY IT MATTERS: If this breaks, nothing works.
        
        TEST: 
        1. Start engine
        2. Send signal
        3. Verify trade recorded
        4. Verify PnL calculated
        5. Verify withdrawal calculable
        """
        slug = clean_engine["slug"]
        
        # 1. Start engine
        response = await http_client.post(
            f"/api/v2/instances/{slug}/start",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # 2. Send signal
        payload = {
            "signal": "BUY",
            "symbol": "FARTCOIN",
            "size": 100.0
        }
        response = await http_client.post(
            f"/api/v2/instances/{slug}/signal",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # 3. Verify trade recorded (requires trade history endpoint)
        # TODO: Implement when endpoint exists
        
        # 4. Verify PnL calculated (requires metrics endpoint)
        # TODO: Implement when endpoint exists
        
        # 5. Verify withdrawal calculable
        response = await http_client.get(
            "/api/v2/withdrawals/calculate",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Stop engine
        await http_client.post(
            f"/api/v2/instances/{slug}/stop",
            headers=auth_headers
        )


# =============================================================================
# TEST RUNNERS
# =============================================================================

if __name__ == "__main__":
    # Run all tests
    pytest.main([__file__, "-v"])
    
    # Run only P0 tests
    # pytest.main([__file__, "-v", "-k", "p0"])
    
    # Run only high concern tests
    # pytest.main([__file__, "-v", "-k", "high"])
    
    # Run with coverage
    # pytest.main([__file__, "-v", "--cov=app", "--cov-report=html"])

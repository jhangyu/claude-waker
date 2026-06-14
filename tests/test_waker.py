import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import waker
from reset_time_fetcher import ClaudeResetTimeError


class WakeOutputParsingTests(unittest.TestCase):
    def test_parse_success_output(self):
        parsed = waker.parse_wake_subprocess_output(
            "\n".join(
                [
                    "COST_USD:0.001",
                    "SESSION_ID:session-123",
                    "MODEL_NAME:haiku",
                    "SUCCESS:ResultMessage",
                ]
            ),
            "",
        )

        self.assertEqual(parsed["status"], "success")
        self.assertEqual(parsed["success_type"], "ResultMessage")
        self.assertEqual(parsed["cost_usd"], "0.001")
        self.assertEqual(parsed["session_id"], "session-123")
        self.assertEqual(parsed["model_name"], "haiku")

    def test_parse_budget_error_details(self):
        parsed = waker.parse_wake_subprocess_output(
            "\n".join(
                [
                    "CLAUDE_ERROR:error_max_budget_usd",
                    "BUDGET_DETAILS:max_budget_usd=0.02, reported_cost_usd=0.031, source=claude-cli",
                ]
            ),
            "",
        )

        self.assertEqual(parsed["status"], "fail")
        self.assertEqual(
            parsed["error_msg"],
            "error_max_budget_usd (max_budget_usd=0.02, reported_cost_usd=0.031, source=claude-cli)",
        )

    def test_parse_timeout_output(self):
        parsed = waker.parse_wake_subprocess_output("TIMEOUT:響應超時", "")

        self.assertEqual(parsed["status"], "timeout")

    def test_build_wake_worker_payload(self):
        payload = waker.build_wake_worker_payload(
            "oauth-token",
            "wake prompt",
            "0.02",
            "haiku",
            "/path/to/claude",
        )

        self.assertEqual(payload["oauth_token"], "oauth-token")
        self.assertEqual(payload["wake_prompt"], "wake prompt")
        self.assertEqual(payload["wake_max_budget_usd"], 0.02)
        self.assertEqual(payload["wake_model"], "haiku")
        self.assertEqual(payload["claude_cli_path"], "/path/to/claude")
        self.assertEqual(payload["command_timeout_s"], waker.WAKE_COMMAND_TIMEOUT_SECONDS)


class WakeGateTests(unittest.TestCase):
    def setUp(self):
        self.original_fetch_reset_times = waker.fetch_reset_times

    def tearDown(self):
        waker.fetch_reset_times = self.original_fetch_reset_times

    def test_future_reset_time_skips_wake(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        waker.fetch_reset_times = lambda *_args, **_kwargs: SimpleNamespace(
            five_hour_resets_at=future.isoformat()
        )

        self.assertFalse(waker.should_wake_account("test-account", "session-key"))

    def test_missing_reset_time_wakes(self):
        waker.fetch_reset_times = lambda *_args, **_kwargs: SimpleNamespace(
            five_hour_resets_at=None
        )

        self.assertTrue(waker.should_wake_account("test-account", "session-key"))

    def test_api_error_wakes(self):
        def raise_error(*_args, **_kwargs):
            raise ClaudeResetTimeError("expired")

        waker.fetch_reset_times = raise_error

        self.assertTrue(waker.should_wake_account("test-account", "session-key"))

    def test_placeholder_token_is_not_configured(self):
        self.assertFalse(waker.has_configured_token(""))
        self.assertFalse(waker.has_configured_token("your-oauth-token-here-1"))
        self.assertTrue(waker.has_configured_token("sk-ant-oat03-real"))


if __name__ == "__main__":
    unittest.main()

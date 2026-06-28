from datetime import datetime
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.health import basic_health_payload, detailed_health_payload


class HealthPayloadTests(unittest.TestCase):
    def test_basic_health_payload_has_valid_utc_timestamp(self):
        payload = basic_health_payload()

        self.assertEqual(payload["status"], "healthy")
        parsed = datetime.fromisoformat(payload["timestamp"])
        self.assertIsNotNone(parsed.tzinfo)

    def test_detailed_health_payload_reports_degraded_dependencies(self):
        payload = detailed_health_payload(
            database_ok=True,
            cache_ok=False,
            version="2.0.0",
            environment="test",
        )

        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["services"]["database"], "healthy")
        self.assertEqual(payload["services"]["cache"], "unhealthy")
        self.assertEqual(payload["version"], "2.0.0")
        self.assertEqual(payload["environment"], "test")


if __name__ == "__main__":
    unittest.main()

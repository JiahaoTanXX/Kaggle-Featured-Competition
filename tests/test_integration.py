from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kaggle_environments import make


class EnvironmentIntegrationTests(unittest.TestCase):
    def test_agent_completes_short_match(self):
        env = make("kaggriculture", configuration={"episodeSteps": 48, "seed": 7}, debug=True)
        env.run([str(ROOT / "main.py"), "starter"])
        final = env.steps[-1]
        self.assertEqual([state.status for state in final], ["DONE", "DONE"])
        self.assertEqual(len(env.steps), 48)


if __name__ == "__main__":
    unittest.main()

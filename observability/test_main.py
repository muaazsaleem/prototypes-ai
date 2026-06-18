import unittest
from main import run_observability_pipeline, USER_PROFILES

class TestObservabilityPipeline(unittest.TestCase):
    def test_pipeline_execution_free_tier(self):
        # Choose Bob's profile
        bob_profile = USER_PROFILES[0]
        query = "Why are quantum computers faster than classical computers? Keep it brief."
        
        result = run_observability_pipeline(bob_profile, query)
        
        # Verify schema elements in return payload
        self.assertIn("trace_id", result)
        self.assertIn("raw_query", result)
        self.assertIn("user_profile", result)
        self.assertIn("metrics", result)
        self.assertIn("steps", result)
        
        # Check metrics details
        metrics = result["metrics"]
        self.assertIn("prompt_tokens", metrics)
        self.assertIn("completion_tokens", metrics)
        self.assertIn("total_tokens", metrics)
        self.assertIn("cost_usd", metrics)
        self.assertIn("latency", metrics)
        
        # Verify step list structure
        steps = result["steps"]
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0]["name"], "Query Refinement")
        self.assertEqual(steps[1]["name"], "Database Retrieval")
        self.assertEqual(steps[2]["name"], "Response Synthesis")

if __name__ == "__main__":
    unittest.main()

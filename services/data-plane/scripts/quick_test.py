"""Quick test of the fixed API test only."""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env = os.environ.copy()
env["PYTHONPATH"] = "."

# Just run the API health tests (the one that was fixed)
result = subprocess.run([
    sys.executable, "-m", "pytest",
    "tests/test_api_health.py::test_invalid_service_key_rejected",
    "-v", "--tb=short",
], env=env, capture_output=False)
print(f"\nExit code: {result.returncode}")
sys.exit(result.returncode)

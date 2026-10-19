"""Quick test of the fixed validation error test only."""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env = os.environ.copy()
env["PYTHONPATH"] = "."

result = subprocess.run([
    sys.executable, "-m", "pytest",
    "tests/test_prod_hardening.py::test_validation_error_for_missing_identifiers",
    "-v", "--tb=short",
], env=env, capture_output=False)
print(f"\nExit code: {result.returncode}")
sys.exit(result.returncode)

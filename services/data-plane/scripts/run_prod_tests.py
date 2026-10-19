"""Run production hardening tests."""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env = os.environ.copy()
env["PYTHONPATH"] = "."

result = subprocess.run([
    sys.executable, "-m", "pytest",
    "tests/test_prod_hardening.py",
    "tests/test_api_health.py",
    "tests/test_seed_determinism.py",
    "tests/test_bloom_index.py",
    "tests/test_attack_masking.py",
    "tests/test_planner.py",
    "tests/test_retention_vault.py",
    "tests/test_ghost_embedding.py",
    "tests/test_pii_redaction.py",
    "tests/test_idempotency.py",
    "-v",
    "--tb=short",
    "-q",
], env=env, capture_output=False)
sys.exit(result.returncode)

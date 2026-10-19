"""Quick import verification script."""
import sys

errors = []

packages = [
    ("fastapi", "fastapi"),
    ("pydantic", "pydantic"),
    ("structlog", "structlog"),
    ("faker", "faker"),
    ("pybloom_live", "pybloom_live"),
    ("redis", "redis"),
    ("cryptography", "cryptography"),
    ("httpx", "httpx"),
    ("tenacity", "tenacity"),
    ("orjson", "orjson"),
]

for import_name, package_name in packages:
    try:
        __import__(import_name)
        print(f"  ✓  {package_name}")
    except ImportError as e:
        print(f"  ✗  {package_name}: {e}")
        errors.append(package_name)

# Heavier packages (may not be installed yet)
heavy = [
    ("sqlalchemy", "sqlalchemy"),
    ("pyarrow", "pyarrow"),
    ("boto3", "boto3"),
    ("psycopg", "psycopg"),
    ("pytest", "pytest"),
]

print("\nHeavy packages:")
for import_name, package_name in heavy:
    try:
        __import__(import_name)
        print(f"  ✓  {package_name}")
    except ImportError as e:
        print(f"  ✗  {package_name}: {e}")

if errors:
    print(f"\nMissing: {errors}")
    sys.exit(1)
else:
    print("\nCore packages OK")

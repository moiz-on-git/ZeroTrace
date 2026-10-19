$env:PYTHONPATH = "."
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
python -m pytest tests/test_seed_determinism.py tests/test_bloom_index.py tests/test_attack_masking.py tests/test_planner.py tests/test_retention_vault.py tests/test_ghost_embedding.py -v --tb=short 2>&1
Write-Host "EXIT_CODE: $LASTEXITCODE"

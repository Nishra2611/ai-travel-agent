# Verify Day 2 & Day 3 checks for ai-travel-agent
# Usage: Open PowerShell, navigate to workspace root and run:
#   pwsh -ExecutionPolicy Bypass -File .\ai-travel-agent\scripts\verify_day2_day3.ps1

set -e

function run {
    Write-Host "\n==> $($args[0])" -ForegroundColor Cyan
    iex $args[1]
}

# 1) Git: stash WIP, checkout develop, pull
run "stash WIP (safe)" "git -C 'ai-travel-agent' stash push -u -m 'wip-before-develop' || echo 'stash skipped'"
run "checkout develop" "git -C 'ai-travel-agent' checkout develop"
run "pull develop" "git -C 'ai-travel-agent' pull origin develop"

# 2) Ensure venv / install deps
run "poetry install" "cd 'ai-travel-agent'; poetry install --no-interaction || echo 'poetry install failed or offline'"

# 3) Lint: ruff (auto-fix then check)
run "ruff --fix" "cd 'ai-travel-agent'; poetry run ruff check . --fix || echo 'ruff --fix failed'"
run "ruff check" "cd 'ai-travel-agent'; poetry run ruff check ."

# 4) Clear mypy cache then run mypy
run "remove mypy cache" "cd 'ai-travel-agent'; if (Test-Path '.mypy_cache') { Remove-Item -Recurse -Force .mypy_cache; Write-Host '.mypy_cache removed' }
"
run "mypy" "cd 'ai-travel-agent'; poetry run mypy src/ || echo 'mypy reported errors or failed (see output above)'
"

# 5) Start Ollama server in background (separate process)
Write-Host "\n==> Starting Ollama server in background (if installed)..." -ForegroundColor Cyan
Start-Process -FilePath ollama -ArgumentList 'serve' -WindowStyle Hidden -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 6) Ollama model check & pull if missing
run "ollama list" "ollama list"
run "pull llama3.2 if missing" "if (-not (ollama list | Select-String 'llama3.2')) { Write-Host 'Pulling llama3.2 (may take long and needs disk space)'; ollama pull llama3.2 } else { Write-Host 'llama3.2 already present' }"

# 7) .env check (use helper to avoid quoting issues)
run ".env check" "cd 'ai-travel-agent'; poetry run python scripts/check_env.py"

# 8) Parser demo
run "demo_parser" "cd 'ai-travel-agent'; poetry run python scripts/demo_parser.py"

# 9) Unit tests (parser, supervisor, nodes)
run "pytest: preference_parser" "cd 'ai-travel-agent'; poetry run pytest tests/unit/test_preference_parser.py -q || echo 'preference_parser tests failed or missing'"
run "pytest: supervisor" "cd 'ai-travel-agent'; poetry run pytest tests/unit/test_supervisor.py -q || echo 'supervisor tests failed or missing'"
run "nodes import check" "cd 'ai-travel-agent'; poetry run python -c \"from ai_travel_agent.agents.nodes import *; print('OK')\" || echo 'nodes import failed'"
run "pytest: nodes" "cd 'ai-travel-agent'; poetry run pytest tests/unit/test_nodes.py -q || echo 'nodes tests failed or missing'"

# 10) Day 3: build graph, run demo agent, viz, integration tests
run "build graph" "cd 'ai-travel-agent'; poetry run python -m ai_travel_agent.agents.graph || echo 'graph build failed'"
run "demo_agent" "cd 'ai-travel-agent'; poetry run python scripts/demo_agent.py || echo 'demo_agent failed'"
run "demo_graph_viz" "cd 'ai-travel-agent'; poetry run python scripts/demo_graph_viz.py || echo 'demo_graph_viz failed'"
run "integration tests" "cd 'ai-travel-agent'; poetry run pytest tests/integration/test_graph_integration.py -q || echo 'integration tests failed or missing'"

# 11) Final full checks
run "final ruff" "cd 'ai-travel-agent'; poetry run ruff check ."
run "final mypy" "cd 'ai-travel-agent'; poetry run mypy src/ || echo 'final mypy failed or errored'"
run "full pytest" "cd 'ai-travel-agent'; poetry run pytest || echo 'some tests failed or missing'"

Write-Host "\nVerification script finished. Review output above for any failures." -ForegroundColor Green

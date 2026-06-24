# ai-travel-agent Verification TODO

## Step 1 — Repo sync
- [x] `git status` (develop up to date)
- [x] `git pull origin develop`

## Step 2 — Dependency/quality baseline
- [x] `poetry run ruff check .` (pass)
- [ ] `poetry run mypy src/` (currently running / needs pass)

## Step 3 — Fix import/package installation issue
- [ ] Add Poetry packaging config so `src/ai_travel_agent` becomes importable in venv
- [ ] Run `poetry install --no-interaction` again
- [ ] Re-run `poetry run python scripts/demo_parser.py`

## Step 4 — Day 2 verification
- [ ] `poetry run ruff check .`
- [ ] `poetry run mypy src/`
- [ ] `.env` check + `demo_parser.py`
- [ ] `pytest tests/unit/test_preference_parser.py -v`
- [ ] `pytest tests/unit/test_supervisor.py -v`
- [ ] Node import check + `pytest tests/unit/test_nodes.py -v`

## Step 5 — Day 3 verification
- [ ] `python -m ai_travel_agent.agents.graph` (checkpoints db created)
- [ ] `python scripts/demo_agent.py`
- [ ] `python scripts/demo_graph_viz.py`
- [ ] `pytest tests/integration/test_graph_integration.py -v`

## Step 6 — Final full check
- [ ] `poetry run ruff check .`
- [ ] `poetry run mypy src/`
- [ ] `poetry run pytest` (full)


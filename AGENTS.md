# Electrolux Wellbeing Integration Info for AI Agents

## WHAT: Tech Stack
- **Language**: Python 3.14+ (managed via `mise`)
- **Framework**: Home Assistant custom integration
- **Environment**: Virtual environment `.venv` managed via `uv`
- **API Backend**: `pyelectroluxgroup` library
- **Libraries**: `Pillow` for map rendering, `pyturbojpeg` for camera tests
- **Tooling**: `ruff` for code styling/formatting/linting, `pytest` for unit testing

## WHY: Purpose
- Home Assistant integration for Electrolux and AEG smart appliances (purifiers, vacuums, humidifiers, ACs).
- Fetches device telemetry and translates it into Home Assistant sensors, binary sensors, climates, vacuums, fans, switches, and cameras.
- Provides real-time event updates via WebSocket stream while maintaining polling fallback.

## HOW: Commands
- **Install dependencies**: `mise exec -- ./scripts/setup --test`
- **Run dev container / environment**: `mise exec -- ./scripts/develop`
- **Lint / Format**: `mise exec -- ./scripts/lint`
- **Tests**: `export PYTHONPATH=$PWD && mise exec -- .venv/bin/pytest`

## Rules for AI Agents
- Be extremely concise. Sacrifice grammar for concision.
- At the end of each plan, list unresolved questions (if any).
- Do not add code snippets; use file:line references (e.g. [__init__.py:L50](file:///workspace/homeassistant-wellbeing/custom_components/wellbeing/__init__.py#L50)) for precision.
- Assume linters and code formatters handle styling during git hooks or `./scripts/lint`.

## Documentation Index (Progressive Disclosure)
- [Architectural Patterns](file:///workspace/homeassistant-wellbeing/docs/architectural_patterns.md): Core architectural designs, hybrid polling/streaming, and map rendering.
- [Appliance manual](file:///workspace/homeassistant-wellbeing/MANUAL.md): Specific manual configurations and capabilities for individual vacuums/purifiers.
- [Validation Workflow](file:///workspace/homeassistant-wellbeing/.github/workflows/validate.yaml): CI checks for HACS, Hassfest, Ruff lint/format, and pytest suite.

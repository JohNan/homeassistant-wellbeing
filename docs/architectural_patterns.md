# Architectural Patterns

## 1. Dynamic Entity Mapping
Instead of hardcoding entities, platforms query the coordinator's parsed capability models to instantiate entities dynamically.
- Setup helper: [binary_sensor.py:L10-25](file:///workspace/homeassistant-wellbeing/custom_components/wellbeing/binary_sensor.py#L10-25)
- Entity representation in api model: [api.py:L130-161](file:///workspace/homeassistant-wellbeing/custom_components/wellbeing/api.py#L130-161)

## 2. Hybrid Polling and WebSocket Streaming Coordinator
Implements a polling coordinator that scales frequency depending on appliance activity (e.g. active vacuum). Integrates a live stream update loop. To prevent frequent stream updates from delaying/postponing polling updates (which fetch poll-only metadata like map coordinates), stream updates notify listeners without resetting the coordinator's next poll timer.
- Live stream listening task: [__init__.py:L85-89](file:///workspace/homeassistant-wellbeing/custom_components/wellbeing/__init__.py#L85-89)
- Polling schedule adjustments: [__init__.py:L132-145](file:///workspace/homeassistant-wellbeing/custom_components/wellbeing/__init__.py#L132-145)
- Stream event dispatch: [__init__.py:L168-186](file:///workspace/homeassistant-wellbeing/custom_components/wellbeing/__init__.py#L168-186)

## 3. CPU-Bound Map Rendering in Executors
Transforms local coordinates (crumbs, vacuum poses) into a PNG map. Map computation and image drawing (via Pillow) are synchronous and CPU-bound, requiring offloading to an executor thread to keep the event loop non-blocking.
- Map renderer entry point: [map_renderer.py:L20-22](file:///workspace/homeassistant-wellbeing/custom_components/wellbeing/map_renderer.py#L20-22)
- Camera execution wrapper: [camera.py:L138-164](file:///workspace/homeassistant-wellbeing/custom_components/wellbeing/camera.py#L138-164)

## 4. Automatic Token Renewal Persistence
Integrates the `pyelectroluxgroup` token manager into Home Assistant's config entries. Once refreshed, updated keys are written back into the entry options to prevent stale authentication keys upon restart.
- Token manager implementation: [__init__.py:L189-212](file:///workspace/homeassistant-wellbeing/custom_components/wellbeing/__init__.py#L189-212)

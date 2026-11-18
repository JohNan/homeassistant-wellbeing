"""Tests for the official interactive vector map data builder."""

from types import SimpleNamespace

from custom_components.wellbeing.map_data import get_interactive_vector_map_data


def test_get_interactive_vector_map_data_zones_and_avoid():
    """Test vector map geometry conversion for clean and avoid zones."""
    mock_map = SimpleNamespace(
        id="map_1",
        name="Ground Floor",
        rotation=0.0,
        zones=[
            {
                "id": "z_1",
                "name": "Living Room",
                "zoneType": "clean",
                "powerMode": 2,
                "vertices": [
                    {"x": 0.0, "y": 0.0},
                    {"x": 2.0, "y": 0.0},
                    {"x": 2.0, "y": 3.0},
                    {"x": 0.0, "y": 3.0},
                ],
            },
            {
                "id": "z_2",
                "name": "Cable Area",
                "zoneType": "avoid",
                "vertices": [
                    {"x": 0.5, "y": 0.5},
                    {"x": 1.0, "y": 0.5},
                    {"x": 1.0, "y": 1.0},
                    {"x": 0.5, "y": 1.0},
                ],
            },
        ],
    )

    mock_api = SimpleNamespace(
        _interactive_maps={"pnc_1": [mock_map]},
        vacuum_get_selected_map=lambda pnc: "Ground Floor",
    )
    mock_app = SimpleNamespace(
        display_name="Robot Vacuum",
        model="PUREi9",
        battery_range=(1, 6),
        vacuum_fan_speed="smart",
        reported_state={
            "robotStatus": 10,
            "dustbinStatus": "empty",
            "batteryStatus": 6,
        },
    )

    res = get_interactive_vector_map_data(mock_api, mock_app, "pnc_1")
    assert res is not None
    assert res["pnc_id"] == "pnc_1"
    assert res["bounds"] is not None
    assert len(res["zones"]) == 1
    assert res["zones"][0]["name"] == "Living Room"
    assert res["zones"][0]["area_sqm"] == 6.0
    assert res["zones"][0]["power_mode"] == "Smart"
    assert len(res["avoid_zones"]) == 1
    assert res["avoid_zones"][0]["name"] == "Cable Area"
    assert res["telemetry"]["bat_pct"] == 100
    assert res["telemetry"]["active_map"] == "Ground Floor"
    assert res["telemetry"]["total_sqm"] == 6.0


def test_get_interactive_vector_map_data_missing_inputs():
    """Test None returned when api or app is missing."""
    assert get_interactive_vector_map_data(None, None, "pnc_1") is None

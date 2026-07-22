"""Tests for map_renderer.py."""

import math

from custom_components.wellbeing.map_renderer import (
    ROBOT_MARKER_CHARGER,
    ROBOT_MARKER_NONE,
    ROBOT_MARKER_POSE,
    _rotate,
    _split_runs,
    _to_global,
    render_map,
)


def test_rotate():
    """Test point rotation."""
    # 90 degrees rotation (pi/2 radians)
    point = (1.0, 0.0)
    rotated = _rotate(point, math.pi / 2)
    assert math.isclose(rotated[0], 0.0, abs_tol=1e-9)
    assert math.isclose(rotated[1], 1.0, abs_tol=1e-9)


def test_to_global():
    """Test frame transformation."""
    # Transform: translate (1.0, 2.0), rotate 0
    transform = (1.0, 2.0, 0.0)
    point = (3.0, 4.0)
    result = _to_global(point, transform)
    # expected: (3 - 1, 4 - 2) rotated by 0 = (2.0, 2.0)
    assert math.isclose(result[0], 2.0, abs_tol=1e-9)
    assert math.isclose(result[1], 2.0, abs_tol=1e-9)


def test_split_runs():
    """Test splitting crumb chunks into separate runs when points jump."""
    # MAX_SEGMENT_M = 0.6
    chunk = [
        (0.0, 0.0),
        (0.3, 0.0),  # dist 0.3 (within limit)
        (1.0, 0.0),  # dist 0.7 (exceeds limit, splits here)
        (1.2, 0.0),  # dist 0.2 (within limit)
    ]
    runs = _split_runs(chunk)
    assert len(runs) == 2
    assert runs[0] == [(0.0, 0.0), (0.3, 0.0)]
    assert runs[1] == [(1.0, 0.0), (1.2, 0.0)]


def test_render_map_empty():
    """Test map renderer with missing or empty inputs."""
    # None input
    assert render_map({}) is None

    # Empty mapData
    assert render_map({"mapData": {}}) is None

    # Missing crumbs
    assert render_map({"mapData": {"crumbs": []}}) is None

    # Crumbs without xy
    assert render_map({"mapData": {"crumbs": [{"t": 0}]}}) is None


def test_render_map_valid_no_marker():
    """Test map renderer returning a valid MapImage with no marker."""
    reported = {
        "mapData": {
            "crumbs": [
                {"xy": [0.0, 0.0], "t": 0},
                {"xy": [0.2, 0.2], "t": 0},
            ],
            "transforms": [{"t": 0, "xya": [0.0, 0.0, 0.0]}],
        }
    }
    result = render_map(reported, rotation_deg=90.0, robot_marker=ROBOT_MARKER_NONE)
    assert result is not None
    assert result.width > 0
    assert result.height > 0
    assert len(result.calibration_points) == 3


def test_render_map_with_markers():
    """Test map renderer with robot and charger markers."""
    reported = {
        "mapData": {
            "crumbs": [
                {"xy": [0.0, 0.0], "t": 0},
                {"xy": [0.2, 0.2], "t": 0},
            ],
            "transforms": [{"t": 0, "xya": [1.0, 1.0, 0.5]}],
            "chargerPoses": [{"xya": [0.0, 0.0, 0.0]}],
            "robotPose": {"xya": [0.2, 0.2, 1.0]},
        }
    }

    # Pose marker
    result_pose = render_map(reported, rotation_deg=0.0, robot_marker=ROBOT_MARKER_POSE)
    assert result_pose is not None

    # Charger marker
    result_charger = render_map(
        reported, rotation_deg=0.0, robot_marker=ROBOT_MARKER_CHARGER
    )
    assert result_charger is not None


def test_render_map_charger_fallback():
    """Test fallback to chargerPoses when transform 0 is missing."""
    reported = {
        "mapData": {
            "crumbs": [
                {"xy": [0.0, 0.0], "t": 0},
                {"xy": [0.2, 0.2], "t": 0},
            ],
            "transforms": [{"t": 1, "xya": [1.0, 1.0, 0.5]}],
            "chargerPoses": [{"xya": [0.5, 0.5, 0.5]}],
        }
    }
    result = render_map(reported, rotation_deg=0.0, robot_marker=ROBOT_MARKER_CHARGER)
    assert result is not None

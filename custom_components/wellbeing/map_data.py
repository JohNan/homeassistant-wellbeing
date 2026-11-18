"""Official interactive vector map geometry & telemetry builder for Wellbeing."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.util.percentage import ranged_value_to_percentage

POWER_MODE_LABELS = {
    1: "Quiet",
    2: "Smart",
    3: "Power",
}


def _rotate_pt(x: float, y: float, rad: float) -> tuple[float, float]:
    """Rotate a 2D point around the origin by `rad` radians."""
    c, s = math.cos(rad), math.sin(rad)
    return (x * c - y * s, x * s + y * c)


def _polygon_area_sqm(vertices: list[Any]) -> float:
    """Compute polygon area in square meters using the shoelace formula."""
    if len(vertices) < 3:
        return 0.0
    pts = [
        (
            float(v["x"] if isinstance(v, dict) else getattr(v, "x", 0.0)),
            float(v["y"] if isinstance(v, dict) else getattr(v, "y", 0.0)),
        )
        for v in vertices
    ]
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _get_field(obj: Any, *keys: str, default: Any = None) -> Any:
    """Read a field from either a dict, a `.data` dict, or an attribute object."""
    if isinstance(obj, dict):
        for k in keys:
            if k in obj:
                return obj[k]
        return default
    data = getattr(obj, "data", None)
    if isinstance(data, dict):
        for k in keys:
            if k in data:
                return data[k]
    for k in keys:
        if hasattr(obj, k):
            return getattr(obj, k)
    return default


def get_interactive_vector_map_data(
    api: Any, app: Any, pnc_id: str
) -> dict[str, Any] | None:
    """Return vector map geometry (in rotated meter coordinates) and live telemetry."""
    if not api or not app:
        return None

    reported = getattr(app, "reported_state", None) or {}
    raw_status = reported.get("robotStatus", 10)
    dustbin_raw = str(reported.get("dustbinStatus", "connected"))
    dustbin_ok = dustbin_raw.casefold() in ("connected", "empty", "notconnected")

    bat_raw = reported.get("batteryStatus", 6)
    bat_pct = max(
        0, min(100, round(ranged_value_to_percentage(app.battery_range, bat_raw)))
    )
    fan_speed = (getattr(app, "vacuum_fan_speed", None) or "smart").upper()

    maps = (
        api._interactive_maps.get(pnc_id, [])
        if hasattr(api, "_interactive_maps")
        else []
    )
    selected_name = (
        api.vacuum_get_selected_map(pnc_id)
        if hasattr(api, "vacuum_get_selected_map")
        else None
    )
    selected_map = None
    if selected_name:
        selected_map = next(
            (m for m in maps if _get_field(m, "name") == selected_name),
            None,
        )
    if selected_map is None and maps:
        selected_map = maps[0]

    raw_zones = _get_field(selected_map, "zones", default=[]) if selected_map else []
    rot = float(_get_field(selected_map, "rotation", default=0.0) or 0.0) - (
        math.pi / 2.0
    )

    all_pts: list[tuple[float, float]] = []
    zones_out: list[dict[str, Any]] = []
    avoid_zones_out: list[dict[str, Any]] = []
    total_sqm = 0.0

    for idx, z in enumerate(raw_zones or []):
        verts = _get_field(z, "vertices", default=[]) or []
        if len(verts) < 3:
            continue
        z_type = str(_get_field(z, "zoneType", "type", default="clean")).casefold()
        poly_svg = []
        for v in verts:
            vx = float(v["x"] if isinstance(v, dict) else getattr(v, "x", 0.0))
            vy = float(v["y"] if isinstance(v, dict) else getattr(v, "y", 0.0))
            rx, ry = _rotate_pt(vx, vy, rot)
            svg_pt = (rx, -ry)
            all_pts.append(svg_pt)
            poly_svg.append([round(rx, 3), round(-ry, 3)])

        if z_type == "avoid":
            avoid_zones_out.append(
                {
                    "id": _get_field(z, "id"),
                    "name": _get_field(z, "name")
                    or f"Avoid {len(avoid_zones_out) + 1}",
                    "vertices": poly_svg,
                }
            )
            continue

        cx = sum(p[0] for p in poly_svg) / len(poly_svg)
        cy = sum(p[1] for p in poly_svg) / len(poly_svg)
        area_sqm = round(_polygon_area_sqm(verts), 1)
        total_sqm += area_sqm
        pm_val = _get_field(z, "powerMode", "power_mode")
        zones_out.append(
            {
                "id": _get_field(z, "id"),
                "name": _get_field(z, "name") or f"Zone {idx + 1}",
                "power_mode": POWER_MODE_LABELS.get(pm_val, ""),
                "area_sqm": area_sqm,
                "vertices": poly_svg,
                "center": [round(cx, 3), round(cy, 3)],
                "color_idx": len(zones_out) % 6,
            }
        )

    bounds = None
    if all_pts:
        pad = 0.35
        bounds = {
            "min_x": round(min(p[0] for p in all_pts) - pad, 3),
            "max_x": round(max(p[0] for p in all_pts) + pad, 3),
            "min_y": round(min(p[1] for p in all_pts) - pad, 3),
            "max_y": round(max(p[1] for p in all_pts) + pad, 3),
        }

    return {
        "pnc_id": pnc_id,
        "bounds": bounds,
        "zones": zones_out,
        "avoid_zones": avoid_zones_out,
        "telemetry": {
            "name": getattr(
                app, "display_name", getattr(app, "name", "Vacuum")
            ).strip(),
            "model": str(getattr(app, "model", "PUREi9")),
            "status_code": raw_status,
            "is_cleaning": raw_status in (1, 3),
            "bat_pct": bat_pct,
            "fan_speed": fan_speed,
            "dustbin_ok": dustbin_ok,
            "active_map": _get_field(selected_map, "name") if selected_map else None,
            "all_maps": [_get_field(m, "name") for m in maps if _get_field(m, "name")],
            "total_sqm": round(total_sqm, 1),
        },
    }

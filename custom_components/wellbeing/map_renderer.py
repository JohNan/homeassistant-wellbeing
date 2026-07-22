"""Render robot vacuum map images from the raw map data in the appliance state.

The Electrolux API reports dynamic map data for robot vacuums in the appliance
state under ``mapData``: "crumbs" (points the robot has visited), the robot
pose, the charger pose and per-chunk coordinate transforms. This module turns
that data into a PNG image plus calibration points, without any additional API
calls.

Coordinates: crumbs are recorded in per-chunk local frames; each crumb's ``t``
selects a transform ``(tx, ty, a)`` and ``global = R(-a) @ (p - (tx, ty))``.
Frame 0's origin maps exactly onto the reported charger pose, which is how
this convention was verified (on a PUREi9.2). The charger pose and the robot
pose are already in the global (persistent map) frame; the robot pose
coincides with the last reported crumb.

The calibration points map the global (metres) frame to image pixels in the
format used by mqtt_vacuum_camera, so lovelace cards such as
xiaomi-vacuum-map-card can consume them via ``calibration_source: camera``.

All functions in this module are synchronous and CPU-bound; call them from an
executor.
"""

import io
import math
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

SCALE = 120  # px per metre (before supersampling)
SUPERSAMPLE = 2
PADDING_M = 0.7
ROBOT_WIDTH_M = 0.33  # PUREi9 footprint -> width of the coverage swath
MAX_SEGMENT_M = 0.6  # crumb gaps larger than this are lifts/jumps, not moves
MAX_DIMENSION_PX = 1600  # safety cap for degenerate map data

ROBOT_MARKER_NONE = "none"
ROBOT_MARKER_POSE = "pose"
ROBOT_MARKER_CHARGER = "charger"

BACKGROUND = (17, 20, 24, 255)
SWATH = (46, 92, 158, 255)
PATH = (137, 180, 250, 255)
CHARGER = (52, 211, 153, 255)
ROBOT_FILL = (255, 255, 204, 255)
ROBOT_OUTLINE = (127, 127, 102, 255)


@dataclass
class MapImage:
    """A rendered vacuum map."""

    image: bytes  # PNG
    width: int
    height: int
    calibration_points: list[dict] = field(default_factory=list)


def _rotate(point, radians):
    return (
        math.cos(radians) * point[0] - math.sin(radians) * point[1],
        math.sin(radians) * point[0] + math.cos(radians) * point[1],
    )


def _to_global(point, transform):
    """Map a local-frame point to the persistent map frame."""
    tx, ty, a = transform
    return _rotate((point[0] - tx, point[1] - ty), -a)


def render_map(
    reported: dict, rotation_deg: float = 0.0, robot_marker: str = ROBOT_MARKER_NONE
) -> MapImage | None:
    """Render the vacuum map from the reported appliance state.

    robot_marker selects where the robot is drawn: at its reported pose (only
    meaningful while the robot is moving), on the charger (when docked), or
    not at all. Returns None when the state carries no usable map data.
    """
    map_data = reported.get("mapData")
    if not map_data or not map_data.get("crumbs"):
        return None

    view_rotation = math.radians(rotation_deg)

    def view(point):
        return _rotate(point, view_rotation)

    transforms = {
        t["t"]: t["xya"]
        for t in map_data.get("transforms", [])
        if len(t.get("xya", [])) == 3
    }
    identity = [0.0, 0.0, 0.0]

    # Crumb chunks, each in its own frame; keep chunks separate so the pen
    # lifts between them instead of drawing a stroke across the room.
    chunks: list[tuple[int, list]] = []
    for crumb in map_data["crumbs"]:
        if "xy" not in crumb:
            continue
        pos = view(_to_global(crumb["xy"], transforms.get(crumb.get("t"), identity)))
        if chunks and chunks[-1][0] == crumb.get("t"):
            chunks[-1][1].append(pos)
        else:
            chunks.append((crumb.get("t"), [pos]))
    if not chunks:
        return None

    # The charger is the origin of local frame 0: the robot zeroes its
    # odometry on the dock at session start (verified: transform 0 is always
    # exactly the inverse of the charger pose). The reported chargerPoses is
    # not reliable - it flip-flops between global coordinates and the local
    # frame-0 origin (0, 0, 0) across sessions - so it is only a fallback.
    charger = charger_heading = None
    if 0 in transforms:
        charger = view(_to_global((0.0, 0.0), transforms[0]))
        charger_heading = -transforms[0][2] + view_rotation
    else:
        charger_poses = map_data.get("chargerPoses")
        if charger_poses and len(charger_poses[0].get("xya", [])) >= 2:
            xya = charger_poses[0]["xya"]
            charger = view(xya[:2])
            charger_heading = (xya[2] if len(xya) == 3 else 0.0) + view_rotation

    # The robot pose is reported directly in the global frame (verified: it
    # coincides with the last reported crumb; the identity transform tagged
    # t=1000 is its frame marker). It is only current while the robot is
    # moving - when docked the pose is a stale mid-session snapshot, so the
    # robot is drawn on the charger instead.
    robot = robot_heading = None
    robot_pose = map_data.get("robotPose")
    if (
        robot_marker == ROBOT_MARKER_POSE
        and robot_pose
        and len(robot_pose.get("xya", [])) == 3
    ):
        robot = view(robot_pose["xya"][:2])
        robot_heading = robot_pose["xya"][2] + view_rotation
    elif robot_marker == ROBOT_MARKER_CHARGER and charger:
        robot = charger
        robot_heading = charger_heading

    points = [p for _, chunk in chunks for p in chunk]
    if charger:
        points.append(charger)
    if robot:
        points.append(robot)

    xs, ys = [p[0] for p in points], [p[1] for p in points]
    xmin, xmax = min(xs) - PADDING_M, max(xs) + PADDING_M
    ymin, ymax = min(ys) - PADDING_M, max(ys) + PADDING_M

    scale = SCALE * SUPERSAMPLE
    width = min(int((xmax - xmin) * scale), MAX_DIMENSION_PX * SUPERSAMPLE)
    height = min(int((ymax - ymin) * scale), MAX_DIMENSION_PX * SUPERSAMPLE)
    if width < 1 or height < 1:
        return None

    def px(point):
        # y axis flipped: world y up, image y down
        return ((point[0] - xmin) * scale, (ymax - point[1]) * scale)

    img = Image.new("RGBA", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(img)

    # Coverage swath: a stroke as wide as the robot along the crumb path
    swath_width = int(ROBOT_WIDTH_M * scale)
    for _, chunk in chunks:
        for run in _split_runs(chunk):
            pts = [px(p) for p in run]
            if len(pts) > 1:
                draw.line(pts, fill=SWATH, width=swath_width, joint="curve")
            for p in (pts[0], pts[-1]):
                radius = swath_width / 2
                draw.ellipse(
                    [p[0] - radius, p[1] - radius, p[0] + radius, p[1] + radius],
                    fill=SWATH,
                )

    # Centre path line on top of the swath
    for _, chunk in chunks:
        for run in _split_runs(chunk):
            pts = [px(p) for p in run]
            if len(pts) > 1:
                draw.line(pts, fill=PATH, width=max(2, scale // 40), joint="curve")

    if charger:
        _draw_charger(draw, px(charger), scale)
    if robot:
        _draw_robot(draw, px, robot, robot_heading, scale)

    img = img.resize((width // SUPERSAMPLE, height // SUPERSAMPLE), Image.LANCZOS)
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, "PNG")

    # Three reference points mapping the vacuum (global metres) frame to
    # image pixels, in the attribute format established by
    # mqtt_vacuum_camera / xiaomi-vacuum-map-card.
    def calibration_point(px_x: int, px_y: int) -> dict:
        rotated = (xmin + px_x * SUPERSAMPLE / scale, ymax - px_y * SUPERSAMPLE / scale)
        world = _rotate(rotated, -view_rotation)
        return {
            "vacuum": {"x": round(world[0], 3), "y": round(world[1], 3)},
            "map": {"x": px_x, "y": px_y},
        }

    out_width, out_height = img.width, img.height
    calibration_points = [
        calibration_point(0, 0),
        calibration_point(out_width, 0),
        calibration_point(0, out_height),
    ]

    return MapImage(
        image=buffer.getvalue(),
        width=out_width,
        height=out_height,
        calibration_points=calibration_points,
    )


def _split_runs(chunk):
    """Split a crumb chunk where consecutive points are implausibly far apart."""
    runs, run = [], [chunk[0]]
    for prev, cur in zip(chunk, chunk[1:]):
        if math.dist(prev, cur) > MAX_SEGMENT_M:
            runs.append(run)
            run = [cur]
        else:
            run.append(cur)
    runs.append(run)
    return runs


def _draw_charger(draw, center, scale):
    cx, cy = center
    radius = 0.14 * scale
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=CHARGER)
    draw.line(
        [cx, cy - radius * 0.5, cx, cy + radius * 0.5],
        fill=BACKGROUND,
        width=int(radius / 3),
    )
    draw.line(
        [cx - radius * 0.4, cy, cx + radius * 0.4, cy],
        fill=BACKGROUND,
        width=int(radius / 3),
    )


def _draw_robot(draw, px, robot, heading, scale):
    """Draw the robot marker: body, front chord, lidar dot and button dot."""
    rx, ry = px(robot)
    radius_m = ROBOT_WIDTH_M / 2
    radius = radius_m * scale
    line_width = max(2, int(radius / 11))

    def along(dist_m, angle):
        return px(
            (robot[0] + dist_m * math.cos(angle), robot[1] + dist_m * math.sin(angle))
        )

    draw.ellipse(
        [rx - radius, ry - radius, rx + radius, ry + radius],
        fill=ROBOT_FILL,
        outline=ROBOT_OUTLINE,
        width=line_width,
    )
    chord = [
        along(radius_m * 0.9, heading - math.radians(80)),
        along(radius_m * 0.9, heading + math.radians(80)),
    ]
    draw.line(chord, fill=ROBOT_OUTLINE, width=line_width)
    lidar_x, lidar_y = along(radius_m * 0.6, heading)
    lidar_r = radius * 3 / 11
    draw.ellipse(
        [lidar_x - lidar_r, lidar_y - lidar_r, lidar_x + lidar_r, lidar_y + lidar_r],
        fill=ROBOT_OUTLINE,
    )
    button_x, button_y = along(radius_m * 0.8, heading + math.pi)
    button_r = radius * 1.5 / 11
    draw.ellipse(
        [
            button_x - button_r,
            button_y - button_r,
            button_x + button_r,
            button_y + button_r,
        ],
        fill=ROBOT_OUTLINE,
    )

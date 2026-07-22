"""Camera platform for Wellbeing: renders the robot vacuum map.

The Electrolux API does not provide a map image, but the appliance state of
robot vacuums includes raw dynamic map data (see map_renderer). This platform
renders that data into a camera entity, so the map can be shown in lovelace
(e.g. with picture-entity or xiaomi-vacuum-map-card, which can also read the
``calibration_points`` attribute via ``calibration_source: camera: true``).
"""

import logging

from homeassistant.components.camera import Camera
from homeassistant.components.vacuum import VacuumActivity
from homeassistant.const import Platform

from .const import CONF_MAP_ROTATION, DEFAULT_MAP_ROTATION, DOMAIN
from .entity import WellbeingEntity
from .map_renderer import (
    ROBOT_MARKER_CHARGER,
    ROBOT_MARKER_NONE,
    ROBOT_MARKER_POSE,
    MapImage,
    render_map,
)
from .vacuum import VACUUM_ACTIVITIES

_LOGGER: logging.Logger = logging.getLogger(__package__)

ACTIVE_ACTIVITIES = {
    VacuumActivity.CLEANING,
    VacuumActivity.RETURNING,
    VacuumActivity.PAUSED,
}


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup camera platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        async_add_devices(
            [
                WellbeingCamera(
                    coordinator, entry, pnc_id, entity.entity_type, entity.attr
                )
                for pnc_id, appliance in appliances.appliances.items()
                for entity in appliance.entities
                if entity.entity_type == Platform.CAMERA
            ]
        )


class WellbeingCamera(WellbeingEntity, Camera):
    """Camera showing the robot vacuum map."""

    _attr_content_type = "image/png"

    def __init__(self, coordinator, config_entry, pnc_id, entity_type, entity_attr):
        super().__init__(coordinator, config_entry, pnc_id, entity_type, entity_attr)
        Camera.__init__(self)
        self._map_image: MapImage | None = None
        self._render_key = None
        self._crumbs: list = []
        self._crumb_session = None
        self._crumb_timestamp = None

    @property
    def map_data(self) -> dict:
        return self.get_entity.state or {}

    def _robot_marker(self) -> str:
        """Where to draw the robot: at its pose (moving), on the charger (docked), or not at all.

        The reported robot pose is only current while the robot is moving AND
        the reported map data belongs to the running cleaning session: at the
        start of a session the cloud still reports the previous session's map
        (uploads lag minutes behind the robot), and drawing the old pose on
        the old map would show the robot somewhere it is not.
        """
        vacuum = next(
            (
                entity
                for entity in self.get_appliance.entities
                if entity.entity_type == Platform.VACUUM
            ),
            None,
        )
        if vacuum is None:
            return ROBOT_MARKER_NONE
        activity = VACUUM_ACTIVITIES.get(vacuum.state)
        if activity in ACTIVE_ACTIVITIES:
            if self._map_session_is_current():
                return ROBOT_MARKER_POSE
            return ROBOT_MARKER_NONE
        # DOCKED covers charging/pitstop; the PUREi9 reports "sleeping"
        # (status 10, mapped to IDLE) when it rests fully charged on the
        # charger, so IDLE is treated as docked too.
        if activity in (VacuumActivity.DOCKED, VacuumActivity.IDLE):
            return ROBOT_MARKER_CHARGER
        return ROBOT_MARKER_NONE

    def _map_session_is_current(self) -> bool:
        """Whether the reported map data belongs to the running cleaning session."""
        session = (
            getattr(self.get_appliance, "reported_state", {}).get("cleaningSession")
            or {}
        )
        session_id = session.get("sessionId")
        if session_id is None:
            return True  # cannot tell; keep the previous behaviour
        return self.map_data.get("sessionId") == session_id

    def _accumulated_crumbs(self, map_data: dict) -> list:
        """Return the full crumb trail for the reported session.

        When a live map view is open in the Electrolux app, the robot
        switches to delta uploads (crumbCollectionDelta) where each state
        carries only the crumbs since the previous upload, so they have to
        be accumulated across updates. Non-delta uploads carry the full
        trail and replace the accumulated state.
        """
        session_id = map_data.get("sessionId")
        if session_id != self._crumb_session:
            self._crumb_session = session_id
            self._crumb_timestamp = None
            self._crumbs = []
        timestamp = map_data.get("timestamp")
        if timestamp != self._crumb_timestamp:
            self._crumb_timestamp = timestamp
            crumbs = map_data.get("crumbs") or []
            if map_data.get("crumbCollectionDelta"):
                self._crumbs = self._crumbs + crumbs
            else:
                self._crumbs = crumbs
        return self._crumbs

    async def _async_render_if_changed(self) -> None:
        """(Re)render the map when the underlying map data has changed."""
        map_data = self.map_data
        crumbs = self._accumulated_crumbs(map_data)
        robot_marker = self._robot_marker()
        rotation = self.config_entry.options.get(
            CONF_MAP_ROTATION, DEFAULT_MAP_ROTATION
        )
        render_key = (
            map_data.get("timestamp"),
            map_data.get("sessionId"),
            len(crumbs),
            robot_marker,
            rotation,
        )
        if render_key == self._render_key:
            return
        map_image = await self.hass.async_add_executor_job(
            render_map,
            {"mapData": {**map_data, "crumbs": crumbs}},
            float(rotation),
            robot_marker,
        )
        self._render_key = render_key
        if map_image:
            self._map_image = map_image

    async def async_added_to_hass(self) -> None:
        """Render once on startup so the image and attributes are available."""
        await super().async_added_to_hass()
        await self._async_render_if_changed()

    def _handle_coordinator_update(self) -> None:
        """Re-render in the background when the coordinator has new data."""
        self.hass.async_create_task(self._async_render_and_write_state())

    async def _async_render_and_write_state(self) -> None:
        await self._async_render_if_changed()
        self.async_write_ha_state()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the rendered map image."""
        await self._async_render_if_changed()
        return self._map_image.image if self._map_image else None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = super().extra_state_attributes
        if self._map_image:
            attributes["calibration_points"] = self._map_image.calibration_points
        if timestamp := self.map_data.get("timestamp"):
            attributes["map_timestamp"] = timestamp
        return attributes

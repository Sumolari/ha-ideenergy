#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2021 Luis López <luis@cuarentaydos.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.


"""Platform for sensor integration."""


import random
from datetime import datetime, timedelta

import ideenergy


from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.const import DEVICE_CLASS_ENERGY, ENERGY_KILO_WATT_HOUR
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt

from . import _LOGGER
from .const import (
    DOMAIN,
    STATE_MAX_AGE,
    UPDATE_BARRIER_MINUTE_MAX,
    UPDATE_BARRIER_MINUTE_MIN,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""
    sensors = [
        IDEEnergyAccumulateSensor(
            hass.data[DOMAIN][config_entry.entry_id],
            name="consumed",
            key="accumulate",
        )
    ]

    async_add_entities(sensors, False)  # Update entity on add


class IDEEnergyAccumulateSensor(RestoreEntity, Entity):
    def __init__(self, api, name, key):
        self._state = None
        self._api = api
        self._unsub_sched_update = None

    async def async_added_to_hass(self) -> None:
        state = await self.async_get_last_state()

        if not state:
            _LOGGER.debug("No previous state, force refresh and update")
            self.async_schedule_update_ha_state(force_refresh=True)

        else:
            try:
                self._state = float(state.state)
                _LOGGER.debug(f"Restored previous state: {state!r}")

                if (
                    dt.now() - state.last_updated
                ).total_seconds() > STATE_MAX_AGE:
                    _LOGGER.debug(
                        "Previous state is too old, scheduling update"
                    )
                    self.async_schedule_update_ha_state(force_refresh=True)

            except ValueError:
                _LOGGER.debug(
                    "Invalid previous state, force refresh and update"
                )
                self.async_schedule_update_ha_state(force_refresh=True)

        self.schedule_next_update()

    def schedule_next_update(self):
        if self._unsub_sched_update:
            _LOGGER.debug("Remove previous track task")
            self._unsub_sched_update()
            self._unsub_sched_update = None

        now = dt.now()
        update_min = random.randrange(
            UPDATE_BARRIER_MINUTE_MIN, UPDATE_BARRIER_MINUTE_MAX
        )
        update_sec = random.randrange(0, 60)

        next_update = now.replace(minute=update_min, second=update_sec)
        if now.minute >= UPDATE_BARRIER_MINUTE_MIN:
            next_update = next_update + timedelta(hours=1)

        _LOGGER.debug(
            f"Updating sensor in {(next_update - now).total_seconds()} secs "
            f"(now: {now}) (update: {next_update})"
        )

        self._unsub_sched_update = async_track_time_change(
            self.hass,
            self.do_scheduled_update,
            hour=[next_update.hour],
            minute=[next_update.minute],
            second=[next_update.second],
        )

    def _schedule_next_update(self):
        if self._unsub_sched_update:
            _LOGGER.debug("Remove previous track task")
            self._unsub_sched_update()
            self._unsub_sched_update = None

        next_second = random.randrange(20, 59)
        delta = timedelta(seconds=next_second)

        now = datetime.now()
        next_update = now + delta

        _LOGGER.debug(
            f"Updating sensor in {delta.total_seconds()} secs (now: {now}) (update: {next_update})"
        )

        self._unsub_sched_update = async_track_time_change(
            self.hass, self.do_scheduled_update, second=[next_update.second]
        )

    @callback
    async def do_scheduled_update(self, now):
        print("do_scheduled_update")
        self.async_schedule_update_ha_state(force_refresh=True)
        self.schedule_next_update()

    async def async_update(self):
        # TODO: replace with real stuff
        try:
            measure = await self._api.get_measure()
        except ideenergy.IDEEnergyException as e:
            _LOGGER.error(f"Error reading measure: {e}")

        # self._state = (self._state or 0) + random.randrange(0, 3)
        self._state = measure.accumulate
        _LOGGER.debug(f"State updated: {self.state}")

    @property
    def name(self):
        return "IDEEnergy consumed energy"

    @property
    def state(self):
        return self._state

    @property
    def device_class(self):
        return DEVICE_CLASS_ENERGY

    @property
    def unit_of_measurement(self):
        return ENERGY_KILO_WATT_HOUR

    @property
    def should_poll(self):
        return False

    @property
    def extra_state_attributes(self):
        return {
            ATTR_LAST_RESET: self.last_reset,
            ATTR_STATE_CLASS: self.state_class,
        }

    @property
    def last_reset(self):
        return dt.utc_from_timestamp(0)

    @property
    def state_class(self):
        return STATE_CLASS_TOTAL_INCREASING

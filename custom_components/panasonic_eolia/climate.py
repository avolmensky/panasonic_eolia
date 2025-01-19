import logging
import voluptuous as vol
from datetime import timedelta
from typing import Optional, List
import panasoniceolia
import homeassistant.helpers.config_validation as cv
from homeassistant.const import UnitOfTemperature

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity, HVACMode, ClimateEntityFeature

from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_USERNAME, CONF_PASSWORD)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'panasonic_eolia'

SCAN_INTERVAL = timedelta(seconds=300)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})

OPERATION_LIST = {
    HVACMode.OFF: 'Off',
    HVACMode.HEAT: 'Heat',
    HVACMode.COOL: 'Cool',
    HVACMode.HEAT_COOL: 'Auto',
    HVACMode.DRY: 'Dry',
    HVACMode.FAN_ONLY: 'Fan'
}

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE |
    ClimateEntityFeature.FAN_MODE |
    ClimateEntityFeature.SWING_MODE |
    ClimateEntityFeature.TURN_ON |
    ClimateEntityFeature.TURN_OFF )


def api_call_login(func):
    def wrapper_call(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            args[0]._api.login()
            func(*args, **kwargs)
    return wrapper_call


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the panasonic cloud components."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    api = panasoniceolia.Session(username, password, verifySsl=True)

    api.login()

    _LOGGER.debug("Adding Panasonic Eolia devices")

    devices = []
    for device in api.get_devices():
        _LOGGER.debug("Setting up %s ...", device)
        devices.append(PanasonicEoliaDevice(
            device, api, panasoniceolia.constants))

    add_entities(devices, True)


class PanasonicEoliaDevice(ClimateEntity):
    """Representation of a Panasonic airconditioning."""

    def __init__(self, device, api, constants):
        """Initialize the device."""
        _LOGGER.debug("Add panasonic device '{0}'".format(device['name']))
        self._api = api
        self._device = device
        self._constants = constants
        self._current_temp = None
        self._is_on = False
        self._hvac_mode = OPERATION_LIST[HVACMode.COOL]

        self._unit = UnitOfTemperature.CELSIUS
        self._target_temp = None
        self._cur_temp = None
        self._outside_temp = None
        self._mode = None
        self._eco = 'Auto'

        self._current_fan = None
        self._airswing_hor = None
        self._airswing_vert = None

        self._enable_turn_on_off_backwards_compatibility = False

    def update(self):
        """Update the state of this climate device."""
        try:
            data = self._api.get_device(self._device['id'])
        except:
            _LOGGER.debug(
                "Error trying to get device {id} state, probably expired token, trying to update it...".format(**self._device))
            self._api.login()
            data = self._api.get_device(self._device['id'])

        if data is None:
            _LOGGER.debug(
                "Received no data for device {id}".format(**self._device))
            return

        if data['parameters']['temperature'] != 126:
            self._target_temp = data['parameters']['temperature']
        else:
            self._target_temp = None

        if data['parameters']['temperatureInside'] != 126:
            self._cur_temp = data['parameters']['temperatureInside']
        else:
            self._cur_temp = None

        if data['parameters']['temperatureOutside'] != 126:
            self._outside_temp = data['parameters']['temperatureOutside']
        else:
            self._outside_temp = None

        self._is_on = bool(data['parameters']['power'].value)
        self._hvac_mode = data['parameters']['mode'].name
        self._current_fan = data['parameters']['fanSpeed'].name
        self._airswing_vert = data['parameters']['airSwingVertical'].name

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the display name of this climate."""
        return self._device['name']

    @property
    def group(self):
        """Return the display group of this climate."""
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._target_temp

    @property
    def hvac_mode(self):
        """Return the current operation."""
        if not self._is_on:
            return HVACMode.OFF

        for key, value in OPERATION_LIST.items():
            if value == self._hvac_mode:
                return key

        # for key, value in OPERATION_LIST_EXTRA.items():
        #     if value == self._hvac_mode:
        #         return key

        return None

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return list(OPERATION_LIST.keys())

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._current_fan

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return [f.name for f in self._constants.FanSpeed]

    @property
    def swing_mode(self):
        """Return the fan setting."""
        return self._airswing_vert

    @property
    def swing_modes(self):
        """Return the list of available swing modes."""
        return [f.name for f in self._constants.AirSwingUD]

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._cur_temp

    @property
    def outside_temperature(self):
        """Return the current temperature."""
        return self._outside_temp

    @api_call_login
    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        _LOGGER.debug("Set %s temperature %s", self.name, target_temp)

        self._api.set_device(
            self._device['id'],
            temperature=target_temp
        )

    @api_call_login
    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Set %s focus mode %s", self.name, fan_mode)

        self._api.set_device(
            self._device['id'],
            fanSpeed=self._constants.FanSpeed[fan_mode]
        )

    @api_call_login
    def set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        _LOGGER.debug("Set %s mode %s", self.name, hvac_mode)
        if hvac_mode == HVACMode.OFF:
            self._api.set_device(
                self._device['id'],
                power=self._constants.Power.Off
            )
        else:

            self._api.set_device(
                self._device['id'],
                power=self._constants.Power.On,
                mode=self._constants.OperationMode[OPERATION_LIST[hvac_mode]]
            )

    @api_call_login
    def set_swing_mode(self, swing_mode):
        """Set swing mode."""
        _LOGGER.debug("Set %s swing mode %s", self.name, swing_mode)
        if swing_mode == 'Auto':
            automode = self._constants.AirSwingAutoMode["AirSwingUD"]
        else:
            automode = self._constants.AirSwingAutoMode["Disabled"]

        _LOGGER.debug("Set %s swing mode %s", self.name, swing_mode, automode)

        self._api.set_device(
            self._device['id'],
            power=self._constants.Power.On,
            airSwingVertical=self._constants.AirSwingUD[swing_mode],
            fanAutoMode=automode
        )

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 16

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 30

    @property
    def target_temp_step(self):
        """Return the temperature step."""
        return 0.5

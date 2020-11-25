import hashlib
from datetime import datetime
from functools import wraps

from .parser import date_order_chart
from .utils import registry


@registry
class Settings:
    """Control and configure default parsing behavior of dateparser.
    Currently, supported settings are:

    * `DATE_ORDER`
    * `PREFER_LOCALE_DATE_ORDER`
    * `TIMEZONE`
    * `TO_TIMEZONE`
    * `RETURN_AS_TIMEZONE_AWARE`
    * `PREFER_DAY_OF_MONTH`
    * `PREFER_DATES_FROM`
    * `RELATIVE_BASE`
    * `STRICT_PARSING`
    * `REQUIRE_PARTS`
    * `SKIP_TOKENS`
    * `NORMALIZE`
    * `RETURN_TIME_AS_PERIOD`
    * `PARSERS`
    """

    _default = True
    _pyfile_data = None
    _mod_settings = dict()

    def __init__(self, **kwargs):
        if not kwargs.get('settings'):
            self._updateall(self._get_settings_from_pyfile().items())

        elif len(self.__dict__) == 1:
            self._updateall(kwargs['settings'].items())

    @classmethod
    def get_key(cls, **kwargs):
        if kwargs:
            keys = sorted('{}-{}'.format(key, val) for key, val in kwargs.pop('settings').items())
            keys.extend(sorted('{}-{}'.format(key, val) for key, val in kwargs.items() if val))
            return hashlib.md5(''.join(sorted(keys)).encode('utf-8')).hexdigest()

        return 'default'

    @classmethod
    def _get_settings_from_pyfile(cls):
        if not cls._pyfile_data:
            from dateparser_data import settings
            cls._pyfile_data = settings.settings
        return cls._pyfile_data

    def _updateall(self, iterable):
        for key, value in iterable:
            setattr(self, key, value)

    def replace(self, mod_settings=None, **kwds):
        _settings = kwds.get('settings', {}).copy()
        for k, v in _settings.items():
            if v is None:
                raise TypeError('Invalid {{"{}": {}}}'.format(k, v))

        for key in self._get_settings_from_pyfile().keys():
            _settings.setdefault(key, getattr(self, key))

        _settings['_default'] = False
        if mod_settings:
            _settings['_mod_settings'] = mod_settings

        kwds['settings'] = _settings
        return self.__class__(**kwds)


settings = Settings()


def apply_settings(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        mod_settings = kwargs.get('settings', {})
        if mod_settings is None:
            kwargs['settings'], mod_settings = {}, {}

        if kwargs:
            if isinstance(mod_settings, dict):
                kwargs['settings'] = settings.replace(mod_settings=mod_settings.copy(), **kwargs)
        else:
            kwargs['settings'] = settings

        if not isinstance(kwargs['settings'], Settings):
            raise TypeError("settings can only be either dict or instance of Settings class")

        return f(*args, **kwargs)
    return wrapper


class SettingValidationError(ValueError):
    pass


def _check_repeated_values(setting_name, setting_value):
    if len(setting_value) != len(set(setting_value)):
        raise SettingValidationError(
            'There are repeated values in the "{}" setting'.format(setting_name)
        )
    return


def _check_require_part(setting_name, setting_value):
    """Returns `True` if the provided list of parts contains valid values"""
    invalid_values = set(setting_value) - {'day', 'month', 'year'}
    if invalid_values:
        raise SettingValidationError(
            '"{}" setting contains invalid values: {}'.format(
                setting_name, ', '.join(invalid_values)
            )
        )
    _check_repeated_values(setting_name, setting_value)


def _check_parsers(setting_name, setting_value):
    """Returns `True` if the provided list of parsers contains valid values"""
    existing_parsers = [
        'timestamp', 'relative-time', 'custom-formats', 'absolute-time', 'no-spaces-time'
    ]  # FIXME: Extract the list of existing parsers from another place (#798)
    unknown_parsers = set(setting_value) - set(existing_parsers)
    if unknown_parsers:
        raise SettingValidationError(
            'Found unknown parsers in the "{}" setting: {}'.format(
                setting_name, ', '.join(unknown_parsers)
            )
        )
    _check_repeated_values(setting_name, setting_value)


def check_settings(settings):
    """
    Check if provided settings are valid, if not it raises `SettingValidationError`.
    Only checks for the modified settings.
    """
    settings_values = {
        'DATE_ORDER': {
            'values': tuple(date_order_chart.keys()),
            'type': str,
        },
        'TIMEZONE': {
            # we don't check invalid Timezones as they raise an error
            'type': str,
        },
        'TO_TIMEZONE': {
            # It defaults to None, but it's not allowed to use it directly
            # "values" can take unlimited options
            'type': str
        },
        'RETURN_AS_TIMEZONE_AWARE': {
            # It defaults to 'default', but it's not allowed to use it directly
            'type': bool
        },
        'PREFER_DAY_OF_MONTH': {
            'values': ('current', 'first', 'last'),
            'type': str
        },
        'PREFER_DATES_FROM': {
            'values': ('current_period', 'past', 'future'),
            'type': str,
        },
        'RELATIVE_BASE': {
            # "values" can take unlimited options
            'type': datetime
        },
        'STRICT_PARSING': {
            'type': bool
        },
        'REQUIRE_PARTS': {
            # "values" covered by the 'extra_check'
            'type': list,
            'extra_check': _check_require_part
        },
        'SKIP_TOKENS': {
            # "values" can take unlimited options
            'type': list,
        },
        'NORMALIZE': {
            'type': bool
        },
        'RETURN_TIME_AS_PERIOD': {
            'type': bool
        },
        'PARSERS': {
            # "values" covered by the 'extra_check'
            'type': list,
            'extra_check': _check_parsers
        },
        'FUZZY': {
            'type': bool
        },
        'PREFER_LOCALE_DATE_ORDER': {
            'type': bool
        },
    }

    modified_settings = settings._mod_settings  # check only modified settings

    # check settings keys:
    for setting in modified_settings:
        if setting not in settings_values:
            raise SettingValidationError('"{}" is not a valid setting'.format(setting))

    for setting_name, setting_value in modified_settings.items():
        setting_type = type(setting_value)
        setting_props = settings_values[setting_name]

        # check type:
        if not setting_type == setting_props['type']:
            raise SettingValidationError(
                '"{}" must be "{}", not "{}".'.format(
                    setting_name, setting_props['type'].__name__, setting_type.__name__
                )
            )

        # check values:
        if setting_props.get('values') and setting_value not in setting_props['values']:
            raise SettingValidationError(
                '"{}" is not a valid value for "{}", it should be: "{}" or "{}"'.format(
                    setting_value,
                    setting_name,
                    '", "'.join(setting_props['values'][:-1]),
                    setting_props['values'][-1],
                )
            )

        # specific checks
        extra_check = setting_props.get('extra_check')
        if extra_check:
            extra_check(setting_name, setting_value)

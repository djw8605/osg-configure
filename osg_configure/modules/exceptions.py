""" Exceptions used in configuration script """


class ConfigurationError(Exception):
    """Base exception class for all exceptions defined"""
    pass


class SettingError(Exception):
    """Class for exceptions due to missing setting or due to an invalid value for a setting"""
    pass


class ApplicationError(Exception):
    """Class for exceptions due to an application error at runtime"""
    pass


class ConfigureError(ApplicationError):
    """Class for exceptions due to problems while running vdt configure scripts"""
    pass

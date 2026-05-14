class BootstrapError(Exception):
    """Base error for application bootstrap failures."""


class ConfigError(BootstrapError):
    """Raised when configuration cannot be loaded or validated."""


class ServiceRegistrationError(BootstrapError):
    """Raised when a runtime service cannot be registered safely."""


class ApplicationStateError(BootstrapError):
    """Raised when the application lifecycle is used incorrectly."""


class HealthServiceError(BootstrapError):
    """Raised when the health HTTP service cannot be started."""

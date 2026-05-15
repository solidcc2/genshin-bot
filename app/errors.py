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


class AppError(Exception):
    """Base error for runtime errors during normal operation."""


class PluginError(AppError):
    """Raised when a plugin encounters an error during match or handle."""


class StorageError(AppError):
    """Raised when a storage operation fails."""


class SessionError(AppError):
    """Raised when a session operation fails."""


class RateLimitError(AppError):
    """Raised when the rate limiter encounters an error."""


class HoyolabError(AppError):
    """Base error for HoYoLAB provider operations."""


class AuthError(HoyolabError):
    """Raised when QR code login fails."""


class ApiError(HoyolabError):
    """Raised when a HoYoLAB API call fails."""


class NotBoundError(HoyolabError):
    """Raised when the user has no bound HoYoLAB cookies."""

import logging
import warnings

logger = logging.getLogger(__name__)

# Safely import pyvips to handle cases where the system library (libvips) is missing.
# Standard 'import pyvips' can raise OSError even if the python package is installed.
try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import pyvips
except Exception:
    logger.warning("pyvips library not found; image processing features will be disabled.")
    pyvips = None

__all__ = ["pyvips"]

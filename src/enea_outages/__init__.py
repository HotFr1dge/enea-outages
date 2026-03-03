from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("enea-outages")
except PackageNotFoundError:
    # Fallback for when the package is not installed (e.g., in development)
    __version__ = "0.0.0-dev"

from .client import EneaOutagesClient
from .models import Outage, OutageType

__all__ = ["EneaOutagesClient", "Outage", "OutageType"]
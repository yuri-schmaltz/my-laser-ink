import inspect
from typing import Type, cast
from .grbl_adapter import GrblAdapter
from .meerk40t_adapter import Meerk40tAdapter
from .laserweb_adapter import LaserWebAdapter
from .driver import Driver
from .dummy import NoDeviceDriver
from .grbl import GrblNetworkDriver
from .grbl_serial import GrblSerialDriver
from .smoothie import SmoothieDriver


def isdriver(obj):
    return (
        inspect.isclass(obj) and issubclass(obj, Driver) and obj is not Driver
    )


drivers = [
    cast(Type[Driver], obj) for obj in list(locals().values()) if isdriver(obj)
]

driver_by_classname = dict([(o.__name__, o) for o in drivers])


def get_driver_cls(classname: str, default=NoDeviceDriver):
    # Map old "GrblSerialDriver" name to new Adapter if preferred, 
    # or just let user select "GrblAdapter" (Label: GRBL (New)).
    # For integration, let's expose GrblAdapter.
    return driver_by_classname.get(classname, default)


def register_driver(driver: Type[Driver]):
    driver_by_classname[driver.__name__] = driver
    drivers.append(driver)


__all__ = [
    "Driver",
    "NoDeviceDriver",
    "GrblNetworkDriver",
    "GrblSerialDriver",
    "GrblAdapter",
    "Meerk40tAdapter",
    "LaserWebAdapter",
    "SmoothieDriver",
]

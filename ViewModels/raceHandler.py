from PySide6.QtCore import QObject

# NOTE: this is to avoid circular imports
class RaceHandler(QObject):
    """
    _This is the object that will handle the signals and communication between each VM, I am just losing my mind rn_
    """
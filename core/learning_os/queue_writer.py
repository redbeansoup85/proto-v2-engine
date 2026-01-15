from typing import Protocol, Dict, Any


class QueueWriter(Protocol):
    """
    Abstract queue writer interface.

    Implementations may write to:
    - in-memory list
    - JSONL file
    - DB table
    - message queue
    - your existing approval queue ingress

    The producer should depend only on this interface.
    """
    def write(self, item: Dict[str, Any]) -> None:
        ...

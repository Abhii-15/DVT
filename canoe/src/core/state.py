from dataclasses import dataclass


@dataclass
class RuntimeCounters:
    tx_count: int = 0
    rx_count: int = 0
    active_cyclic_messages: int = 0

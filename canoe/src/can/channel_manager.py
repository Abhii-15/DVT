"""
channel_manager.py
------------------
Manages CAN channels with independent tx/rx queues and assigned databases.

Each channel represents a separate CAN bus with isolated message routing.
Multiple databases can share a channel; one database can map to only one channel.
"""

from __future__ import annotations

import logging
import queue
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Channel:
    """Represents a single CAN channel with isolated message queues."""

    channel_id: int
    bus_type: str = "CAN"  # "CAN", "LIN", "Ethernet", etc.
    is_active: bool = True
    assigned_databases: List[str] = field(default_factory=list)

    # Message queues for this channel
    _tx_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=1000))
    _rx_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=1000))

    @property
    def tx_queue(self) -> queue.Queue:
        """Transmit queue for this channel."""
        return self._tx_queue

    @property
    def rx_queue(self) -> queue.Queue:
        """Receive queue for this channel."""
        return self._rx_queue

    def add_database(self, database_name: str) -> None:
        """Register a database to this channel."""
        if database_name not in self.assigned_databases:
            self.assigned_databases.append(database_name)
            logger.debug(f"Database '{database_name}' assigned to channel {self.channel_id}")

    def remove_database(self, database_name: str) -> None:
        """Unregister a database from this channel."""
        if database_name in self.assigned_databases:
            self.assigned_databases.remove(database_name)
            logger.debug(f"Database '{database_name}' removed from channel {self.channel_id}")

    def has_database(self, database_name: str) -> bool:
        """Check if a database is assigned to this channel."""
        return database_name in self.assigned_databases

    def get_status(self) -> dict:
        """Return channel status snapshot."""
        return {
            "channel_id": self.channel_id,
            "bus_type": self.bus_type,
            "is_active": self.is_active,
            "assigned_databases": list(self.assigned_databases),
            "tx_queue_size": self.tx_queue.qsize(),
            "rx_queue_size": self.rx_queue.qsize(),
        }


class ChannelManager:
    """
    Manages all CAN channels and their message routing.

    Channels are independent buses. Multiple databases can share one channel.
    One database maps to exactly one channel.
    """

    def __init__(self) -> None:
        self._channels: Dict[int, Channel] = {}
        self._channel_counter = 0

    def create_channel(self, bus_type: str = "CAN") -> Channel:
        """Create a new channel and return it."""
        channel_id = self._channel_counter
        self._channel_counter += 1
        channel = Channel(channel_id=channel_id, bus_type=bus_type)
        self._channels[channel_id] = channel
        logger.info(f"Created channel {channel_id} ({bus_type})")
        return channel

    def get_channel(self, channel_id: int) -> Optional[Channel]:
        """Retrieve a channel by ID."""
        return self._channels.get(channel_id)

    def get_all_channels(self) -> List[Channel]:
        """Return all active channels."""
        return list(self._channels.values())

    def assign_database_to_channel(self, database_name: str, channel_id: int) -> bool:
        """Assign a database to a specific channel."""
        channel = self.get_channel(channel_id)
        if channel is None:
            logger.error(f"Channel {channel_id} not found")
            return False
        channel.add_database(database_name)
        return True

    def remove_database_from_channel(self, database_name: str, channel_id: int) -> bool:
        """Remove a database from a channel."""
        channel = self.get_channel(channel_id)
        if channel is None:
            return False
        channel.remove_database(database_name)
        return True

    def get_channels_for_database(self, database_name: str) -> List[Channel]:
        """Get all channels that have a specific database assigned."""
        return [ch for ch in self._channels.values() if ch.has_database(database_name)]

    def get_all_databases_in_channel(self, channel_id: int) -> List[str]:
        """Get all databases assigned to a specific channel."""
        channel = self.get_channel(channel_id)
        return channel.assigned_databases if channel else []

    def send_message_to_channel(self, channel_id: int, message_data: dict) -> bool:
        """
        Put a message in the tx_queue of a specific channel.

        message_data: {
            'message_id': int,
            'data': bytes,
            'timestamp': float,
            'database_name': str (optional)
        }
        """
        channel = self.get_channel(channel_id)
        if channel is None or not channel.is_active:
            logger.warning(f"Cannot send to channel {channel_id}: not found or inactive")
            return False
        try:
            channel.tx_queue.put_nowait(message_data)
            return True
        except queue.Full:
            logger.error(f"TX queue full on channel {channel_id}")
            return False

    def receive_message_from_channel(self, channel_id: int, timeout: float = 0.1) -> Optional[dict]:
        """
        Get a message from the rx_queue of a specific channel.

        Returns None if queue is empty or timeout occurs.
        """
        channel = self.get_channel(channel_id)
        if channel is None:
            return None
        try:
            return channel.rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def push_to_channel_rx(self, channel_id: int, message_data: dict) -> bool:
        """Push a received message into a channel's RX queue."""
        channel = self.get_channel(channel_id)
        if channel is None:
            return False
        try:
            channel.rx_queue.put_nowait(message_data)
            return True
        except queue.Full:
            logger.error(f"RX queue full on channel {channel_id}")
            return False

    def deactivate_channel(self, channel_id: int) -> bool:
        """Deactivate a channel (no more messages routed)."""
        channel = self.get_channel(channel_id)
        if channel:
            channel.is_active = False
            logger.info(f"Channel {channel_id} deactivated")
            return True
        return False

    def activate_channel(self, channel_id: int) -> bool:
        """Reactivate a channel."""
        channel = self.get_channel(channel_id)
        if channel:
            channel.is_active = True
            logger.info(f"Channel {channel_id} activated")
            return True
        return False

    def get_all_status(self) -> Dict[int, dict]:
        """Return status of all channels."""
        return {ch.channel_id: ch.get_status() for ch in self._channels.values()}

    def clear_all_queues(self) -> None:
        """Clear all TX/RX queues (for reset)."""
        for channel in self._channels.values():
            while not channel.tx_queue.empty():
                try:
                    channel.tx_queue.get_nowait()
                except queue.Empty:
                    break
            while not channel.rx_queue.empty():
                try:
                    channel.rx_queue.get_nowait()
                except queue.Empty:
                    break
        logger.info("All channel queues cleared")

"""
router.py
---------
Message routing engine for channel-based isolation.

Routes incoming and outgoing CAN messages to appropriate channels based on
database-to-channel assignments.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .channel_manager import ChannelManager
from .database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class Router:
    """
    Routes CAN messages to appropriate channels based on database assignments.

    Ensures message isolation: messages from one database/channel do not leak
    to other channels.
    """

    def __init__(self, channel_manager: ChannelManager, database_manager: DatabaseManager):
        """
        Initialize the router.

        Args:
            channel_manager: ChannelManager instance
            database_manager: DatabaseManager instance
        """
        self._channel_manager = channel_manager
        self._database_manager = database_manager
        self._message_to_channel_map: Dict[int, int] = {}

    def rebuild_routing_map(self) -> Dict[int, int]:
        """
        Rebuild the message_id -> channel_id mapping from current database assignments.

        Called when:
        - A database is added/removed
        - A database is assigned/unassigned from a channel
        - A database is activated/deactivated

        Returns:
            The rebuilt mapping dict
        """
        self._message_to_channel_map = (
            self._database_manager.rebuild_message_to_channel_mapping()
        )
        logger.info(
            f"Routing map rebuilt with {len(self._message_to_channel_map)} message routes"
        )
        return self._message_to_channel_map

    def get_channel_for_message(self, message_id: int) -> Optional[int]:
        """Get the channel ID for a message (lookup in routing map)."""
        return self._message_to_channel_map.get(message_id)

    def route_rx_message(self, message_id: int, message_data: Any) -> bool:
        """
        Route an incoming CAN message to its assigned channel.

        Args:
            message_id: CAN message ID
            message_data: Message data/object

        Returns:
            True if routed successfully, False if no route found
        """
        channel_id = self.get_channel_for_message(message_id)
        if channel_id is None:
            logger.debug(f"No route found for RX message ID {message_id}")
            return False

        try:
            self._channel_manager.push_to_channel_rx(channel_id, message_data)
            logger.debug(f"RX message {message_id} routed to channel {channel_id}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to route RX message {message_id} to channel {channel_id}: {e}"
            )
            return False

    def route_tx_message(self, message_id: int, message_data: Any) -> bool:
        """
        Route an outgoing CAN message from its assigned channel.

        Args:
            message_id: CAN message ID
            message_data: Message data/object

        Returns:
            True if routed successfully, False if no route found
        """
        channel_id = self.get_channel_for_message(message_id)
        if channel_id is None:
            logger.debug(f"No route found for TX message ID {message_id}")
            return False

        try:
            self._channel_manager.send_message_to_channel(channel_id, message_data)
            logger.debug(f"TX message {message_id} routed from channel {channel_id}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to route TX message {message_id} from channel {channel_id}: {e}"
            )
            return False

    def get_message_source_database(self, message_id: int) -> Optional[str]:
        """Get the source database name for a message."""
        db = self._database_manager.find_message_database(message_id)
        return db.name if db else None

    def get_message_source_channel(self, message_id: int) -> Optional[int]:
        """Get the source channel for a message."""
        db = self._database_manager.find_message_database(message_id)
        return db.assigned_channel if db and db.assigned_channel is not None else None

    def get_routing_status(self) -> dict:
        """Return current routing status."""
        return {
            "total_routes": len(self._message_to_channel_map),
            "channels_active": len(self._channel_manager._channels),
            "databases_assigned": len(
                self._database_manager.get_all_assigned_channels()
            ),
            "route_map_size": len(self._message_to_channel_map),
        }

    def get_routing_info_for_message(self, message_id: int) -> dict:
        """Get detailed routing info for a specific message."""
        channel_id = self.get_channel_for_message(message_id)
        db = self._database_manager.find_message_database(message_id)

        return {
            "message_id": message_id,
            "source_database": db.name if db else None,
            "assigned_channel": db.assigned_channel if db else None,
            "is_routed": channel_id is not None,
            "route_destination": channel_id,
        }

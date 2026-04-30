"""
database_manager.py
-------------------
Manages loaded DBC files and their channel assignments.

Each database tracks its parsed messages and the channel it is assigned to.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Database:
    """Represents a loaded DBC database."""

    name: str
    file_path: Path
    assigned_channel: Optional[int] = None
    messages: Dict[int, Any] = field(default_factory=dict)  # message_id -> message_data
    signals: Dict[int, Dict[str, Any]] = field(default_factory=dict)  # message_id -> signals
    is_active: bool = True

    def get_message(self, message_id: int) -> Optional[Any]:
        """Retrieve a message by ID."""
        return self.messages.get(message_id)

    def get_signals_for_message(self, message_id: int) -> Dict[str, Any]:
        """Get all signals for a message."""
        return self.signals.get(message_id, {})

    def get_all_message_ids(self) -> List[int]:
        """Return all message IDs in this database."""
        return list(self.messages.keys())

    def get_status(self) -> dict:
        """Return database status snapshot."""
        return {
            "name": self.name,
            "file_path": str(self.file_path),
            "assigned_channel": self.assigned_channel,
            "is_active": self.is_active,
            "message_count": len(self.messages),
            "signal_count": sum(len(sigs) for sigs in self.signals.values()),
        }


class DatabaseManager:
    """
    Manages all loaded DBC databases and their channel assignments.

    Ensures:
    - One database maps to exactly one channel
    - Multiple databases can share a channel
    - Channel assignment updates are tracked
    """

    def __init__(self) -> None:
        self._databases: Dict[str, Database] = {}

    def add_database(
        self,
        name: str,
        file_path: Path,
        messages: Dict[int, Any],
        signals: Dict[int, Dict[str, Any]],
    ) -> Database:
        """
        Register a new database.

        Args:
            name: Unique database name
            file_path: Path to the DBC file
            messages: Dict mapping message_id -> message_data
            signals: Dict mapping message_id -> {signal_name -> signal_data}

        Returns:
            The created Database object
        """
        db = Database(name=name, file_path=file_path, messages=messages, signals=signals)
        self._databases[name] = db
        logger.info(f"Database '{name}' registered with {len(messages)} messages")
        return db

    def get_database(self, name: str) -> Optional[Database]:
        """Retrieve a database by name."""
        return self._databases.get(name)

    def get_all_databases(self) -> List[Database]:
        """Return all registered databases."""
        return list(self._databases.values())

    def remove_database(self, name: str) -> bool:
        """Remove a database from the manager."""
        if name in self._databases:
            del self._databases[name]
            logger.info(f"Database '{name}' removed")
            return True
        return False

    def assign_to_channel(self, database_name: str, channel_id: int) -> bool:
        """
        Assign a database to a channel.

        Note: Database can only be assigned to one channel at a time.
        """
        db = self.get_database(database_name)
        if db is None:
            logger.error(f"Database '{database_name}' not found")
            return False

        # Unassign from previous channel if any
        if db.assigned_channel is not None:
            old_channel = db.assigned_channel
            db.assigned_channel = None
            logger.debug(f"Database '{database_name}' unassigned from channel {old_channel}")

        # Assign to new channel
        db.assigned_channel = channel_id
        logger.info(f"Database '{database_name}' assigned to channel {channel_id}")
        return True

    def unassign_from_channel(self, database_name: str) -> bool:
        """Unassign a database from its channel."""
        db = self.get_database(database_name)
        if db is None:
            return False
        if db.assigned_channel is not None:
            old_channel = db.assigned_channel
            db.assigned_channel = None
            logger.info(f"Database '{database_name}' unassigned from channel {old_channel}")
            return True
        return False

    def get_databases_for_channel(self, channel_id: int) -> List[Database]:
        """Get all databases assigned to a specific channel."""
        return [db for db in self._databases.values() if db.assigned_channel == channel_id]

    def get_channel_for_database(self, database_name: str) -> Optional[int]:
        """Get the channel a database is assigned to (if any)."""
        db = self.get_database(database_name)
        return db.assigned_channel if db else None

    def find_message_database(self, message_id: int) -> Optional[Database]:
        """
        Find which database contains a specific message ID.

        Returns the first database that has this message_id.
        """
        for db in self._databases.values():
            if message_id in db.messages:
                return db
        return None

    def find_database_by_message_in_channel(
        self, message_id: int, channel_id: int
    ) -> Optional[Database]:
        """
        Find a database that:
        1. Is assigned to the given channel
        2. Contains the given message_id

        Returns None if not found.
        """
        for db in self.get_databases_for_channel(channel_id):
            if message_id in db.messages:
                return db
        return None

    def activate_database(self, database_name: str) -> bool:
        """Activate a database (enable message routing)."""
        db = self.get_database(database_name)
        if db:
            db.is_active = True
            logger.debug(f"Database '{database_name}' activated")
            return True
        return False

    def deactivate_database(self, database_name: str) -> bool:
        """Deactivate a database (disable message routing)."""
        db = self.get_database(database_name)
        if db:
            db.is_active = False
            logger.debug(f"Database '{database_name}' deactivated")
            return True
        return False

    def get_all_assigned_channels(self) -> Dict[str, int]:
        """Return mapping of database_name -> channel_id for all assigned databases."""
        return {
            db.name: db.assigned_channel
            for db in self._databases.values()
            if db.assigned_channel is not None
        }

    def get_all_status(self) -> Dict[str, dict]:
        """Return status of all databases."""
        return {db.name: db.get_status() for db in self._databases.values()}

    def rebuild_message_to_channel_mapping(self) -> Dict[int, int]:
        """
        Build a flat mapping of message_id -> channel_id for all active databases.

        Used by the router to quickly look up which channel a message belongs to.
        """
        mapping = {}
        for db in self._databases.values():
            if db.is_active and db.assigned_channel is not None:
                for msg_id in db.get_all_message_ids():
                    mapping[msg_id] = db.assigned_channel
        return mapping

"""
test_channel_system.py
----------------------
Unit tests for Channel Mapping System (ChannelManager, DatabaseManager, Router).

Tests:
- Channel creation and management
- Database registration and channel assignment
- Message routing via Router
- Channel isolation and queue management
"""

import pytest
from pathlib import Path

from src.can import Channel, ChannelManager, Database, DatabaseManager, Router


class TestChannel:
    """Tests for Channel dataclass."""

    def test_channel_creation(self):
        """Test creating a channel."""
        channel = Channel(channel_id=0, bus_type="CAN")
        assert channel.channel_id == 0
        assert channel.bus_type == "CAN"
        assert channel.is_active is True
        assert channel.assigned_databases == []

    def test_channel_queue_isolation(self):
        """Test that TX and RX queues are isolated."""
        ch1 = Channel(channel_id=0, bus_type="CAN")
        ch2 = Channel(channel_id=1, bus_type="CAN")

        # Put in ch1 TX
        ch1.tx_queue.put({"msg": "ch1_tx"})

        # Put in ch2 RX
        ch2.rx_queue.put({"msg": "ch2_rx"})

        # Queues should not cross
        assert ch1.tx_queue.qsize() == 1
        assert ch1.rx_queue.qsize() == 0
        assert ch2.tx_queue.qsize() == 0
        assert ch2.rx_queue.qsize() == 1

    def test_channel_add_database(self):
        """Test adding database to channel."""
        channel = Channel(channel_id=0)
        channel.add_database("CAN_DB")
        assert channel.has_database("CAN_DB")
        assert "CAN_DB" in channel.assigned_databases

    def test_channel_remove_database(self):
        """Test removing database from channel."""
        channel = Channel(channel_id=0)
        channel.add_database("CAN_DB")
        channel.remove_database("CAN_DB")
        assert not channel.has_database("CAN_DB")


class TestChannelManager:
    """Tests for ChannelManager."""

    def test_create_channel(self):
        """Test creating channels."""
        mgr = ChannelManager()
        ch0 = mgr.create_channel("CAN")
        ch1 = mgr.create_channel("LIN")

        assert ch0.channel_id == 0
        assert ch1.channel_id == 1
        assert ch0.bus_type == "CAN"
        assert ch1.bus_type == "LIN"

    def test_get_channel(self):
        """Test retrieving a channel."""
        mgr = ChannelManager()
        ch = mgr.create_channel()
        retrieved = mgr.get_channel(0)

        assert retrieved is not None
        assert retrieved.channel_id == 0

    def test_get_all_channels(self):
        """Test getting all channels."""
        mgr = ChannelManager()
        mgr.create_channel()
        mgr.create_channel()
        mgr.create_channel()

        all_ch = mgr.get_all_channels()
        assert len(all_ch) == 3

    def test_send_message_to_channel(self):
        """Test sending message to channel."""
        mgr = ChannelManager()
        ch = mgr.create_channel()

        msg = {"message_id": 0x123, "data": b"\x01\x02"}
        result = mgr.send_message_to_channel(ch.channel_id, msg)

        assert result is True
        assert ch.tx_queue.qsize() == 1
        assert ch.tx_queue.get_nowait() == msg

    def test_receive_message_from_channel(self):
        """Test receiving message from channel."""
        mgr = ChannelManager()
        ch = mgr.create_channel()

        msg = {"message_id": 0x456, "data": b"\x03\x04"}
        ch.rx_queue.put(msg)

        received = mgr.receive_message_from_channel(ch.channel_id)
        assert received == msg

    def test_channel_isolation(self):
        """Test that messages don't leak between channels."""
        mgr = ChannelManager()
        ch0 = mgr.create_channel()
        ch1 = mgr.create_channel()

        mgr.send_message_to_channel(ch0.channel_id, {"msg": "to_ch0"})
        mgr.send_message_to_channel(ch1.channel_id, {"msg": "to_ch1"})

        # Each channel should only have its own message
        assert ch0.tx_queue.qsize() == 1
        assert ch1.tx_queue.qsize() == 1
        assert ch0.tx_queue.get_nowait()["msg"] == "to_ch0"
        assert ch1.tx_queue.get_nowait()["msg"] == "to_ch1"


class TestDatabase:
    """Tests for Database dataclass."""

    def test_database_creation(self):
        """Test creating a database."""
        db = Database(
            name="TestDB",
            file_path=Path("test.dbc"),
            messages={0x100: {"name": "MSG1"}},
            signals={0x100: {"SIG1": {}}},
        )

        assert db.name == "TestDB"
        assert db.assigned_channel is None
        assert db.is_active is True

    def test_get_message(self):
        """Test retrieving a message."""
        msg_data = {"name": "MSG1", "dlc": 8}
        db = Database(
            name="TestDB",
            file_path=Path("test.dbc"),
            messages={0x100: msg_data},
            signals={},
        )

        retrieved = db.get_message(0x100)
        assert retrieved == msg_data

    def test_get_all_message_ids(self):
        """Test getting all message IDs."""
        db = Database(
            name="TestDB",
            file_path=Path("test.dbc"),
            messages={0x100: {}, 0x101: {}, 0x102: {}},
            signals={},
        )

        ids = db.get_all_message_ids()
        assert sorted(ids) == [0x100, 0x101, 0x102]


class TestDatabaseManager:
    """Tests for DatabaseManager."""

    def test_add_database(self):
        """Test adding a database."""
        mgr = DatabaseManager()
        db = mgr.add_database(
            name="TestDB",
            file_path=Path("test.dbc"),
            messages={0x100: {"name": "MSG1"}},
            signals={0x100: {"SIG1": {}}},
        )

        assert db.name == "TestDB"
        assert mgr.get_database("TestDB") is not None

    def test_get_all_databases(self):
        """Test getting all databases."""
        mgr = DatabaseManager()
        mgr.add_database("DB1", Path("db1.dbc"), {0x100: {}}, {})
        mgr.add_database("DB2", Path("db2.dbc"), {0x200: {}}, {})

        all_dbs = mgr.get_all_databases()
        assert len(all_dbs) == 2

    def test_remove_database(self):
        """Test removing a database."""
        mgr = DatabaseManager()
        mgr.add_database("TestDB", Path("test.dbc"), {}, {})
        result = mgr.remove_database("TestDB")

        assert result is True
        assert mgr.get_database("TestDB") is None

    def test_assign_to_channel(self):
        """Test assigning a database to a channel."""
        mgr = DatabaseManager()
        mgr.add_database("TestDB", Path("test.dbc"), {}, {})
        result = mgr.assign_to_channel("TestDB", 0)

        assert result is True
        db = mgr.get_database("TestDB")
        assert db.assigned_channel == 0

    def test_unassign_from_channel(self):
        """Test unassigning a database from a channel."""
        mgr = DatabaseManager()
        mgr.add_database("TestDB", Path("test.dbc"), {}, {})
        mgr.assign_to_channel("TestDB", 0)
        result = mgr.unassign_from_channel("TestDB")

        assert result is True
        db = mgr.get_database("TestDB")
        assert db.assigned_channel is None

    def test_get_databases_for_channel(self):
        """Test getting databases for a specific channel."""
        mgr = DatabaseManager()
        mgr.add_database("DB1", Path("db1.dbc"), {0x100: {}}, {})
        mgr.add_database("DB2", Path("db2.dbc"), {0x200: {}}, {})
        mgr.add_database("DB3", Path("db3.dbc"), {0x300: {}}, {})

        mgr.assign_to_channel("DB1", 0)
        mgr.assign_to_channel("DB2", 0)
        mgr.assign_to_channel("DB3", 1)

        ch0_dbs = mgr.get_databases_for_channel(0)
        assert len(ch0_dbs) == 2
        assert set(db.name for db in ch0_dbs) == {"DB1", "DB2"}

    def test_find_message_database(self):
        """Test finding which database contains a message."""
        mgr = DatabaseManager()
        mgr.add_database("DB1", Path("db1.dbc"), {0x100: {"name": "MSG1"}}, {})
        mgr.add_database("DB2", Path("db2.dbc"), {0x200: {"name": "MSG2"}}, {})

        db1 = mgr.find_message_database(0x100)
        db2 = mgr.find_message_database(0x200)

        assert db1.name == "DB1"
        assert db2.name == "DB2"

    def test_rebuild_mapping(self):
        """Test rebuilding message-to-channel mapping."""
        mgr = DatabaseManager()
        mgr.add_database("DB1", Path("db1.dbc"), {0x100: {}, 0x101: {}}, {})
        mgr.add_database("DB2", Path("db2.dbc"), {0x200: {}}, {})

        mgr.assign_to_channel("DB1", 0)
        mgr.assign_to_channel("DB2", 1)

        mapping = mgr.rebuild_message_to_channel_mapping()

        assert mapping[0x100] == 0
        assert mapping[0x101] == 0
        assert mapping[0x200] == 1


class TestRouter:
    """Tests for Router."""

    def test_router_creation(self):
        """Test creating a router."""
        cm = ChannelManager()
        dm = DatabaseManager()
        router = Router(cm, dm)

        assert router._channel_manager is cm
        assert router._database_manager is dm

    def test_rebuild_routing_map(self):
        """Test rebuilding the routing map."""
        cm = ChannelManager()
        dm = DatabaseManager()
        router = Router(cm, dm)

        dm.add_database("DB1", Path("db1.dbc"), {0x100: {}, 0x101: {}}, {})
        dm.assign_to_channel("DB1", 0)

        mapping = router.rebuild_routing_map()

        assert 0x100 in mapping
        assert 0x101 in mapping
        assert mapping[0x100] == 0
        assert mapping[0x101] == 0

    def test_get_channel_for_message(self):
        """Test looking up channel for a message."""
        cm = ChannelManager()
        dm = DatabaseManager()
        router = Router(cm, dm)

        dm.add_database("DB1", Path("db1.dbc"), {0x100: {}}, {})
        dm.assign_to_channel("DB1", 0)
        router.rebuild_routing_map()

        channel_id = router.get_channel_for_message(0x100)
        assert channel_id == 0

    def test_route_rx_message(self):
        """Test routing an RX message."""
        cm = ChannelManager()
        dm = DatabaseManager()
        router = Router(cm, dm)

        ch = cm.create_channel()
        dm.add_database("DB1", Path("db1.dbc"), {0x100: {}}, {})
        dm.assign_to_channel("DB1", ch.channel_id)
        router.rebuild_routing_map()

        msg = {"message_id": 0x100, "data": b"\x01"}
        result = router.route_rx_message(0x100, msg)

        assert result is True
        assert ch.rx_queue.qsize() == 1

    def test_route_tx_message(self):
        """Test routing a TX message."""
        cm = ChannelManager()
        dm = DatabaseManager()
        router = Router(cm, dm)

        ch = cm.create_channel()
        dm.add_database("DB1", Path("db1.dbc"), {0x100: {}}, {})
        dm.assign_to_channel("DB1", ch.channel_id)
        router.rebuild_routing_map()

        msg = {"message_id": 0x100, "data": b"\x01"}
        result = router.route_tx_message(0x100, msg)

        assert result is True
        assert ch.tx_queue.qsize() == 1

    def test_message_isolation(self):
        """Test that messages are isolated between channels."""
        cm = ChannelManager()
        dm = DatabaseManager()
        router = Router(cm, dm)

        ch0 = cm.create_channel("CAN")
        ch1 = cm.create_channel("CAN")

        dm.add_database("DB0", Path("db0.dbc"), {0x100: {}}, {})
        dm.add_database("DB1", Path("db1.dbc"), {0x200: {}}, {})

        dm.assign_to_channel("DB0", ch0.channel_id)
        dm.assign_to_channel("DB1", ch1.channel_id)

        router.rebuild_routing_map()

        # Route messages
        router.route_rx_message(0x100, {"msg": "for_ch0"})
        router.route_rx_message(0x200, {"msg": "for_ch1"})

        # Each channel should only have its message
        assert ch0.rx_queue.qsize() == 1
        assert ch1.rx_queue.qsize() == 1

        msg0 = ch0.rx_queue.get_nowait()
        msg1 = ch1.rx_queue.get_nowait()

        assert msg0["msg"] == "for_ch0"
        assert msg1["msg"] == "for_ch1"

    def test_no_route_for_message(self):
        """Test that unrouted messages are rejected."""
        cm = ChannelManager()
        dm = DatabaseManager()
        router = Router(cm, dm)

        # Don't add any database, so 0x999 has no route
        router.rebuild_routing_map()

        result = router.route_rx_message(0x999, {"msg": "orphan"})
        assert result is False


class TestChannelSystemIntegration:
    """Integration tests for the complete channel system."""

    def test_multi_channel_routing(self):
        """Test routing across multiple channels with multiple databases."""
        cm = ChannelManager()
        dm = DatabaseManager()
        router = Router(cm, dm)

        # Create 3 channels
        ch0 = cm.create_channel("CAN")
        ch1 = cm.create_channel("CAN")
        ch2 = cm.create_channel("LIN")

        # Create 5 databases with different message IDs
        dm.add_database("CAN_DB1", Path("can1.dbc"), {0x100: {}, 0x101: {}}, {})
        dm.add_database("CAN_DB2", Path("can2.dbc"), {0x200: {}, 0x201: {}}, {})
        dm.add_database("CAN_DB3", Path("can3.dbc"), {0x300: {}, 0x301: {}}, {})
        dm.add_database("LIN_DB1", Path("lin1.dbc"), {0x500: {}}, {})
        dm.add_database("LIN_DB2", Path("lin2.dbc"), {0x600: {}}, {})

        # Assign to channels
        dm.assign_to_channel("CAN_DB1", ch0.channel_id)
        dm.assign_to_channel("CAN_DB2", ch1.channel_id)
        dm.assign_to_channel("CAN_DB3", ch2.channel_id)
        dm.assign_to_channel("LIN_DB1", ch2.channel_id)
        dm.assign_to_channel("LIN_DB2", ch2.channel_id)

        router.rebuild_routing_map()

        # Route messages from different databases
        router.route_rx_message(0x100, {"source": "CAN_DB1", "ch": 0})
        router.route_rx_message(0x200, {"source": "CAN_DB2", "ch": 1})
        router.route_rx_message(0x500, {"source": "LIN_DB1", "ch": 2})
        router.route_rx_message(0x600, {"source": "LIN_DB2", "ch": 2})

        # Verify routing
        assert ch0.rx_queue.qsize() == 1
        assert ch1.rx_queue.qsize() == 1
        assert ch2.rx_queue.qsize() == 2

        assert ch0.rx_queue.get_nowait()["source"] == "CAN_DB1"
        assert ch1.rx_queue.get_nowait()["source"] == "CAN_DB2"

    def test_database_reassignment(self):
        """Test reassigning a database from one channel to another."""
        cm = ChannelManager()
        dm = DatabaseManager()
        router = Router(cm, dm)

        ch0 = cm.create_channel()
        ch1 = cm.create_channel()

        db = dm.add_database("TestDB", Path("test.dbc"), {0x100: {}}, {})
        dm.assign_to_channel("TestDB", ch0.channel_id)
        router.rebuild_routing_map()

        # Route to ch0
        router.route_rx_message(0x100, {"msg": "to_ch0"})
        assert ch0.rx_queue.qsize() == 1

        # Reassign to ch1
        dm.assign_to_channel("TestDB", ch1.channel_id)
        router.rebuild_routing_map()

        # Route to ch1
        router.route_rx_message(0x100, {"msg": "to_ch1"})
        assert ch1.rx_queue.qsize() == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

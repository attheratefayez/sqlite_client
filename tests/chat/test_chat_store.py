"""Tests for ChatStore persistence."""

from chat.chat_store import ChatStore


class TestChatStore:
    def test_create_conversation(self, tmp_path):
        store = ChatStore(db_path=str(tmp_path / "chat.db"))
        cid = store.create_conversation()
        assert isinstance(cid, int)
        assert cid > 0
        store.close()

    def test_add_and_get_messages(self, tmp_path):
        store = ChatStore(db_path=str(tmp_path / "chat.db"))
        cid = store.create_conversation("Test")
        store.add_message(cid, "user", "hello")
        store.add_message(cid, "assistant", "hi there")
        msgs = store.get_messages(cid)
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "hello"}
        assert msgs[1] == {"role": "assistant", "content": "hi there"}
        store.close()

    def test_get_conversations(self, tmp_path):
        store = ChatStore(db_path=str(tmp_path / "chat.db"))
        cid1 = store.create_conversation("Chat A")
        cid2 = store.create_conversation("Chat B")
        convs = store.get_conversations()
        assert len(convs) == 2
        assert convs[0]["title"] == "Chat B"
        assert convs[1]["title"] == "Chat A"
        store.close()

    def test_get_messages_empty(self, tmp_path):
        store = ChatStore(db_path=str(tmp_path / "chat.db"))
        cid = store.create_conversation()
        assert store.get_messages(cid) == []
        store.close()

    def test_multiple_conversations(self, tmp_path):
        store = ChatStore(db_path=str(tmp_path / "chat.db"))
        cid1 = store.create_conversation()
        cid2 = store.create_conversation()
        store.add_message(cid1, "user", "msg1")
        store.add_message(cid2, "user", "msg2")
        store.add_message(cid2, "assistant", "reply2")
        assert len(store.get_messages(cid1)) == 1
        assert len(store.get_messages(cid2)) == 2
        store.close()

    def test_add_message_updates_conversation_timestamp(self, tmp_path):
        store = ChatStore(db_path=str(tmp_path / "chat.db"))
        cid = store.create_conversation("Original")
        orig = store.get_conversations()[0]
        store.add_message(cid, "user", "new message")
        updated = store.get_conversations()[0]
        assert updated["updated_at"] >= orig["updated_at"]
        store.close()

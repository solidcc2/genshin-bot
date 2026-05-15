from __future__ import annotations

import pytest

from app.storage import create_storage
from app.storage.memory import MemoryStorage
from app.config import StorageConfig


@pytest.fixture(params=["memory", "sqlite"])
def storage(request):
    config = StorageConfig(backend=request.param)
    store = create_storage(config)
    yield store
    # cleanup after each test
    for key in ["key_a", "key_b", "ns1_key", "ns2_key", "to_delete", "ttl_key"]:
        pass  # storage-specific cleanup handled by namespace clearing


class TestMemoryStorage:
    @pytest.fixture
    def store(self):
        return MemoryStorage()

    @pytest.mark.anyio
    async def test_set_and_get(self, store) -> None:
        await store.set("ns", "mykey", {"hello": "world"})
        val = await store.get("ns", "mykey")
        assert val == {"hello": "world"}

    @pytest.mark.anyio
    async def test_get_missing(self, store) -> None:
        val = await store.get("ns", "nonexistent")
        assert val is None

    @pytest.mark.anyio
    async def test_get_missing_namespace(self, store) -> None:
        val = await store.get("no_such_ns", "key")
        assert val is None

    @pytest.mark.anyio
    async def test_delete_existing(self, store) -> None:
        await store.set("ns", "to_delete", "value")
        assert await store.delete("ns", "to_delete") is True
        assert await store.get("ns", "to_delete") is None

    @pytest.mark.anyio
    async def test_delete_missing(self, store) -> None:
        assert await store.delete("ns", "no_such_key") is False

    @pytest.mark.anyio
    async def test_list(self, store) -> None:
        await store.set("ns", "b_key", 1)
        await store.set("ns", "a_key", 2)
        keys = await store.list("ns")
        assert keys == ["a_key", "b_key"]

    @pytest.mark.anyio
    async def test_list_empty_namespace(self, store) -> None:
        keys = await store.list("empty_ns")
        assert keys == []

    @pytest.mark.anyio
    async def test_namespace_isolation(self, store) -> None:
        await store.set("ns1", "key", "ns1_value")
        await store.set("ns2", "key", "ns2_value")
        assert await store.get("ns1", "key") == "ns1_value"
        assert await store.get("ns2", "key") == "ns2_value"

    @pytest.mark.anyio
    async def test_ttl_expiry(self, store) -> None:
        await store.set("ns", "ttl_key", "expire_me", ttl=0.0)
        val = await store.get("ns", "ttl_key")
        assert val is None

    @pytest.mark.anyio
    async def test_set_overwrite(self, store) -> None:
        await store.set("ns", "key", "old")
        await store.set("ns", "key", "new")
        assert await store.get("ns", "key") == "new"

    @pytest.mark.anyio
    async def test_list_excludes_expired(self, store) -> None:
        await store.set("ns", "valid", "ok")
        await store.set("ns", "expired", "gone", ttl=0.0)
        keys = await store.list("ns")
        assert "expired" not in keys
        assert "valid" in keys

    @pytest.mark.anyio
    async def test_get_clears_expired_on_access(self, store) -> None:
        await store.set("ns", "expired", "gone", ttl=0.0)
        assert await store.get("ns", "expired") is None
        # should be removed from internal dict too
        assert "expired" not in store._data.get("ns", {})

    @pytest.mark.anyio
    async def test_close_clears_data(self, store) -> None:
        await store.set("ns", "key", "val")
        await store.close()
        assert await store.get("ns", "key") is None

    @pytest.mark.anyio
    async def test_complex_types(self, store) -> None:
        data = {"list": [1, 2, 3], "nested": {"a": 1}, "number": 42, "flag": True}
        await store.set("ns", "complex", data)
        assert await store.get("ns", "complex") == data


class TestSQLiteStorage:
    @pytest.fixture
    def store(self):
        config = StorageConfig(backend="sqlite", db_path=":memory:")
        return create_storage(config)

    @pytest.mark.anyio
    async def test_set_and_get(self, store) -> None:
        await store.set("ns", "mykey", {"hello": "world"})
        val = await store.get("ns", "mykey")
        assert val == {"hello": "world"}

    @pytest.mark.anyio
    async def test_get_missing(self, store) -> None:
        val = await store.get("ns", "nonexistent")
        assert val is None

    @pytest.mark.anyio
    async def test_delete_existing(self, store) -> None:
        await store.set("ns", "to_delete", "value")
        assert await store.delete("ns", "to_delete") is True
        assert await store.get("ns", "to_delete") is None

    @pytest.mark.anyio
    async def test_delete_missing(self, store) -> None:
        assert await store.delete("ns", "no_such_key") is False

    @pytest.mark.anyio
    async def test_list(self, store) -> None:
        await store.set("ns", "b_key", 1)
        await store.set("ns", "a_key", 2)
        keys = await store.list("ns")
        assert keys == ["a_key", "b_key"]

    @pytest.mark.anyio
    async def test_list_empty_namespace(self, store) -> None:
        keys = await store.list("empty_ns")
        assert keys == []

    @pytest.mark.anyio
    async def test_namespace_isolation(self, store) -> None:
        await store.set("ns1", "key", "ns1_value")
        await store.set("ns2", "key", "ns2_value")
        assert await store.get("ns1", "key") == "ns1_value"
        assert await store.get("ns2", "key") == "ns2_value"

    @pytest.mark.anyio
    async def test_ttl_expiry(self, store) -> None:
        await store.set("ns", "ttl_key", "expire_me", ttl=0.0)
        val = await store.get("ns", "ttl_key")
        assert val is None

    @pytest.mark.anyio
    async def test_set_overwrite(self, store) -> None:
        await store.set("ns", "key", "old")
        await store.set("ns", "key", "new")
        assert await store.get("ns", "key") == "new"

    @pytest.mark.anyio
    async def test_list_excludes_expired(self, store) -> None:
        await store.set("ns", "valid", "ok")
        await store.set("ns", "expired", "gone", ttl=0.0)
        keys = await store.list("ns")
        assert "expired" not in keys
        assert "valid" in keys

    @pytest.mark.anyio
    async def test_close(self, store) -> None:
        await store.set("ns", "key", "val")
        await store.close()

    @pytest.mark.anyio
    async def test_complex_types(self, store) -> None:
        data = {"list": [1, 2, 3], "nested": {"a": 1}, "number": 42, "flag": True}
        await store.set("ns", "complex", data)
        assert await store.get("ns", "complex") == data


class TestCreateStorage:
    def test_create_memory(self) -> None:
        config = StorageConfig(backend="memory")
        store = create_storage(config)
        from app.storage.memory import MemoryStorage
        assert isinstance(store, MemoryStorage)

    def test_create_sqlite(self) -> None:
        config = StorageConfig(backend="sqlite", db_path=":memory:")
        store = create_storage(config)
        from app.storage.sqlite import SQLiteStorage
        assert isinstance(store, SQLiteStorage)

    def test_unknown_backend(self) -> None:
        config = StorageConfig(backend="redis")
        with pytest.raises(ValueError, match="Unknown storage backend"):
            create_storage(config)

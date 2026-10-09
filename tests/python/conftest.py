import pytest
from fastapi.testclient import TestClient

from ultron.api import create_app
from ultron.config import Config


class FakeVault:
    def __init__(self):
        self.values = {}

    def get(self, name):
        return self.values.get(name)

    def put(self, name, value):
        self.values[name] = value

    def delete(self, name):
        self.values.pop(name, None)


@pytest.fixture
def client(tmp_path):
    app = create_app(Config(data_dir=tmp_path / "data", token="test-session"), FakeVault())
    with TestClient(app, headers={"Authorization": "Bearer test-session"}) as client:
        yield client


@pytest.fixture
def store(tmp_path):
    from ultron.store import Store
    result = Store(tmp_path / "ultron.sqlite3")
    yield result
    result.db.close()

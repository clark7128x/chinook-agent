import sqlite3

import pytest

from chinook_agent.database import ReadOnlyDatabase
from chinook_agent.llm import ChatResult
from chinook_agent.tools import Toolbox


@pytest.fixture
def mini_path(tmp_path):
    path = tmp_path / "mini.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE Artist(ArtistId INTEGER PRIMARY KEY, Name TEXT NOT NULL);
        CREATE TABLE Album(AlbumId INTEGER PRIMARY KEY, Title TEXT NOT NULL,
                           ArtistId INTEGER NOT NULL REFERENCES Artist(ArtistId));
        INSERT INTO Artist VALUES (1, 'AC/DC'), (2, 'Accept');
        INSERT INTO Album VALUES (1, 'For Those About To Rock', 1),
                                 (2, 'Balls to the Wall', 2),
                                 (3, 'Restless and Wild', 2);
        """
    )
    connection.commit()
    connection.close()
    return path


@pytest.fixture
def database(mini_path):
    return ReadOnlyDatabase(mini_path, timeout_s=1.0, max_rows=100)


@pytest.fixture
def toolbox(database):
    return Toolbox(database)


def tool_call(name: str, arguments: str, call_id: str = "c1") -> dict:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def assistant(calls: list[dict] | None = None, content: str | None = None) -> dict:
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return message


class ScriptedClient:
    def __init__(self, messages: list[dict]):
        self.messages = list(messages)
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools=None):
        self.calls.append(list(messages))
        if not self.messages:
            raise AssertionError("модель викликано більше разів, ніж очікувалось")
        return ChatResult(self.messages.pop(0), "scripted", 100, 20, 0.01)


@pytest.fixture
def scripted():
    return ScriptedClient

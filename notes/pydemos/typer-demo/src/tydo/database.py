import configparser
import json
from pathlib import Path
from typing import Any, NamedTuple

from tydo import DB_READ_ERROR, DB_WRITE_ERROR, JSON_ERROR, SUCCESS

DEFAULT_DB_FILE_PATH = Path(__file__).parent.parent.parent.joinpath(
    ".default_todo.json"
)


class DBResponse(NamedTuple):
    todo_list: list[dict[str, Any]]
    error: int


class DatabaseHandler:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def read_todos(self) -> DBResponse:
        try:
            with self._db_path.open("r") as db:
                try:
                    return DBResponse(json.load(db), SUCCESS)
                except json.JSONDecodeError:
                    return DBResponse([], JSON_ERROR)

        except OSError:
            return DBResponse([], DB_READ_ERROR)

    def write_todos(self, todo_list: list[dict[str, Any]]) -> DBResponse:
        try:
            with self._db_path.open("w") as db:
                json.dump(todo_list, db, indent=4)
            return DBResponse(todo_list, SUCCESS)
        except OSError:
            return DBResponse(todo_list, DB_WRITE_ERROR)


def get_database_path(config_file: Path) -> Path:
    config_parser = configparser.ConfigParser()
    config_parser.read(config_file)
    return Path(config_parser["General"]["database"])


def init_database(db_path: Path) -> int:
    try:
        db_path.write_text("[]")  # init an empty to-do list
    except OSError:
        return DB_WRITE_ERROR
    return SUCCESS

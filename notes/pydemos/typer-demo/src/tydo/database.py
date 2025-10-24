import configparser
from pathlib import Path

from tydo import DB_WRITE_ERROR, SUCCESS

DEFAULT_DB_FILE_PATH = Path(__file__).parent.parent.parent.joinpath(
    ".default_todo.json"
)


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

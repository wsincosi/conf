from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from tydo import ERRORS, __app_name__, __version__, config, database

app = typer.Typer()


@app.command()
def init(
    db_path: Annotated[
        str, typer.Option("--db-path", "-db", prompt="The to-do database location?")
    ] = str(database.DEFAULT_DB_FILE_PATH),
) -> None:
    """Initializes the to-do database"""

    app_init_error = config.init_app(db_path)
    if app_init_error:
        typer.secho(
            f"Creating config file failed with {ERRORS[app_init_error]}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    db_init_error = database.init_database(Path(db_path))
    if db_init_error:
        typer.secho(
            f"Creating database failed with {ERRORS[db_init_error]}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    else:
        typer.secho(f"The to-do database is {db_path}", fg=typer.colors.GREEN)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{__app_name__} version: {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Show the application's version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """The main entry point of the application."""
    return

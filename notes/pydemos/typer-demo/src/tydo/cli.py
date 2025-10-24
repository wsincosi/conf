from typing import Optional

import typer
from tydo import ERRORS, __app_name__, __version__
from typing_extensions import Annotated

app = typer.Typer()


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
    ],
) -> None:
    """The main entry point of the application."""
    return

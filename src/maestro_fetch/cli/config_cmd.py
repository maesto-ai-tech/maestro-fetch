"""Configuration management — `mfetch config init|show`.

Stub for Phase 2 implementation.
"""
from __future__ import annotations

import typer

app = typer.Typer(help="Configuration management.")


@app.command("init")
def init_config() -> None:
    """Generate default config file at ~/.maestro-fetch/config.toml."""
    typer.echo("config init: not yet implemented (Phase 2)")
    raise typer.Exit(code=0)


@app.command()
def show() -> None:
    """Show current configuration."""
    typer.echo("config show: not yet implemented (Phase 2)")
    raise typer.Exit(code=0)

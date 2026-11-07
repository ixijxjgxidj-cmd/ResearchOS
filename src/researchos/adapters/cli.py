"""Backward compatibility forwarding adapter for CLI."""

from researchos.interfaces.cli.main import app

if __name__ == "__main__":
    app()

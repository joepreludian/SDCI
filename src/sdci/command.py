from importlib.metadata import version

import click

__version__ = version("sdci")

from sdci.client import SDCIClient
from sdci.exceptions import SDCIException


@click.group()
def cli():
    print(f"@ SDCI CLI v{__version__}\n")
    """CLI application"""
    pass


@cli.command()
@click.option("--token", required=True, help="Token")
@click.argument("server", required=True)
@click.argument("task", required=True)
@click.argument("args", nargs=-1)
def run(token, server, task, args):
    """Run a task into the server"""

    print(f"Invoking Task {task} with args {args}...\n")
    try:
        client = SDCIClient(server, token)
        client.trigger(task, *args, action="run")
        output = client.trigger(task, ..., action="status")
        exit(output.exit_code)

    except SDCIException as exc:
        print(f"[Client Failed to execute task] - {exc}")
        exit(1)

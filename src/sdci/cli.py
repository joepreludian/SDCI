import os
from importlib.metadata import version

import click
import keyring

__version__ = version("sdci")

from sdci.client_service import SDCIClient
from sdci.exceptions import SDCIException


@click.group()
def entrypoint():
    print(f"[ SDCI-CLI v{__version__} ]")
    """CLI application"""
    pass


@entrypoint.command()
@click.option("--token", required=False, help="Token or env var SDCI_TOKEN")
@click.argument("server", required=False)
@click.argument("task", required=True)
@click.argument("args", nargs=-1)
def run(token, server, task, args):
    """Run a task into the server"""
    print(f"[ TASK RUN ] - Running {task} into server {server}...\n")

    if not token:
        token = os.environ.get("SDCI_TOKEN", None)

    if not token:
        token = keyring.get_password("SDCI_token", server)

    try:
        if not token:
            raise SDCIException(
                "TOKEN NOT FOUND - Please provide a token or set SDCI_TOKEN env var, or use 'sdci-cli store-token'"
            )

        client = SDCIClient(server, token)
        client.trigger(task, *args, action="run")
        output = client.trigger(task, ..., action="status")
        exit(output.exit_code)

    except SDCIException as exc:
        print(f"[Client Failed to execute task] - {exc}")
        exit(1)


@entrypoint.command(name="upload-asset")
@click.option("--token", required=False, help="Token or env var SDCI_TOKEN")
@click.argument("server", required=True)
@click.argument("local_file", required=True)
@click.argument("remote_path", required=True)
def upload_asset(token, server, local_file, remote_path):
    """Upload a single file (asset) to the server"""
    print(f"[ UPLOAD ASSET ] - Uploading {local_file} to {server} ({remote_path})...\n")

    if not token:
        token = os.environ.get("SDCI_TOKEN", None)

    if not token:
        token = keyring.get_password("SDCI_token", server)

    try:
        if not token:
            raise SDCIException(
                "TOKEN NOT FOUND - Please provide a token or set SDCI_TOKEN env var, or use 'sdci-cli store-token'"
            )

        if not os.path.isfile(local_file):
            raise SDCIException(f"LOCAL FILE NOT FOUND: {local_file}")

        client = SDCIClient(server, token)
        result = client.upload(local_file, remote_path)
        print(f"\n[ UPLOAD COMPLETE ] - {result.path} ({result.size} bytes)\n")

    except SDCIException as exc:
        print(f"[Client Failed to upload asset] - {exc}")
        exit(1)


@entrypoint.command()
@click.argument("server", required=True)
@click.argument("token", required=True)
def store_token(server, token):
    """Store the token in the local system"""
    keyring.set_password("SDCI_token", server, token)
    print(f"[ TOKEN STORED ] - Stored for {server}...\n")


@entrypoint.command()
@click.argument("server", required=True)
def delete_token(server):
    """Delete the token from the local system"""
    keyring.delete_password("SDCI_token", server)
    print(f"[ TOKEN DELETED ] - Deleted for {server}...\n")

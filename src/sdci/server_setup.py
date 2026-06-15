"""SystemdInstaller — service class for installing SDCI as a systemd unit."""

import getpass
import os
import shlex
import shutil
import string
import subprocess
import sys

import click

from sdci.exceptions import SDCIServerException

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_UNIT_TEMPLATE = string.Template(
    """\
[Unit]
Description=SDCI - Sidecar Micro CD server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$user
WorkingDirectory=$working_dir
EnvironmentFile=/etc/sdci/sdci.env
ExecStart="$binary" serve --host $ip --port $port --tasks-dir "$tasks_dir"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
)

_ENV_TEMPLATE = string.Template("SDCI_SERVER_TOKEN=$token\n")


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class SystemdInstaller:
    def __init__(
        self,
        *,
        ip: str,
        token: str,
        port: int = 8842,
        tasks_dir: str | None = None,
        user: str | None = None,
        service_name: str = "sdci",
        force: bool = False,
    ) -> None:
        self.ip = ip
        self.token = token
        self.port = port
        self.user = user if user is not None else getpass.getuser()
        self.service_name = service_name
        self.force = force

        home = os.path.expanduser(f"~{self.user}")
        if home.startswith("~"):
            raise SDCIServerException(
                f"Cannot resolve home directory for user '{self.user}'"
            )
        self._working_dir = os.path.join(home, ".sdci")

        if tasks_dir is None:
            self.tasks_dir = os.path.join(home, ".sdci", "tasks")
            self._tasks_dir_explicit = False
        else:
            self.tasks_dir = os.path.abspath(tasks_dir)
            self._tasks_dir_explicit = True

        # Injected confirmation callable — defaults to click.confirm.
        # Tests override this to avoid interactive stdin.
        self._confirm = lambda msg: click.confirm(msg)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def unit_path(self) -> str:
        return f"/etc/systemd/system/{self.service_name}.service"

    @property
    def env_path(self) -> str:
        return "/etc/sdci/sdci.env"

    @property
    def working_dir(self) -> str:
        return self._working_dir

    # ------------------------------------------------------------------
    # Pure rendering (no I/O)
    # ------------------------------------------------------------------

    def render_unit(self) -> str:
        binary = self.resolve_binary()
        return _UNIT_TEMPLATE.substitute(
            user=self.user,
            working_dir=self.working_dir,
            binary=binary,
            ip=self.ip,
            port=self.port,
            tasks_dir=self.tasks_dir,
        )

    def render_env(self) -> str:
        return _ENV_TEMPLATE.substitute(token=self.token)

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def check_platform(self) -> None:
        if sys.platform != "linux":
            raise SDCIServerException(
                f"systemd setup requires linux; detected platform: {sys.platform}"
            )
        if shutil.which("systemctl") is None:
            raise SDCIServerException(
                "systemctl not found on PATH; is systemd available on this host?"
            )

    def resolve_binary(self) -> str:
        path = shutil.which("sdci-server")
        if path is None:
            raise SDCIServerException(
                "sdci-server binary not found on PATH; "
                "ensure sdci is installed in the active environment"
            )
        return path

    def prepare_dirs(self) -> None:
        # Tool-managed working dir — always create
        os.makedirs(self.working_dir, exist_ok=True)

        # tasks_dir
        if self._tasks_dir_explicit:
            if not os.path.isdir(self.tasks_dir):
                raise SDCIServerException(
                    f"tasks_dir '{self.tasks_dir}' does not exist; "
                    "create it first or omit --tasks-dir to use the default"
                )
        else:
            os.makedirs(self.tasks_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Privileged helpers
    # ------------------------------------------------------------------

    def _run_privileged(self, args: list[str], input: str | None = None) -> None:
        result = subprocess.run(
            ["sudo", *args],
            input=input,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise SDCIServerException(
                f"Command 'sudo {shlex.join(args)}' failed: {result.stderr}"
            )

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def install(self) -> None:
        self.check_platform()
        self.resolve_binary()
        self.prepare_dirs()

        if os.path.exists(self.unit_path) and not self.force:
            confirmed = self._confirm(
                f"Unit file {self.unit_path} already exists. Overwrite?"
            )
            if not confirmed:
                raise SDCIServerException("aborted")

        # 1. Create /etc/sdci directory
        self._run_privileged(["install", "-d", "-m", "0755", "/etc/sdci"])

        # 2. Write env file (token via stdin, never on argv)
        self._run_privileged(["tee", self.env_path], input=self.render_env())
        self._run_privileged(["chmod", "600", self.env_path])

        # 3. Write unit file
        self._run_privileged(["tee", self.unit_path], input=self.render_unit())
        self._run_privileged(["chmod", "644", self.unit_path])

        # 4. Reload / enable / restart
        self._run_privileged(["systemctl", "daemon-reload"])
        self._run_privileged(["systemctl", "enable", self.service_name])
        self._run_privileged(["systemctl", "restart", self.service_name])

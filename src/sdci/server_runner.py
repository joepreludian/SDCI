import asyncio
import logging
import os
import time
from importlib.metadata import version

from sdci.exceptions import SDCIServerException
from sdci.settings import Settings

__version__ = version("sdci")
logger = logging.getLogger(__name__)


class AvailableCommandsDescriber:
    @staticmethod
    def get_available_commands():
        if not os.path.exists(Settings.TASKS_DIR):
            raise SDCIServerException(f"TASKS_DIR NOT FOUND: {Settings.TASKS_DIR}")

        available_tasks = [
            f[:-3] for f in os.listdir(Settings.TASKS_DIR) if f.endswith(".sh")
        ]
        logger.info(f"available_tasks={available_tasks}")

        return available_tasks


def format_bytes(num_bytes: float) -> str:
    """Render a byte count using binary units, e.g. 16.0 MiB."""
    value = float(num_bytes)

    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0

    return f"{value:.1f} TiB"


class UploadProgressReporter:
    """Accumulates transferred bytes and logs progress at a bounded frequency.

    The label is the client address rather than the destination file: while the
    body is still arriving, the multipart payload holding the filename has not
    been parsed yet.
    """

    INTERVAL_SECONDS = 2.0

    def __init__(
        self,
        label: str,
        total_bytes: int = None,
        interval_seconds: float = INTERVAL_SECONDS,
        clock=time.monotonic,
    ) -> None:
        self._label = label
        self._total_bytes = total_bytes
        self._interval_seconds = interval_seconds
        self._clock = clock
        self._started_at = clock()
        self._last_report_at = self._started_at
        self._bytes_received = 0

    @property
    def bytes_received(self) -> int:
        return self._bytes_received

    @property
    def elapsed_seconds(self) -> float:
        return self._clock() - self._started_at

    def advance(self, chunk_size: int) -> None:
        self._bytes_received += chunk_size

        now = self._clock()
        if now - self._last_report_at < self._interval_seconds:
            return

        self._last_report_at = now
        logger.info(self.summary())

    def summary(self) -> str:
        received = format_bytes(self._bytes_received)

        if self._total_bytes:
            percentage = int(self._bytes_received * 100 / self._total_bytes)
            received += f" / {format_bytes(self._total_bytes)} ({percentage}%)"

        return self._with_rate(f"UPLOAD PROGRESS - {self._label} - {received}")

    def finish(self) -> None:
        logger.info(
            self._with_rate(
                f"UPLOAD RECEIVED - {self._label} - "
                f"{format_bytes(self._bytes_received)} in {self.elapsed_seconds:.1f}s"
            )
        )

    def _with_rate(self, message: str) -> str:
        elapsed = self.elapsed_seconds

        if elapsed <= 0:
            return message

        return f"{message} - {format_bytes(self._bytes_received / elapsed)}/s"


class FileUploader:
    CHUNK_SIZE = 1024 * 1024  # 1 MiB

    def __init__(self, remote_dir: str, filename: str) -> None:
        self._remote_dir = remote_dir
        self._filename = filename
        self._lock = None

    def for_lock(self, lock: asyncio.Lock):
        self._lock = lock
        return self

    @property
    def resolved_path(self) -> str:
        if os.sep in self._filename or (os.altsep and os.altsep in self._filename):
            raise SDCIServerException(
                f"INVALID FILENAME (contains path separator): {self._filename}"
            )

        upload_dir = os.path.realpath(Settings.UPLOADS_DIR)
        candidate = os.path.realpath(
            os.path.join(upload_dir, self._remote_dir, self._filename)
        )

        if os.path.commonpath([upload_dir, candidate]) != upload_dir:
            raise SDCIServerException(
                f"INVALID DESTINATION PATH (escapes upload dir): {self._remote_dir}"
            )

        return candidate

    async def save(self, upload_file) -> int:
        destination = self.resolved_path

        os.makedirs(os.path.dirname(destination), exist_ok=True)

        if os.path.exists(destination):
            raise SDCIServerException(f"DESTINATION FILE ALREADY EXISTS: {destination}")

        bytes_written = 0
        try:
            with open(destination, "wb") as out_file:
                while True:
                    chunk = await upload_file.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    bytes_written += len(chunk)
        except BaseException:
            # A broken or cancelled (timed out) transfer must not leave a
            # half-written file behind; it would 409 on the next attempt.
            self._discard_partial_file(destination)
            raise

        logger.info(f"UPLOADED FILE: {destination} ({bytes_written} bytes)")
        return bytes_written

    @staticmethod
    def _discard_partial_file(destination: str) -> None:
        try:
            os.remove(destination)
            logger.warning(f"DISCARDED PARTIAL UPLOAD: {destination}")
        except OSError as exc:
            logger.error(f"COULD NOT DISCARD PARTIAL UPLOAD {destination}: {exc}")


class CommandRunner:
    def __init__(self, shell_file: str) -> None:
        self._task_name = shell_file
        self._shell_file = f"{Settings.TASKS_DIR}/{self._task_name}.sh"
        self._lock = None
        self._store = None

        if not os.path.exists(self._shell_file):
            logger.error(f"SHELL FILE NOT FOUND ON SERVER: {self._shell_file}")
            available_tasks = AvailableCommandsDescriber.get_available_commands()

            raise SDCIServerException(
                f'TASK "{shell_file}" not found. Available tasks: {available_tasks}'
            )

    def for_lock(self, lock: asyncio.Lock):
        self._lock = lock
        return self

    def for_store(self, store: dict):
        self._store = store
        return self

    async def run(self, args):
        if not self._lock:
            raise SDCIServerException("NO LOCK available")

        cmd = ["bash", self._shell_file]
        cmd.extend(args)

        logger.info(f"RUNNING TASK WITH CMD: {cmd}")

        await self._lock.acquire()
        logger.info("Triggering Task - Lock acquired")

        yield f"********** SDCI SERVER v{__version__} **********\n"
        yield f'RUNNING TASK: "{cmd}": TIMEOUT: {Settings.TASK_RUN_TIMEOUT_SECONDS}s\n'
        yield "********** task logs - start ********** \n\n"

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )

        # Update Process
        run_status = "RUNNING"
        self._store[self._task_name] = {
            "pid": process.pid,
            "exit_code": None,
            "status": run_status,
        }

        start_time = time.time()
        timeout = start_time + Settings.TASK_RUN_TIMEOUT_SECONDS
        while True:
            output = await process.stdout.readline()

            if output:
                yield output.decode()

            if process.returncode is not None:
                run_status = "FINISHED"
                break

            if time.time() > timeout:
                process.kill()
                run_status = "TIMEOUT"
                yield "TIMEOUT REACHED"
                break

        self._store[self._task_name] = {
            "pid": process.pid,
            "exit_code": process.returncode,
            "status": run_status,
        }

        self._lock.release()
        logger.info("TASK ENDED - Lock released")

        yield "\n********** task logs - end ********** \n"

        elapsed_time = time.time() - start_time
        yield f"EXITED ({process.returncode}) - Took {elapsed_time:.2f}s"

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

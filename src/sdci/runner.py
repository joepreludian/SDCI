import asyncio
import logging
import os
import time

from .exceptions import SDCIServerException

logger = logging.getLogger(__name__)


class CommandRunner:
    def __init__(self, shell_file: str) -> None:
        self._task_name = shell_file
        self._shell_file = f"./tasks/{self._task_name}.sh"
        self._lock = None
        self._store = None

        if not os.path.exists(self._shell_file):
            raise SDCIServerException(
                f"SHELL FILE NOT FOUND ON SERVER: {self._shell_file}"
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
        logger.info("LOCK ACQUIRED")

        yield "\n**********\n"
        yield f"RUNNING: {cmd}"

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        # Update Process
        run_status = "RUNNING"
        self._store[self._task_name] = {
            "pid": process.pid,
            "exit_code": None,
            "status": run_status,
        }

        timeout = time.time() + 12
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
        logger.info("LOCK RELEASED")

        yield f"\n**********\n\nEXITED ({process.returncode})"

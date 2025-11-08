import asyncio
import getpass
import logging
import logging.config
from contextlib import asynccontextmanager
from importlib.metadata import version

import click
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBearer

__version__ = version("sdci")

from starlette.responses import StreamingResponse

from sdci.exceptions import SDCIServerException
from sdci.schemas import TaskOutputSchema, TaskRequestSchema
from sdci.server_runner import AvailableCommandsDescriber, CommandRunner
from sdci.settings import Settings

logger = logging.getLogger(__name__)

# Global Variables
lock = asyncio.Lock()
task_info_store = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("*******************************")
    logger.info(f"SDCI - SERVER - v{__version__}")
    logger.info("*******************************")
    logger.info("Ready to rock! /o/\n")

    yield

    logger.info("SDCI - Shutting down system")


app = FastAPI(
    title="SDCI API",
    description="Sistema de Deploy Continuo Integrado - Integrated Continuous Deployment System",
    version=__version__,
    lifespan=lifespan,
)

oauth2_scheme = HTTPBearer()


async def verify_token(token: str = Depends(oauth2_scheme)):
    if token.credentials != Settings.SERVER_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


@app.post("/tasks/{task_name:str}/", dependencies=[Depends(verify_token)])
async def run_task(task_name: str, request: TaskRequestSchema):
    global task_info_store

    logger.info(f"SDCI - RUN COMMAND - {task_name}")

    try:
        command = CommandRunner(task_name).for_lock(lock).for_store(task_info_store)
    except SDCIServerException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    if lock.locked():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Command already running",
        )

    return StreamingResponse(command.run(request.args), media_type="text/plain")


@app.post("/tasks/{task_name:str}/status/", dependencies=[Depends(verify_token)])
async def get_task_status(task_name: str) -> TaskOutputSchema:
    global task_info_store

    try:
        CommandRunner(task_name).for_lock(lock).for_store(task_info_store)
    except SDCIServerException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    task_details = task_info_store.get(
        task_name, {"pid": None, "exit_code": None, "status": "STOPPED"}
    )

    return TaskOutputSchema.model_validate(task_details)


@click.command()
@click.option("--host", default="127.0.0.1", help="Host address to bind")
@click.option("--port", default=8842, type=int, help="Port to listen")
@click.option(
    "--server-token",
    help="Server token to secure SDCI. if not provided, SDCI_SERVER_TOKEN env var will be used",
)
@click.option("--tasks-dir", help="Directory with sh scripts to be executed as tasks")
def run_server(host: str, port: int, server_token: str, tasks_dir: str = "./tasks"):
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "[%(levelname)s] %(asctime)s | %(name)s: %(message)s"
                },
                "access": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                },
                "access": {
                    "formatter": "access",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "loggers": {
                "uvicorn.error": {
                    "level": "WARNING",
                    "handlers": ["default"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": "INFO",
                    "handlers": ["access"],
                    "propagate": False,
                },
            },
            "root": {"level": "INFO", "handlers": ["default"], "propagate": False},
        }
    )

    running_username = getpass.getuser()
    logger.info(
        f"Starting server with {host=}, {port=}, tasks_dir={tasks_dir if tasks_dir else Settings.TASKS_DIR}, user={running_username}"
    )

    # Settings Override
    if server_token:
        Settings.SERVER_TOKEN = server_token

    if tasks_dir:
        Settings.TASKS_DIR = tasks_dir

    try:
        if not Settings.SERVER_TOKEN:
            raise SDCIServerException(
                "SERVER TOKEN NOT FOUND; Provide either SDCI_SERVER_TOKEN env var or --server-token"
            )

        AvailableCommandsDescriber.get_available_commands()
    except SDCIServerException as exc:
        logger.error(f"SDCI - v{__version__} - {exc}")
        exit(1)

    uvicorn.run("sdci.server:app", host=host, port=port)

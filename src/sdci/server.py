import asyncio
import logging
from contextlib import asynccontextmanager
from importlib.metadata import version

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBearer

__version__ = version("sdci")

from starlette.responses import StreamingResponse

from sdci.exceptions import SDCIServerException
from sdci.schemas import TaskOutputSchema, TaskRequestSchema
from sdci.server_runner import CommandRunner
from sdci.settings import SERVER_TOKEN

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
    if token.credentials != SERVER_TOKEN:
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


def run_server():
    if not SERVER_TOKEN:
        print(
            f"SDCI - v{__version__} - SERVER TOKEN NOT FOUND - Please provide a token via SDCI_SERVER_TOKEN env var"
        )
        exit(1)

    uvicorn.run("sdci.server:app", host="0.0.0.0", port=8842, log_config="log_conf.yaml")

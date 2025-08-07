import asyncio
import logging
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import Literal, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel

__version__ = version("sdci")

from starlette.responses import StreamingResponse

from sdci.exceptions import SDCIServerException
from sdci.runner import CommandRunner

logger = logging.getLogger(__name__)

# Global Variables
lock = asyncio.Lock()
task_info_store = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"SDCI - Initializing System - Server Version v{__version__}")
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
    if token.credentials != "HAPPY123":
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


class TaskRequestSchema(BaseModel):
    args: list = []


class TaskOutputSchema(BaseModel):
    pid: Optional[int] = None
    exit_code: Optional[int] = None
    status: Literal["STOPPED", "RUNNING", "FINISHED", "TIMEOUT"] = "STOPPED"


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


if __name__ == "__main__":
    uvicorn.run(
        "server:app", host="0.0.0.0", port=8842, reload=True, log_config="log_conf.yaml"
    )

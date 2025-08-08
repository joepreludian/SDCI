from typing import Literal, Optional

from pydantic import BaseModel


class TaskRequestSchema(BaseModel):
    args: list = []


class TaskOutputSchema(BaseModel):
    pid: Optional[int] = None
    exit_code: Optional[int] = None
    status: Literal["STOPPED", "RUNNING", "FINISHED", "TIMEOUT"] = "STOPPED"

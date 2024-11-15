from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Game(BaseModel):
    start: datetime
    team: str
    opponent: str
    gym_code: str
    gym_name: Optional[str] = None
    gym_address: Optional[str] = None

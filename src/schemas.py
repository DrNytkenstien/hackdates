from pydantic import BaseModel
from typing import List, Optional

class TaskStep(BaseModel):
    step_id: int
    action: str
    power_draw_watts: float
    duration_seconds: float
    target_orient_angle: float = 0.0  # Added default value here!

class MissionPlan(BaseModel):
    tasks: List[TaskStep]

class GateResult(BaseModel):
    passed: bool
    gate_type: str
    message: str
    error_details: Optional[dict] = None
from enum import Enum
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class TaskStep(BaseModel):
    step_id: int
    action: str
    power_draw_watts: float
    duration_seconds: float
    target_orient_angle: float = 0.0

class MissionPlan(BaseModel):
    tasks: List[TaskStep]

class GateResult(BaseModel):
    passed: bool
    gate_type: str
    message: str
    error_details: Optional[dict] = None

class Severity(str, Enum):
    NOMINAL = "NOMINAL"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class AnomalyType(str, Enum):
    RW_SATURATION = "Reaction Wheel Saturation"
    ORBIT_DEVIATION = "Orbit Velocity Deviation"
    UNDERVOLTAGE = "Power Bus Undervoltage"
    THERMAL_EXCURSION = "Thermal Excursion"

class TelemetryFrame(BaseModel):
    latitude: float
    longitude: float
    altitude_km: float
    velocity_kms: float
    rw2_speed_rpm: float
    bus_voltage_v: float
    component_temp_c: float
    mission_phase: str = "NOMINAL ORBIT"

class MissionResponse(BaseModel):
    anomaly_detected: bool
    fault_type: Optional[str]
    severity: str
    success: bool
    attempts: int
    tasks: List[str]
    gate1_passed: bool
    gate1_message: str
    gate2_passed: bool
    gate2_message: str
    telemetry: Optional[List[Dict[str, Any]]]
    radiation_events: List[str]
    b_dot_triggered: bool
from typing import List
from z3 import Solver, sat
from .schemas import MissionPlan, GateResult

def verify_gate_1_z3(plan: MissionPlan, battery_capacity_wh: float = 40.0) -> GateResult:
    s = Solver()
    
    # Calculate energy in Watt-hours
    total_energy_wh = sum((t.power_draw_watts * (t.duration_seconds / 3600.0)) for t in plan.tasks)
    remaining_battery = battery_capacity_wh - total_energy_wh
    
    # Core mathematical constraint: 20% non-negotiable reserve
    s.add(remaining_battery >= (battery_capacity_wh * 0.20))
    
    if s.check() == sat:
        return GateResult(
            passed=True,
            gate_type="GATE_1_Z3",
            message="Mathematical constraints verified: Battery reserve safely maintained."
        )
    else:
        return GateResult(
            passed=False,
            gate_type="GATE_1_Z3",
            message=f"UNSAT: Total energy drawn ({total_energy_wh:.2f} Wh) violates the 20% reserve limit.",
            error_details={"total_energy_wh": total_energy_wh, "limit_wh": battery_capacity_wh * 0.8}
        )

def verify_gate_2_telemetry(telemetry_logs: List[dict], max_rpm: float = 6000.0, max_temp_c: float = 55.0) -> GateResult:
    for entry in telemetry_logs:
        if entry["wheel_rpm"] > max_rpm:
            return GateResult(
                passed=False,
                gate_type="GATE_2_TELEMETRY",
                message=f"Reaction wheel saturation detected at step {entry['step_id']}.",
                error_details={
                    "timestamp": entry["timestamp"],
                    "metric": "wheel_rpm",
                    "value": entry["wheel_rpm"],
                    "limit": max_rpm,
                    "step_id": entry["step_id"]
                }
            )
        if entry["temperature_c"] > max_temp_c:
            return GateResult(
                passed=False,
                gate_type="GATE_2_TELEMETRY",
                message=f"Thermal threshold exceeded at step {entry['step_id']}.",
                error_details={
                    "timestamp": entry["timestamp"],
                    "metric": "temperature_c",
                    "value": entry["temperature_c"],
                    "limit": max_temp_c,
                    "step_id": entry["step_id"]
                }
            )
            
    return GateResult(
        passed=True,
        gate_type="GATE_2_TELEMETRY",
        message="All telemetry bounds maintained safely during execution."
    )
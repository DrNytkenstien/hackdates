import asyncio
import json
import os
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="OrbitGuard-AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ORBIT_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "orbit_telemetry.json")

def load_telemetry_dataset() -> List[dict]:
    if os.path.exists(ORBIT_DATA_PATH):
        with open(ORBIT_DATA_PATH, "r") as f:
            return json.load(f)
    return []

def map_phase_to_fault(frame: dict) -> Optional[str]:
    phase = frame.get("mission_phase", "")
    if "EPS UNDERVOLTAGE" in phase or frame.get("bus_voltage_v", 28) < 24.0:
        return "Power Bus Undervoltage"
    elif "THERMAL OVERLIMIT" in phase or frame.get("component_temp_c", 30) > 65.0:
        return "Thermal Excursion"
    elif "RW2 STALL" in phase or "RW2 OVERSPEED" in phase or frame.get("rw2_speed_rpm", 2000) > 4200:
        return "Reaction Wheel Saturation"
    elif "VELOCITY OUT OF SAFE RANGE" in phase or frame.get("velocity_kms", 7.55) > 7.8 or frame.get("velocity_kms", 7.55) < 7.2:
        return "Orbit Velocity Deviation"
    return None

def build_candidates_for_fault(fault_type: str):
    if fault_type == "Reaction Wheel Saturation":
        candidates = [
            {
                "name": "Magnetorquer Momentum Desaturation",
                "short": "MTQ Desat",
                "color": "#38bdf8",
                "metrics": {"recoveryTime": 14.2, "resourceUse": 12, "risk": 15, "missionImpact": 8, "constraint": 94},
                "score": 92,
                "calculations": [
                    "τ_mag = M × B",
                    "H_wheel_new = H_wheel - ∫ τ_mag dt",
                    "Result: Wheel momentum safely reduced to 2200 RPM"
                ],
                "explanation": "Desaturates wheel momentum using Earth's magnetic field without consuming chemical propellant."
            },
            {
                "name": "RCS Thruster Pulse Dump",
                "short": "Thruster Dump",
                "color": "#f59e0b",
                "metrics": {"recoveryTime": 4.1, "resourceUse": 68, "risk": 42, "missionImpact": 35, "constraint": 72},
                "score": 74,
                "calculations": [
                    "τ_thruster = F × r",
                    "Δm = 0.14 kg thruster fuel expended",
                    "Result: Fast momentum dump executed in 4.1 seconds"
                ],
                "explanation": "Rapidly dumps angular momentum using cold-gas thrusters but depletes non-renewable fuel reserves."
            }
        ]
        return candidates, "Magnetorquer Momentum Desaturation"
    else:
        candidates = [
            {
                "name": "Closed-Loop Retro-Thrust Orbit Trim",
                "short": "Orbit Trim",
                "color": "#38bdf8",
                "metrics": {"recoveryTime": 8.0, "resourceUse": 25, "risk": 18, "missionImpact": 15, "constraint": 89},
                "score": 88,
                "calculations": [
                    "Δv_required = v_target - v_measured",
                    "Δv = -0.42 m/s correction pulse",
                    "Result: Velocity restored to nominal 7.55 km/s"
                ],
                "explanation": "Executes a precise retro-thrust burst to correct orbital velocity deviation."
            },
            {
                "name": "Passive Drag Area Alignment",
                "short": "Aero Drag",
                "color": "#f59e0b",
                "metrics": {"recoveryTime": 120.0, "resourceUse": 0, "risk": 40, "missionImpact": 30, "constraint": 65},
                "score": 62,
                "calculations": [
                    "F_drag = 0.5 × ρ × v² × C_d × A",
                    "Result: Trajectory decay over 3 orbital periods"
                ],
                "explanation": "Increases drag surface area to allow upper-atmosphere drag to decay velocity passively."
            }
        ]
        return candidates, "Closed-Loop Retro-Thrust Orbit Trim"

@app.websocket("/ws/orbitguard")
async def orbitguard_websocket(websocket: WebSocket):
    await websocket.accept()
    dataset = load_telemetry_dataset()
    
    if not dataset:
        await websocket.close(code=1000, reason="No dataset found")
        return

    step_index = 0
    try:
        while True:
            raw_frame = dataset[step_index % len(dataset)]
            step_index += 1
            
            telemetry = {
                "latitude": raw_frame.get("latitude", 0.0),
                "longitude": raw_frame.get("longitude", 0.0),
                "altitude": raw_frame.get("altitude_km", 540.0),
                "velocity": raw_frame.get("velocity_kms", 7.55),
                "wheelRPM": raw_frame.get("rw2_speed_rpm", 2100.0),
            }
            
            fault_type = map_phase_to_fault(raw_frame)
            
            if fault_type:
                candidates, selected = build_candidates_for_fault(fault_type)
                payload = {
                    "fault": fault_type,
                    "telemetry": telemetry,
                    "candidates": candidates,
                    "selectedCandidate": selected,
                    "eventId": f"{fault_type}-{step_index}"
                }
                await websocket.send_json(payload)
                # Pause on active anomaly for 30 seconds so operator has full control
                await asyncio.sleep(30)
            else:
                payload = {
                    "fault": None,
                    "telemetry": telemetry,
                    "candidates": [],
                    "selectedCandidate": "",
                    "eventId": f"nominal-{step_index}"
                }
                await websocket.send_json(payload)
                # Stream calm nominal coordinates every 3 seconds
                await asyncio.sleep(3)

    except WebSocketDisconnect:
        pass
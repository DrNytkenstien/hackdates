import asyncio
import json
import math
import os
from typing import Any, Dict, List, Optional
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
        try:
            with open(ORBIT_DATA_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return generate_fallback_telemetry()

def generate_fallback_telemetry(num_frames: int = 100) -> List[dict]:
    dataset = []
    for i in range(num_frames):
        theta = (i / num_frames) * 2 * math.pi
        frame = {
            "latitude": 18.45 + math.sin(theta) * 4.8,
            "longitude": 73.9 + math.cos(theta) * 8.6,
            "altitude_km": 540.0 + math.sin(theta * 2) * 4.7,
            "velocity_kms": 7.55 + math.cos(theta * 1.7) * 0.018,
            "rw2_speed_rpm": 2100.0 + math.sin(theta * 1.8) * 65,
            "bus_voltage_v": 28.0,
            "component_temp_c": 30.0,
            "mission_phase": "NOMINAL CRUISE"
        }
        if i == 20:
            frame["rw2_speed_rpm"] = 4850.0
            frame["mission_phase"] = "RW2 OVERSPEED"
        elif i == 45:
            frame["velocity_kms"] = 7.12
            frame["mission_phase"] = "VELOCITY OUT OF SAFE RANGE"
        elif i == 70:
            frame["bus_voltage_v"] = 22.4
            frame["mission_phase"] = "EPS UNDERVOLTAGE"
        elif i == 85:
            frame["component_temp_c"] = 68.5
            frame["mission_phase"] = "THERMAL OVERLIMIT"
        dataset.append(frame)
    return dataset

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

    elif fault_type == "Orbit Velocity Deviation":
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

    elif fault_type == "Power Bus Undervoltage":
        candidates = [
            {
                "name": "Payload Load Shedding & Battery Re-conditioning",
                "short": "Load Shed",
                "color": "#38bdf8",
                "metrics": {"recoveryTime": 18.5, "resourceUse": 5, "risk": 12, "missionImpact": 20, "constraint": 91},
                "score": 90,
                "calculations": [
                    "P_saved = P_total - P_essential",
                    "V_bus_new = V_bus + (I_charge × R_internal)",
                    "Result: Bus voltage stabilized at nominal 28.2V"
                ],
                "explanation": "Temporarily isolates non-critical science payloads to restore primary bus voltage."
            },
            {
                "name": "Solar Array Orient Thrust Slew",
                "short": "Array Slew",
                "color": "#f59e0b",
                "metrics": {"recoveryTime": 9.2, "resourceUse": 45, "risk": 35, "missionImpact": 25, "constraint": 78},
                "score": 76,
                "calculations": [
                    "θ_sun = arctan(S_vector)",
                    "P_gen = P_max × cos(θ_sun)",
                    "Result: Solar power generation boosted by 310W"
                ],
                "explanation": "Re-orients primary solar array vector toward peak solar intensity."
            }
        ]
        return candidates, "Payload Load Shedding & Battery Re-conditioning"

    else:  # Thermal Excursion
        candidates = [
            {
                "name": "Radiator Panel Attitude Re-orientation",
                "short": "Radiator Slew",
                "color": "#38bdf8",
                "metrics": {"recoveryTime": 22.0, "resourceUse": 10, "risk": 14, "missionImpact": 12, "constraint": 93},
                "score": 91,
                "calculations": [
                    "Q_emitted = ε × σ × A × (T^4 - T_space^4)",
                    "ΔT_rate = -1.4°C/min",
                    "Result: Component temperature cooled to 42.0°C"
                ],
                "explanation": "Slews radiator panels to point toward deep space cold-sink."
            },
            {
                "name": "Duty Cycle Power Throttle",
                "short": "Power Throttle",
                "color": "#f59e0b",
                "metrics": {"recoveryTime": 15.0, "resourceUse": 15, "risk": 22, "missionImpact": 38, "constraint": 80},
                "score": 78,
                "calculations": [
                    "P_thermal = I²R × DutyCycle",
                    "Result: Heat generation reduced by 45%"
                ],
                "explanation": "Throttles high-power processing units to mitigate internal thermal generation."
            }
        ]
        return candidates, "Radiator Panel Attitude Re-orientation"

@app.get("/")
def read_root():
    return {"status": "online", "system": "OrbitGuard-AI Backend"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.websocket("/ws/orbitguard")
async def orbitguard_websocket(websocket: WebSocket):
    await websocket.accept()
    dataset = load_telemetry_dataset()

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
                await asyncio.sleep(3)

    except WebSocketDisconnect:
        pass
import json
import os
from typing import Optional, Dict, Any
from groq import Groq
from dotenv import load_dotenv
from .schemas import MissionPlan, TelemetryFrame, AnomalyType, Severity

load_dotenv()

class AutonomousAnomalyDetector:
    """Monitors raw telemetry frames against orbit safety constraints."""

    RW_MAX_SAFE_RPM = 4200.0
    VOLTAGE_MIN_SAFE_V = 24.0
    TEMP_MAX_SAFE_C = 65.0
    VELOCITY_MIN_KMS = 7.20
    VELOCITY_MAX_KMS = 7.80

    def analyze_frame(self, frame: TelemetryFrame) -> Optional[Dict[str, Any]]:
        if frame.rw2_speed_rpm > self.RW_MAX_SAFE_RPM:
            return {
                "type": AnomalyType.RW_SATURATION.value,
                "severity": Severity.HIGH.value,
                "metric": "rw2_speed_rpm",
                "value": frame.rw2_speed_rpm,
                "threshold": self.RW_MAX_SAFE_RPM
            }
        elif frame.bus_voltage_v < self.VOLTAGE_MIN_SAFE_V:
            return {
                "type": AnomalyType.UNDERVOLTAGE.value,
                "severity": Severity.CRITICAL.value,
                "metric": "bus_voltage_v",
                "value": frame.bus_voltage_v,
                "threshold": self.VOLTAGE_MIN_SAFE_V
            }
        elif frame.component_temp_c > self.TEMP_MAX_SAFE_C:
            return {
                "type": AnomalyType.THERMAL_EXCURSION.value,
                "severity": Severity.MEDIUM.value,
                "metric": "component_temp_c",
                "value": frame.component_temp_c,
                "threshold": self.TEMP_MAX_SAFE_C
            }
        elif not (self.VELOCITY_MIN_KMS <= frame.velocity_kms <= self.VELOCITY_MAX_KMS):
            return {
                "type": AnomalyType.ORBIT_DEVIATION.value,
                "severity": Severity.HIGH.value,
                "metric": "velocity_kms",
                "value": frame.velocity_kms,
                "threshold": self.VELOCITY_MAX_KMS
            }
        return None

def generate_mission_plan(anomaly: Dict[str, Any], error_context: Optional[dict] = None) -> MissionPlan:
    client = Groq()
    
    prompt = (
        f"AUTONOMOUS SYSTEM ALERT: Anomaly Detected.\n"
        f"Fault Type: {anomaly['type']}\n"
        f"Severity: {anomaly['severity']}\n"
        f"Violating Metric: {anomaly['metric']} currently at {anomaly['value']} (Threshold: {anomaly['threshold']})\n\n"
        "Your objective is to generate a recovery task sequence to resolve this anomaly."
    )
    
    if error_context:
        prompt += (
            "\nCRITICAL SAFETY GATE FAILURE IN PREVIOUS RECOVERY ATTEMPT:\n"
            f"{json.dumps(error_context, indent=2)}\n\n"
            "RE-PLANNING RULES TO FIX THIS FAILURE:\n"
            "1. REACTION WHEEL SATURATION (wheel_rpm > 6000):\n"
            "   - If a step failed due to RPM limits, insert 'MAGNETORQUER_MOMENTUM_DUMP' BEFORE the failed step.\n"
            "   - Reduce thruster burn duration_seconds if requested > 15s.\n"
            "2. BATTERY / ENERGY BREACH (Gate 1 UNSAT):\n"
            "   - Reduce task duration_seconds or power_draw_watts to preserve 20% battery reserve.\n"
        )
    else:
        prompt += (
            "\nRECOVERY ACTION GUIDELINES:\n"
            "- If Reaction Wheel Saturation: Prioritize 'MAGNETORQUER_MOMENTUM_DUMP' task.\n"
            "- If Orbit Velocity Deviation: Prioritize short 'THRUSTER_BURN' task.\n"
            "- If Power Bus Undervoltage: Prioritize 'SHED_PAYLOAD_LOAD' and 'ORIENT_SOLAR_PANELS' tasks.\n"
            "- If Thermal Excursion: Prioritize 'REORIENT_THERMAL_RADIATOR' task.\n\n"
            "SYSTEM OPERATIONAL BOUNDS:\n"
            "- Battery: 40 Wh nominal (Maintain >= 20% / 8 Wh reserve at all times)\n"
            "- Reaction Wheels: Max 6000 RPM hard limit during tasks.\n"
            "  * Thruster burns add ~315 RPM/sec.\n"
            "  * Magnetorquer dumps reduce wheel speed back to 1000 RPM baseline.\n"
        )

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system", 
                "content": "You are an autonomous satellite flight control AI. You solve onboard anomalies. You output JSON matching the MissionPlan schema strictly. "
                           "Example: {\"tasks\": [{\"step_id\": 1, \"action\": \"MAGNETORQUER_MOMENTUM_DUMP\", "
                           "\"power_draw_watts\": 15.0, \"duration_seconds\": 180.0, \"target_orient_angle\": 0.0}]}"
            },
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    
    plan_dict = json.loads(response.choices[0].message.content)
    return MissionPlan(**plan_dict)
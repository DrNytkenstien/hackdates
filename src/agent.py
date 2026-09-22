import json
import os
from typing import Optional
from groq import Groq
from dotenv import load_dotenv
from .schemas import MissionPlan

load_dotenv()

def generate_mission_plan(directive: str, error_context: Optional[dict] = None) -> MissionPlan:
    client = Groq()
    
    prompt = f"Ground Directive: '{directive}'\n"
    
    if error_context:
        prompt += (
            "\nCRITICAL SAFETY GATE FAILURE IN PREVIOUS ATTEMPT:\n"
            f"{json.dumps(error_context, indent=2)}\n\n"
            "RE-PLANNING RULES TO FIX THIS FAILURE:\n"
            "1. REACTION WHEEL SATURATION (wheel_rpm > 6000):\n"
            "   - Look at 'step_id' in error_details to see WHICH step failed.\n"
            "   - IF A STEP AFTER A THRUSTER BURN FAILS (e.g. step 4 Payload Sweep): You MUST insert a SECOND "
            "'MAGNETORQUER_MOMENTUM_DUMP' task IMMEDIATELY BEFORE that failed step to clear residual thruster momentum!\n"
            "   - NO SINGLE THRUSTER BURN CAN EXCEED 12-15 SECONDS. Reduce burn duration_seconds if requested > 15s.\n"
            "   - Remember: ALL tasks (even 60s payload sweeps) accumulate +25 RPM/sec attitude holding momentum.\n"
            "2. BATTERY / ENERGY BREACH (Gate 1 UNSAT):\n"
            "   - Reduce task duration_seconds or power_draw_watts to preserve 20% battery reserve (max allowable draw = 32 Wh).\n"
        )
    else:
        prompt += (
            "\nSYSTEM OPERATIONAL BOUNDS & PHYSICS LAWS:\n"
            "- Battery: 40 Wh nominal (Maintain >= 20% / 8 Wh reserve at all times)\n"
            "- Reaction Wheels: Max 6000 RPM.\n"
            "  * Thruster burns add ~315 RPM/sec (Max safe burn = 12-15s).\n"
            "  * Antenna/Payload tasks add ~25 RPM/sec.\n"
            "  * Magnetorquer dumps REDUCE wheel speed back to 1000 RPM floor.\n"
            "IMPORTANT: If a mission has multiple heavy tasks (e.g. Thruster + Payload Sweep), insert 'MAGNETORQUER_MOMENTUM_DUMP' "
            "BEFORE the thruster AND BEFORE long payload tasks to prevent cumulative momentum saturation."
        )

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system", 
                "content": "You are a satellite flight control AI. You output JSON matching the MissionPlan schema strictly. "
                           "Example: {\"tasks\": [{\"step_id\": 1, \"action\": \"ORIENT_ANTENNA\", "
                           "\"power_draw_watts\": 50.0, \"duration_seconds\": 10.0, \"target_orient_angle\": 45.0}]}"
            },
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    
    plan_dict = json.loads(response.choices[0].message.content)
    return MissionPlan(**plan_dict)
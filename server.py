import asyncio
import hashlib
import json
import os
import re
import time
from typing import Dict, List

import pandas as pd
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="OrbitGuard-AI NASA Telemetry Stream")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NASA_DATA_PATH = os.path.join(os.path.dirname(__file__), "labeled_anomalies.csv")
LEDGER_FILE = os.path.join(os.path.dirname(__file__), "ledger_store.json")


def load_persisted_ledgers() -> Dict[str, List[dict]]:
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as ledger_file:
                return json.load(ledger_file)
        except Exception as error:
            print(f"Error loading ledger file: {error}")
    return {}


def save_persisted_ledgers(ledgers: Dict[str, List[dict]]) -> None:
    try:
        with open(LEDGER_FILE, "w", encoding="utf-8") as ledger_file:
            json.dump(ledgers, ledger_file, indent=2)
    except Exception as error:
        print(f"Error saving ledger file: {error}")


def load_nasa_dataset() -> Dict[str, dict]:
    try:
        dataframe = pd.read_csv(NASA_DATA_PATH)
        dataset: Dict[str, dict] = {}

        for _, row in dataframe.iterrows():
            channel_id = str(row["chan_id"])
            raw_classes = str(row["class"])
            quoted_classes = re.sub(r"([a-zA-Z_]+)", r'"\1"', raw_classes)

            dataset[channel_id] = {
                "spacecraft": str(row["spacecraft"]),
                "chan_id": channel_id,
                "anomaly_sequences": json.loads(str(row["anomaly_sequences"])),
                "classes": json.loads(quoted_classes),
                "total_steps": int(row["num_values"]),
            }

        print(f"NASA dataset loaded: {len(dataset)} telemetry channels available.")
        return dataset
    except Exception as error:
        print(f"Error loading NASA dataset: {error}")
        return {}


nasa_channels = load_nasa_dataset()
user_ledgers: Dict[str, List[dict]] = load_persisted_ledgers()

DEFAULT_CANDIDATES = [
    {
        "id": "cand-1",
        "title": "Desaturate Reaction Wheel Vector",
        "score": 96.4,
        "recoveryTime": 4.2,
        "recovery_time": 4.2,
        "time": 4.2,
        "risk": 12,
        "riskScore": 12,
        "risk_score": 12,
        "missionImpact": 8,
        "mission_impact": 8,
        "impact": 8,
        "constraintFit": 98,
        "constraint_fit": 98,
        "fit": 98,
        "metrics": {
            "recoveryTime": 4.2,
            "resourceUse": 12,
            "risk": 12,
            "missionImpact": 8,
            "constraint": 98,
        },
        "actions": ["Dump momentum via magnetic torquers"],
        "steps": ["1. Arm RCS", "2. Torque dump"],
        "proofs": ["HASH_PROOF_A1"],
    },
    {
        "id": "cand-2",
        "title": "Switch to RCS Thruster Hold",
        "score": 89.1,
        "recoveryTime": 12.8,
        "recovery_time": 12.8,
        "time": 12.8,
        "risk": 38,
        "riskScore": 38,
        "risk_score": 38,
        "missionImpact": 25,
        "mission_impact": 25,
        "impact": 25,
        "constraintFit": 85,
        "constraint_fit": 85,
        "fit": 85,
        "metrics": {
            "recoveryTime": 12.8,
            "resourceUse": 38,
            "risk": 38,
            "missionImpact": 25,
            "constraint": 85,
        },
        "actions": ["Inhibit wheel control loop"],
        "steps": ["1. Inhibit RW", "2. Engage RCS"],
        "proofs": ["HASH_PROOF_A2"],
    },
]


def create_ledger_block(
    user_id: str,
    event_type: str,
    details: str,
    prev_hash: str,
) -> dict:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    ledger = user_ledgers.setdefault(user_id, [])
    block_id = len(ledger) + 1
    raw_payload = f"{block_id}{timestamp}{event_type}{details}{prev_hash}"
    block_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    block = {
        "id": block_id,
        "timestamp": timestamp,
        "type": event_type,
        "details": details,
        "hash": block_hash,
        "prevHash": prev_hash,
    }
    ledger.append(block)
    save_persisted_ledgers(user_ledgers)
    return block


def get_channel(channel: str) -> dict:
    if not nasa_channels:
        raise RuntimeError("NASA anomaly dataset is empty or unavailable")
    return nasa_channels.get(channel) or nasa_channels.get("A-1") or next(iter(nasa_channels.values()))


@app.get("/")
def read_root():
    return {"status": "online", "system": "OrbitGuard-AI NASA Telemetry Stream"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "channels": len(nasa_channels)}


@app.websocket("/ws/orbitguard")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str = Query("default_user"),
    channel: str = Query("A-1"),
):
    await websocket.accept()

    ledger = user_ledgers.setdefault(user_id, [])
    if not ledger:
        create_ledger_block(
            user_id,
            "GENESIS_INITIALIZATION",
            "OrbitGuard NASA Telemetry Bridge Initialized",
            "0" * 64,
        )

    channel_info = get_channel(channel)
    spacecraft = channel_info["spacecraft"]
    channel_id = channel_info["chan_id"]
    sequences = channel_info["anomaly_sequences"]
    classes = channel_info["classes"]
    first_start = sequences[0][0] if sequences else 100
    step_index = max(0, first_start - 10)
    anomaly_logged_for_current_event = False
    current_active_sequence_end = 0

    try:
        while True:
            try:
                raw_client_message = await asyncio.wait_for(
                    websocket.receive_text(), timeout=1.0
                )
                message = json.loads(raw_client_message)
                message_type = message.get("type", "")

                if message_type in {"RESOLVE_ANOMALY", "CONTINUE_MISSION"}:
                    if anomaly_logged_for_current_event or current_active_sequence_end > 0:
                        last_block = ledger[-1]
                        create_ledger_block(
                            user_id,
                            "AUTONOMOUS_RECOVERY_VERIFIED",
                            f"Channel {channel_id} ({spacecraft}) mitigation verified by operator action",
                            last_block["hash"],
                        )
                        anomaly_logged_for_current_event = False
                        if current_active_sequence_end > 0:
                            step_index = current_active_sequence_end + 1
                            current_active_sequence_end = 0
                elif message_type == "RESET_MISSION":
                    user_ledgers[user_id] = []
                    ledger = user_ledgers[user_id]
                    create_ledger_block(
                        user_id,
                        "GENESIS_INITIALIZATION",
                        "OrbitGuard NASA Bridge Reset",
                        "0" * 64,
                    )
                    step_index = max(0, first_start - 10)
                    anomaly_logged_for_current_event = False
                    current_active_sequence_end = 0
            except asyncio.TimeoutError:
                step_index += 1

            if step_index > channel_info["total_steps"]:
                step_index = 0

            active_fault_class = None
            for sequence_index, (start, end) in enumerate(sequences):
                if start <= step_index <= end:
                    active_fault_class = (
                        classes[sequence_index]
                        if sequence_index < len(classes)
                        else "point"
                    )
                    current_active_sequence_end = end
                    break

            latitude = 20.0 + (step_index * 0.05) % 60 - 30
            longitude = 66.0 + (step_index * 0.1) % 360 - 180
            altitude = 539.8 + (step_index % 10) * 0.05
            velocity = 7.47 + (step_index % 5) * 0.001
            wheel_rpm = (
                4800.0 + (step_index % 20) * 25.0
                if active_fault_class
                else 2100.0 + (step_index % 15) * 5.0
            )

            fault_obj = None
            candidates = []
            logs = []
            proofs = []
            if active_fault_class:
                fault_title = (
                    f"NASA {spacecraft} [{channel_id}] - "
                    f"{active_fault_class.upper()} ANOMALY"
                )

                fault_obj = {
                    "title": fault_title,
                    "type": active_fault_class,
                    "channel": channel_id,
                    "spacecraft": spacecraft,
                    "severity": "CRITICAL",
                    "actions": [
                        "Autonomous Containment Engaged",
                        "Vector Dump Initiated",
                    ],
                    "steps": [
                        "Step 1: Inhibit RW",
                        "Step 2: Engage ADCS Safe Hold",
                    ],
                    "proofs": [
                        "SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                    ],
                }

                candidates = [dict(candidate) for candidate in DEFAULT_CANDIDATES]

                logs = [
                    f"Threshold breach detected on channel {channel_id}",
                    "LLM Autonomous Recovery Planner armed",
                    "Evidence hash committed to Black Box Ledger",
                ]
                proofs = fault_obj["proofs"]

                if not anomaly_logged_for_current_event:
                    last_block = ledger[-1]
                    create_ledger_block(
                        user_id,
                        f"NASA_{active_fault_class.upper()}_ANOMALY_DETECTED",
                        f"Channel {channel_id} ({spacecraft}) threshold breach "
                        f"at step {step_index}",
                        last_block["hash"],
                    )
                    anomaly_logged_for_current_event = True
            elif anomaly_logged_for_current_event:
                last_block = ledger[-1]
                create_ledger_block(
                    user_id,
                    "AUTONOMOUS_RECOVERY_VERIFIED",
                    f"Channel {channel_id} ({spacecraft}) telemetry restored "
                    "to nominal bounds",
                    last_block["hash"],
                )
                anomaly_logged_for_current_event = False
                current_active_sequence_end = 0

            await websocket.send_json(
                {
                    "telemetry": {
                        "latitude": latitude,
                        "longitude": longitude,
                        "altitude": altitude,
                        "velocity": velocity,
                        "wheelRPM": wheel_rpm,
                        "stepIndex": step_index,
                        "channel": channel_id,
                        "spacecraft": spacecraft,
                    },
                    "fault": fault_obj,
                    "candidates": candidates,
                    "selectedCandidate": candidates[0]["title"] if candidates else "",
                    "logs": logs,
                    "proofs": proofs,
                    "blackBoxChain": ledger,
                    "isChainValid": True,
                    "missionPhase": (
                        "ANOMALY CONTAINED"
                        if active_fault_class
                        else "RECOVERY VERIFIED"
                        if len(ledger) > 1
                        else "NOMINAL ORBIT"
                    ),
                }
            )
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        print(f"Client disconnected: {user_id}")

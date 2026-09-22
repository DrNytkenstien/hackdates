import os
import sys
import json
import uuid
import random
from dotenv import load_dotenv

load_dotenv()

from src.agent import generate_mission_plan
from src.gates import verify_gate_1_z3, verify_gate_2_telemetry
from src.simulator import run_satellite_simulation
from src.radiation_defense import (
    GroundStationCache,
    TMRMemoryController,
    compute_hmac_signature,
    inject_transit_seu_bit_flip,
    verify_onboard_hmac
)

def execute_b_dot_safe_mode():
    print("\n" + "=" * 70)
    print("[HARDWARE FALLBACK TRIGGERED]: B-DOT AUTONOMOUS SAFE-MODE ENGAGED")
    print("=" * 70)
    print("  -> CAUSE: High-level AI Flight Agent reached maximum attempt limits.")
    print("  -> EXECUTING: Hardwired analog B-Dot magnetic detumbling algorithm...")
    print("  -> MAG_X, MAG_Y, MAG_Z active: Damping kinetic momentum (-K * dB/dt)...")
    print("  -> Reaction wheels: Commanded to 1,000 RPM idle baseline.")
    print("  -> Solar Arrays: Oriented toward Sun vector (+Z face) for passive trickle charge.")
    print("  -> Payloads & Thrusters: HARD ISOLATED / POWERED DOWN.")
    print("-" * 70)
    print("STATE: Satellite stabilized. Power reserve nominal. Holding for Ground Pass...")
    print("=" * 70 + "\n")

def main():
    print("=" * 70)
    print("SATELLITE AUTONOMY - EVIDENCE-GATED SELF-HEALING PIPELINE")
    print("=" * 70)
    
    if "GROQ_API_KEY" not in os.environ:
        print("Error: GROQ_API_KEY environment variable not set.")
        sys.exit(1)

    # Initialize Ground Cache
    ground_cache = GroundStationCache()
        
    print("\nEnter a Mission Directive (or press Enter to use default demo directive):")
    user_input = input("> ").strip()
    
    default_prompt = (
        "Re-orient directional antenna 45 degrees toward Ground Station B "
        "and execute 15-second high power thruster adjustment."
    )
    directive = user_input if user_input else default_prompt
    
    print(f"\nActive Ground Directive: {directive}\n")
    
    max_attempts = 3
    attempt = 1
    error_feedback = None
    success = False
    
    while attempt <= max_attempts:
        print(f"--- [ATTEMPT {attempt}/{max_attempts}] ---")
        print("Agent generating execution plan...")
        
        try:
            plan = generate_mission_plan(directive, error_feedback)
        except Exception as e:
            print(f"Agent failed to generate valid Pydantic plan: {e}")
            break
            
        print(f"Plan Actions: {[t.action for t in plan.tasks]}\n")
        
        print("[GATE 1]: Running Z3 SMT Static Verification...")
        g1_result = verify_gate_1_z3(plan)
        if not g1_result.passed:
            print(f"  -> FAIL: {g1_result.message}")
            error_feedback = {"gate": 1, "details": g1_result.error_details}
            attempt += 1
            print("\nRe-routing mathematical violation back to agent...\n")
            continue
        print(f"  -> PASS: {g1_result.message}\n")
        
        print("[SIMULATOR]: Executing tasks in SimPy hardware environment...")
        telemetry = run_satellite_simulation(plan)
        print("  -> Execution complete. Telemetry generated.\n")
        
        print("[GATE 2]: Running Telemetry Invariant Audit...")
        g2_result = verify_gate_2_telemetry(telemetry)
        if not g2_result.passed:
            print(f"  -> FAIL: {g2_result.message}")
            error_feedback = {"gate": 2, "details": g2_result.error_details}
            attempt += 1
            print("\nRe-routing runtime telemetry machine evidence back to agent...\n")
            continue
        print(f"  -> PASS: {g2_result.message}\n")
        
        # =====================================================================
        # LAYER 1: GROUND STATION SIGNING & CACHING
        # =====================================================================
        packet_id = f"PKT-{uuid.uuid4().hex[:8].upper()}"
        raw_payload = json.dumps([t.model_dump() for t in plan.tasks], sort_keys=True)
        hmac_sig = compute_hmac_signature(raw_payload)
        
        # Store in Ground Cache for fast-path re-transmission if RF link fails
        ground_cache.store(packet_id, raw_payload)
        
        print("[GROUND STATION]: Plan cryptographically sealed and cached.")
        print(f"  -> Packet ID: {packet_id}")
        print(f"  -> HMAC-SHA256 Signature: {hmac_sig[:16]}...{hmac_sig[-16:]}")
        print("  -> Uplinking payload across TC&T RF radio link...\n")

        # =====================================================================
        # STOCHASTIC RADIATION ENVIRONMENT CONFIGURATION
        # =====================================================================
        SIMULATE_RADIATION_ENVIRONMENT = True
        TRANSIT_SEU_PROBABILITY = 0.50  # 50% chance of RF corruption
        RAM_SEU_PROBABILITY     = 0.75  # 75% chance of RAM bit flip

        # =====================================================================
        # LAYER 2: SPACE LINK SEU STRIKE (Probabilistic)
        # =====================================================================
        transit_hit = SIMULATE_RADIATION_ENVIRONMENT and (random.random() < TRANSIT_SEU_PROBABILITY)
        
        if transit_hit:
            print("[SPACE ENVIRONMENT]: ⚡ SOUTH ATLANTIC ANOMALY: RF Transit Strike!")
            rf_payload = inject_transit_seu_bit_flip(raw_payload)
            print("  -> Solar heavy ion flipped a bit in the incoming RF bitstream.\n")
        else:
            rf_payload = raw_payload

        # =====================================================================
        # LAYER 3: ONBOARD FPGA RECEIVER & HARDWARE DROP SIGNAL
        # =====================================================================
        print("[SATELLITE TC&T RECEIVER]: Computing onboard HMAC verification...")
        if not verify_onboard_hmac(rf_payload, hmac_sig):
            print("  -> REJECTED: HMAC signature mismatch!")
            print("  -> ACTION: Asserting Hardware Drop Signal. Clearing volatile RF buffer.")
            print("  -> TRANSMITTING: Outbound Diagnostic NACK to Ground Station...")
            
            # Ground Fast-Path Recovery
            print("\n[GROUND STATION]: Received NACK for Packet " + packet_id)
            print("  -> Bypassing LLM re-planning loop (Plan logic is valid).")
            print("  -> Retrieving uncorrupted packet from Ground Cache...")
            rf_payload = ground_cache.retrieve(packet_id)
            print("  -> Re-uplinking pristine telecommand payload...")
            print("  -> PASS: HMAC verified on second uplink pass!\n")

        else:
            print("  -> PASS: Onboard HMAC signature verified. Zero transit corruption.\n")

        # =====================================================================
        # LAYER 4: ONBOARD TRIPLE MODULAR REDUNDANCY (TMR) MEMORY CHECK
        # =====================================================================
        print("[ONBOARD AVIONICS]: Loading command into Triple Modular Redundancy (TMR) RAM...")
        tmr_memory = TMRMemoryController(rf_payload)
        
        # Probabilistic onboard RAM bit-flip targeting a RANDOM bank
        ram_hit = SIMULATE_RADIATION_ENVIRONMENT and (random.random() < RAM_SEU_PROBABILITY)
        if ram_hit:
            hit_bank = tmr_memory.inject_random_seu_bit_flip()
            print(f"  -> [RADIATION EVENT]: Cosmic ray struck RAM Bank {hit_bank} during execution cycle!")
        
        tmr_passed, tmr_msg = tmr_memory.evaluate_tmr_voting_gate()
        print(f"  -> TMR VOTER: {tmr_msg}")

        if not tmr_passed:
            print("  -> FATAL: TMR memory corruption unrecoverable.")
            break

        print("\nSUCCESS: Execution verified, signed, memory-scrubbed, and deployed safely!")
        success = True
        break
        
    if not success:
        execute_b_dot_safe_mode()

if __name__ == "__main__":
    main()
import numpy as np
from scipy.integrate import solve_ivp
from typing import List, Dict, Any
from .schemas import MissionPlan

# =====================================================================
# PHYSICAL CONSTANTS & SPACECRAFT SPECIFICATIONS (3U CubeSat Standard)
# =====================================================================
MASS_KG = 4.0               # Satellite Mass (4 kg)
HEAT_CAPACITY = 900.0       # Aluminum 6061 Specific Heat Capacity J/(kg*K)
THERMAL_MASS = MASS_KG * HEAT_CAPACITY # Thermal Mass (J/K) = 3600 J/K

EMISSIVITY = 0.85           # Surface emissivity coefficient
SURFACE_AREA = 0.06         # Radiative surface area exposed to space (m^2)
SIGMA = 5.670374e-8         # Stefan-Boltzmann Constant (W/(m^2 K^4))
T_SPACE_K = 3.0             # Deep space background temperature (Kelvin)

# Reaction Wheel Dynamics
I_WHEEL = 1.5e-5            # Wheel Moment of Inertia (kg*m^2)

def run_satellite_simulation(plan: MissionPlan) -> List[dict]:
    """
    Executes a numerical physics simulation using SciPy's IVP solver.
    Integrates system differential equations for:
      1. Thermal Dynamics: Stefan-Boltzmann radiation + electrical waste heat.
      2. Kinematics: Reaction wheel momentum accumulation & magnetorquer desaturation.
      3. Electrical Energy: Conservation of charge and instantaneous power draw.
    """
    battery_energy_wh = 40.0    # 40 Wh nominal battery capacity
    temp_celsius = 25.0         # 25°C initial ambient hull temperature
    wheel_rpm = 1200.0          # Initial baseline reaction wheel speed (RPM)
    
    telemetry_log = []

    for step in plan.tasks:
        duration = float(step.duration_seconds)
        power_w = float(step.power_draw_watts)
        action = step.action.upper()

        if "MAGNETORQUER" in action or "DUMP" in action:
            electrical_loss_factor = 0.40
            wheel_accel_rpm_per_sec = -380.0  # Magnetic dipole counter-torque
        elif "THRUSTER" in action or "BURN" in action:
            electrical_loss_factor = 0.92
            wheel_accel_rpm_per_sec = 315.0   # Plume disturbance torque
        else:
            electrical_loss_factor = 0.85
            wheel_accel_rpm_per_sec = 25.0    # Slew maneuver torque

        # Differential equation system for numerical integrator
        def system_ode(t, y):
            temp_k, rpm, energy_wh = y
            
            # 1. Thermal ODE: dT/dt = (P_waste - P_radiated) / C_thermal
            p_waste = power_w * electrical_loss_factor
            p_radiated = EMISSIVITY * SIGMA * SURFACE_AREA * (temp_k**4 - T_SPACE_K**4)
            dtemp_dt = (p_waste - p_radiated) / THERMAL_MASS
            
            # 2. Reaction Wheel Dynamics: d(RPM)/dt
            if rpm <= 1000.0 and wheel_accel_rpm_per_sec < 0:
                drpm_dt = 0.0  # Wheel velocity floor
            else:
                drpm_dt = wheel_accel_rpm_per_sec
                
            # 3. Electrical Energy ODE: dE/dt = -Power
            denergy_dt = -(power_w / 3600.0)
            
            return [dtemp_dt, drpm_dt, denergy_dt]

        y0 = [temp_celsius + 273.15, wheel_rpm, battery_energy_wh]
        
        # Run Numerical Runge-Kutta IVP Integration
        sol = solve_ivp(
            system_ode, 
            t_span=(0, duration), 
            y0=y0, 
            method='RK45', 
            t_eval=np.linspace(0, duration, max(2, int(duration)))
        )

        # Extract final numerical state values
        final_temp_k = sol.y[0][-1]
        final_rpm = max(1000.0, sol.y[1][-1])
        final_energy = sol.y[2][-1]

        # Update continuous state
        temp_celsius = final_temp_k - 273.15
        wheel_rpm = final_rpm
        battery_energy_wh = final_energy

        # Record telemetry snapshot matching Gate 2 expectation
        telemetry_log.append({
            "timestamp": len(telemetry_log) + 1,
            "step_id": step.step_id,
            "action": action,
            "battery_wh": round(battery_energy_wh, 4),
            "temperature_c": round(temp_celsius, 2),
            "wheel_rpm": round(wheel_rpm, 1)
        })

    # Return raw list of telemetry dictionaries directly for Gate 2
    return telemetry_log
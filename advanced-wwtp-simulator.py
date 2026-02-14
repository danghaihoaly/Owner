#!/usr/bin/env python3
"""
Advanced Multi-Reactor Wastewater Treatment Plant Simulator
with Real-Time Parameter Adjustment

Features:
- Multiple reactor configurations (anoxic-aerobic, A2O, oxidation ditch)
- Interactive parameter adjustment
- Real-time simulation control
- Comprehensive performance analysis
- Export capabilities
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import odeint
from dataclasses import dataclass, asdict
import json
import sys
import os
from datetime import datetime
import threading
import time

@dataclass
class ASM3Parameters:
    """ASM3 kinetic and stoichiometric parameters"""
    mu_H: float = 2.0
    q_fe: float = 3.0
    b_H: float = 0.2
    K_O2: float = 0.2
    K_NO3: float = 0.5
    K_S: float = 2.0
    K_STO: float = 1.0
    K_ALK: float = 0.1
    K_NH4_H: float = 0.01
    mu_A: float = 1.0
    b_A: float = 0.15
    K_NH4_A: float = 1.0
    K_O2_A: float = 0.5
    K_ALK_A: float = 0.5
    Y_H: float = 0.63
    Y_STO: float = 0.85
    Y_A: float = 0.24
    f_XI: float = 0.1
    i_NBM: float = 0.07
    i_NXI: float = 0.02
    k_h: float = 3.0
    K_X: float = 1.0
    eta_NO3: float = 0.6


@dataclass
class ReactorZone:
    """Individual reactor zone configuration"""
    name: str
    volume: float  # m³
    do_setpoint: float  # mg/L
    zone_type: str  # 'anoxic', 'aerobic', 'anaerobic'


class MultiReactorWWTP:
    """Multi-reactor wastewater treatment plant"""
    
    def __init__(self, params: ASM3Parameters):
        self.p = params
        self.zones = []
        self.flow_rate = 100.0  # m³/h
        self.recycle_streams = {}  # {name: (from_zone, to_zone, ratio)}
        self.waste_flow = 0.0
        self.influent = None
        self.state_history = []
        self.time_history = []
        
    def add_zone(self, zone: ReactorZone):
        """Add a reactor zone"""
        self.zones.append(zone)
        print(f"✓ Added zone: {zone.name} ({zone.volume} m³, {zone.zone_type})")
        
    def add_recycle_stream(self, name: str, from_zone_idx: int, to_zone_idx: int, ratio: float):
        """Add recycle stream (ratio relative to influent flow)"""
        self.recycle_streams[name] = (from_zone_idx, to_zone_idx, ratio)
        print(f"✓ Added recycle: {name} from Zone {from_zone_idx} to Zone {to_zone_idx} (Q × {ratio})")
        
    def set_influent(self, influent_dict):
        """Set influent composition"""
        self.influent = np.array([
            influent_dict.get('S_S', 400),
            influent_dict.get('X_S', 100),
            influent_dict.get('X_I', 50),
            influent_dict.get('S_I', 30),
            0.0,  # X_STO
            0.0,  # X_H
            0.0,  # X_A
            influent_dict.get('S_NH', 40),
            influent_dict.get('S_NO', 0),
            influent_dict.get('S_ALK', 5),
            0.0   # S_O2
        ])
        
    def monod(self, S, K):
        return S / (K + S)
    
    def switch_O2(self, S_O, K_O):
        return S_O / (K_O + S_O)
    
    def switch_NO3(self, S_O, S_NO, K_O, K_NO):
        return (K_O / (K_O + S_O)) * (S_NO / (K_NO + S_NO))
    
    def process_rates(self, state, do_setpoint):
        """Calculate ASM3 process rates for a zone"""
        S_S, X_S, X_I, S_I, X_STO, X_H, X_A, S_NH, S_NO, S_ALK, S_O2 = state
        p = self.p
        
        f_STO = X_STO / (X_H + 1e-10)
        f_X = X_S / (X_H + 1e-10)
        
        r = {}
        
        # Storage (aerobic and anoxic)
        r['r1_ae'] = (p.q_fe * self.monod(S_S, p.K_S) * self.monod(S_ALK, p.K_ALK) *
                      self.switch_O2(S_O2, p.K_O2) * X_H)
        r['r1_an'] = (p.eta_NO3 * p.q_fe * self.monod(S_S, p.K_S) * self.monod(S_ALK, p.K_ALK) *
                      self.switch_NO3(S_O2, S_NO, p.K_O2, p.K_NO3) * X_H)
        
        # Growth
        r['r2_ae'] = (p.mu_H * self.monod(f_STO, p.K_STO) * self.monod(S_NH, p.K_NH4_H) *
                      self.monod(S_ALK, p.K_ALK) * self.switch_O2(S_O2, p.K_O2) * X_H)
        r['r2_an'] = (p.eta_NO3 * p.mu_H * self.monod(f_STO, p.K_STO) * self.monod(S_NH, p.K_NH4_H) *
                      self.monod(S_ALK, p.K_ALK) * self.switch_NO3(S_O2, S_NO, p.K_O2, p.K_NO3) * X_H)
        
        # Endogenous respiration
        r['r3_ae'] = p.b_H * self.monod(S_ALK, p.K_ALK) * self.switch_O2(S_O2, p.K_O2) * X_H
        r['r3_an'] = p.eta_NO3 * p.b_H * self.monod(S_ALK, p.K_ALK) * self.switch_NO3(S_O2, S_NO, p.K_O2, p.K_NO3) * X_H
        
        # Nitrification
        r['r4'] = p.mu_A * self.monod(S_NH, p.K_NH4_A) * self.monod(S_ALK, p.K_ALK_A) * self.switch_O2(S_O2, p.K_O2_A) * X_A
        r['r5'] = p.b_A * self.monod(S_ALK, p.K_ALK_A) * self.switch_O2(S_O2, p.K_O2_A) * X_A
        
        # Hydrolysis
        r['r6_ae'] = p.k_h * self.monod(f_X, p.K_X) * self.monod(S_ALK, p.K_ALK) * self.switch_O2(S_O2, p.K_O2) * X_H
        r['r6_an'] = p.eta_NO3 * p.k_h * self.monod(f_X, p.K_X) * self.monod(S_ALK, p.K_ALK) * self.switch_NO3(S_O2, S_NO, p.K_O2, p.K_NO3) * X_H
        
        return r
    
    def derivatives(self, state, rates):
        """Calculate state derivatives"""
        p = self.p
        r = rates
        
        dS = np.zeros(11)
        
        dS[0] = -(1/p.Y_STO) * (r['r1_ae'] + r['r1_an']) + r['r6_ae'] + r['r6_an']
        dS[1] = -(r['r6_ae'] + r['r6_an']) + (1 - p.f_XI) * (r['r3_ae'] + r['r3_an'] + r['r5'])
        dS[2] = p.f_XI * (r['r3_ae'] + r['r3_an'] + r['r5'])
        dS[3] = 0
        dS[4] = r['r1_ae'] + r['r1_an'] - (1/p.Y_H) * (r['r2_ae'] + r['r2_an'])
        dS[5] = r['r2_ae'] + r['r2_an'] - r['r3_ae'] - r['r3_an']
        dS[6] = r['r4'] - r['r5']
        dS[7] = (-p.i_NBM * (r['r2_ae'] + r['r2_an']) - (p.i_NBM + 1/p.Y_A) * r['r4'] +
                 (p.i_NBM - p.f_XI * p.i_NXI) * (r['r3_ae'] + r['r3_an'] + r['r5']))
        dS[8] = ((1 - 1/p.Y_A) * r['r4'] - ((1 - p.Y_H) / (2.86 * p.Y_H)) * (r['r1_an'] + r['r2_an']) -
                 (1 / 2.86) * r['r3_an'])
        dS[9] = (-(p.i_NBM / 14) * (r['r2_ae'] + r['r2_an']) - (p.i_NBM / 14 + 1 / (7 * p.Y_A)) * r['r4'] +
                 (p.i_NBM / 14) * (r['r3_ae'] + r['r3_an'] + r['r5']) +
                 (1 / (14 * 2.86)) * (r['r1_an'] + r['r2_an'] + r['r3_an']))
        dS[10] = 0
        
        return dS
    
    def simulate_step(self, states, dt):
        """Simulate one time step for all zones"""
        Q = self.flow_rate / 24  # m³/day
        new_states = []
        
        for i, zone in enumerate(self.zones):
            state = states[i]
            V = zone.volume
            
            # Calculate biological rates
            rates = self.process_rates(state, zone.do_setpoint)
            dS_bio = self.derivatives(state, rates)
            
            # Calculate inflows
            inflow_total = 0
            inflow_conc = np.zeros(11)
            
            # Influent to first zone
            if i == 0:
                inflow_total += Q
                inflow_conc += Q * self.influent
            
            # Previous zone
            if i > 0:
                inflow_total += Q
                inflow_conc += Q * states[i-1]
            
            # Recycle streams
            for name, (from_idx, to_idx, ratio) in self.recycle_streams.items():
                if to_idx == i:
                    Q_recycle = Q * ratio
                    inflow_total += Q_recycle
                    inflow_conc += Q_recycle * states[from_idx]
            
            # Calculate outflow
            outflow = inflow_total
            
            # Hydraulic derivative
            if inflow_total > 0:
                dS_hydraulic = (inflow_conc / inflow_total - state) * outflow / V
            else:
                dS_hydraulic = np.zeros(11)
            
            # Total derivative
            dS_total = dS_bio + dS_hydraulic
            
            # Keep DO at setpoint
            dS_total[10] = 0
            
            # Update state
            new_state = state + dS_total * dt
            new_state = np.maximum(new_state, 0)  # Non-negative
            new_state[10] = zone.do_setpoint
            
            new_states.append(new_state)
        
        return new_states
    
    def simulate(self, initial_states, t_span, dt=0.01, callback=None):
        """Run full simulation"""
        t = np.arange(t_span[0], t_span[1], dt)
        n_steps = len(t)
        
        states = initial_states.copy()
        self.state_history = [states]
        self.time_history = [t[0]]
        
        print(f"\n🔄 Running simulation: {t_span[0]} to {t_span[1]} days")
        print(f"   Time step: {dt} days ({dt*24:.2f} hours)")
        print(f"   Total steps: {n_steps}")
        
        for step in range(1, n_steps):
            states = self.simulate_step(states, dt)
            self.state_history.append(states)
            self.time_history.append(t[step])
            
            if callback and step % 100 == 0:
                callback(step, n_steps, t[step], states)
        
        print("✓ Simulation complete!")
        return np.array(self.time_history), self.state_history
    
    def get_performance_metrics(self, states):
        """Calculate performance metrics for final zone (effluent)"""
        effluent = states[-1]
        S_S, X_S, X_I, S_I, X_STO, X_H, X_A, S_NH, S_NO, S_ALK, S_O2 = effluent
        
        # Apply settling (98% removal of particulates)
        settling_eff = 0.98
        X_H_eff = X_H * (1 - settling_eff)
        X_A_eff = X_A * (1 - settling_eff)
        X_I_eff = X_I * (1 - settling_eff)
        X_S_eff = X_S * (1 - settling_eff)
        X_STO_eff = X_STO * (1 - settling_eff)
        
        total_COD = S_S + X_S_eff + X_I_eff + S_I + X_STO_eff + X_H_eff + X_A_eff
        soluble_COD = S_S + S_I
        total_N = S_NH + S_NO + self.p.i_NBM * (X_H_eff + X_A_eff) + self.p.i_NXI * X_I_eff
        TSS = 0.75 * (X_H_eff + X_A_eff + X_I_eff + X_S_eff)
        
        # Calculate removals
        influent_COD = self.influent[0] + self.influent[1] + self.influent[2] + self.influent[3]
        influent_N = self.influent[7]
        
        COD_removal = (1 - total_COD / influent_COD) * 100
        N_removal = (1 - total_N / influent_N) * 100
        
        return {
            'Total COD': total_COD,
            'Soluble COD': soluble_COD,
            'NH4-N': S_NH,
            'NO3-N': S_NO,
            'Total N': total_N,
            'TSS': TSS,
            'COD Removal (%)': COD_removal,
            'N Removal (%)': N_removal,
            'MLSS': 0.75 * (X_H + X_A + X_I + X_S)
        }


class InteractiveSimulator:
    """Interactive simulation controller"""
    
    def __init__(self):
        self.plant = None
        self.params = ASM3Parameters()
        self.running = False
        
    def display_menu(self):
        """Display main menu"""
        os.system('clear' if os.name != 'nt' else 'cls')
        print("=" * 80)
        print(" " * 20 + "🏭 ADVANCED WWTP SIMULATOR 🏭")
        print("=" * 80)
        print("\n📋 MAIN MENU:\n")
        print("  1. Configure Plant (Add Zones & Recycles)")
        print("  2. Set Influent Characteristics")
        print("  3. Adjust Kinetic Parameters")
        print("  4. Run Simulation")
        print("  5. View Results")
        print("  6. Export Data")
        print("  7. Load Preset Configuration")
        print("  8. Exit")
        print("\n" + "=" * 80)
        
    def configure_plant_interactive(self):
        """Interactive plant configuration"""
        print("\n🏗️  PLANT CONFIGURATION")
        print("=" * 60)
        
        self.plant = MultiReactorWWTP(self.params)
        
        # Get flow rate
        flow = float(input("\nInfluent Flow Rate (m³/h) [100]: ") or "100")
        self.plant.flow_rate = flow
        
        # Add zones
        print("\n📦 ADD REACTOR ZONES:")
        n_zones = int(input("Number of zones [3]: ") or "3")
        
        for i in range(n_zones):
            print(f"\n--- Zone {i+1} ---")
            name = input(f"  Name [Zone-{i+1}]: ") or f"Zone-{i+1}"
            volume = float(input(f"  Volume (m³) [500]: ") or "500")
            zone_type = input(f"  Type (anoxic/aerobic/anaerobic) [aerobic]: ") or "aerobic"
            
            if zone_type.lower() == 'anoxic':
                do = 0.2
            elif zone_type.lower() == 'anaerobic':
                do = 0.0
            else:
                do = 2.0
            
            do = float(input(f"  DO setpoint (mg/L) [{do}]: ") or str(do))
            
            zone = ReactorZone(name, volume, do, zone_type)
            self.plant.add_zone(zone)
        
        # Add recycles
        print("\n🔄 ADD RECYCLE STREAMS:")
        add_recycle = input("Add recycle streams? (y/n) [y]: ") or "y"
        
        if add_recycle.lower() == 'y':
            n_recycles = int(input("Number of recycle streams [1]: ") or "1")
            
            for i in range(n_recycles):
                print(f"\n--- Recycle {i+1} ---")
                name = input(f"  Name [RAS]: ") or "RAS"
                from_idx = int(input(f"  From zone (0-{len(self.plant.zones)-1}): "))
                to_idx = int(input(f"  To zone (0-{len(self.plant.zones)-1}): "))
                ratio = float(input(f"  Ratio (× influent flow) [1.0]: ") or "1.0")
                
                self.plant.add_recycle_stream(name, from_idx, to_idx, ratio)
        
        input("\n✓ Configuration complete! Press Enter to continue...")
        
    def set_influent_interactive(self):
        """Interactive influent setup"""
        print("\n💧 INFLUENT CHARACTERISTICS")
        print("=" * 60)
        
        print("\nEnter concentrations (press Enter for defaults):")
        
        influent = {
            'S_S': float(input("  Readily biodegradable COD (g/m³) [400]: ") or "400"),
            'X_S': float(input("  Slowly biodegradable COD (g/m³) [100]: ") or "100"),
            'X_I': float(input("  Inert particulate COD (g/m³) [50]: ") or "50"),
            'S_I': float(input("  Inert soluble COD (g/m³) [30]: ") or "30"),
            'S_NH': float(input("  Ammonia-N (g/m³) [40]: ") or "40"),
            'S_NO': float(input("  Nitrate-N (g/m³) [0]: ") or "0"),
            'S_ALK': float(input("  Alkalinity (mol/m³) [5]: ") or "5")
        }
        
        self.plant.set_influent(influent)
        
        total_COD = influent['S_S'] + influent['X_S'] + influent['X_I'] + influent['S_I']
        print(f"\n✓ Total influent COD: {total_COD:.1f} g/m³")
        print(f"✓ Total influent N: {influent['S_NH']:.1f} g/m³")
        
        input("\nPress Enter to continue...")
        
    def adjust_parameters_interactive(self):
        """Interactive parameter adjustment"""
        print("\n⚙️  KINETIC PARAMETERS")
        print("=" * 60)
        
        print("\nCurrent parameters:")
        for key, value in asdict(self.params).items():
            print(f"  {key}: {value}")
        
        modify = input("\nModify parameters? (y/n) [n]: ") or "n"
        
        if modify.lower() == 'y':
            print("\nEnter new values (press Enter to keep current):")
            for key in asdict(self.params).keys():
                current = getattr(self.params, key)
                new_val = input(f"  {key} [{current}]: ")
                if new_val:
                    setattr(self.params, key, float(new_val))
            
            self.plant.p = self.params
            print("\n✓ Parameters updated!")
        
        input("\nPress Enter to continue...")
        
    def run_simulation_interactive(self):
        """Interactive simulation run"""
        if self.plant is None:
            print("\n❌ No plant configured! Please configure plant first.")
            input("Press Enter to continue...")
            return
        
        if self.plant.influent is None:
            print("\n❌ No influent set! Please set influent characteristics first.")
            input("Press Enter to continue...")
            return
        
        print("\n▶️  RUN SIMULATION")
        print("=" * 60)
        
        duration = float(input("\nSimulation duration (days) [30]: ") or "30")
        dt = float(input("Time step (days) [0.01]: ") or "0.01")
        
        # Initialize states
        print("\nInitializing reactor states...")
        initial_states = []
        for zone in self.plant.zones:
            state = np.array([2, 80, 1000, 30, 30, 2000, 100, 1, 8, 3.5, zone.do_setpoint])
            initial_states.append(state)
        
        # Progress callback
        def progress_callback(step, total, t, states):
            percent = (step / total) * 100
            print(f"\r  Progress: {percent:.1f}% | Time: {t:.2f} days", end='', flush=True)
        
        # Run simulation
        t, states = self.plant.simulate(initial_states, (0, duration), dt, progress_callback)
        
        print("\n\n✓ Simulation complete!")
        
        # Display final performance
        final_performance = self.plant.get_performance_metrics(states[-1])
        
        print("\n📊 FINAL EFFLUENT QUALITY:")
        print("-" * 60)
        for key, value in final_performance.items():
            if '%' in key:
                print(f"  {key:<25} {value:>10.2f}")
            else:
                print(f"  {key:<25} {value:>10.2f} {'g/m³' if 'TSS' in key or 'COD' in key or 'N' in key or 'MLSS' in key else ''}")
        
        input("\nPress Enter to continue...")
        
    def view_results(self):
        """View and plot results"""
        if not self.plant.state_history:
            print("\n❌ No simulation results available!")
            input("Press Enter to continue...")
            return
        
        print("\n📈 GENERATING PLOTS...")
        
        t = np.array(self.plant.time_history)
        
        # Extract data for each zone
        fig, axes = plt.subplots(len(self.plant.zones), 2, figsize=(16, 4*len(self.plant.zones)))
        if len(self.plant.zones) == 1:
            axes = axes.reshape(1, -1)
        
        fig.suptitle('Multi-Reactor WWTP Simulation Results', fontsize=16, fontweight='bold')
        
        for i, zone in enumerate(self.plant.zones):
            zone_states = np.array([states[i] for states in self.plant.state_history])
            
            # Plot 1: Substrates and Biomass
            ax1 = axes[i, 0]
            ax1.plot(t, zone_states[:, 0], label='$S_S$', linewidth=2)
            ax1.plot(t, zone_states[:, 4], label='$X_{STO}$', linewidth=2)
            ax1.plot(t, zone_states[:, 5], label='$X_H$', linewidth=2)
            ax1.plot(t, zone_states[:, 6], label='$X_A$', linewidth=2)
            ax1.set_xlabel('Time (days)')
            ax1.set_ylabel('Concentration (g COD/m³)')
            ax1.set_title(f'{zone.name} - Substrates & Biomass')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Plot 2: Nitrogen
            ax2 = axes[i, 1]
            ax2.plot(t, zone_states[:, 7], label='$S_{NH}$ (NH4-N)', linewidth=2, color='green')
            ax2.plot(t, zone_states[:, 8], label='$S_{NO}$ (NO3-N)', linewidth=2, color='purple')
            ax2.set_xlabel('Time (days)')
            ax2.set_ylabel('Concentration (g N/m³)')
            ax2.set_title(f'{zone.name} - Nitrogen Species')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"wwtp_results_{timestamp}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"\n✓ Plot saved as: {filename}")
        
        plt.show()
        
        input("\nPress Enter to continue...")
        
    def export_data(self):
        """Export simulation data"""
        if not self.plant.state_history:
            print("\n❌ No simulation results available!")
            input("Press Enter to continue...")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Export to CSV
        import csv
        csv_file = f"wwtp_data_{timestamp}.csv"
        
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            header = ['Time (days)']
            for i, zone in enumerate(self.plant.zones):
                for var in ['S_S', 'X_S', 'X_I', 'S_I', 'X_STO', 'X_H', 'X_A', 'S_NH', 'S_NO', 'S_ALK', 'S_O2']:
                    header.append(f'{zone.name}_{var}')
            writer.writerow(header)
            
            # Data
            for j, t in enumerate(self.plant.time_history):
                row = [t]
                for i in range(len(self.plant.zones)):
                    row.extend(self.plant.state_history[j][i])
                writer.writerow(row)
        
        print(f"\n✓ Data exported to: {csv_file}")
        
        # Export configuration
        config = {
            'timestamp': timestamp,
            'flow_rate': self.plant.flow_rate,
            'zones': [
                {
                    'name': z.name,
                    'volume': z.volume,
                    'do_setpoint': z.do_setpoint,
                    'zone_type': z.zone_type
                } for z in self.plant.zones
            ],
            'recycles': self.plant.recycle_streams,
            'influent': self.plant.influent.tolist(),
            'parameters': asdict(self.params)
        }
        
        json_file = f"wwtp_config_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✓ Configuration exported to: {json_file}")
        
        input("\nPress Enter to continue...")
        
    def load_preset(self):
        """Load preset configuration"""
        print("\n📁 PRESET CONFIGURATIONS")
        print("=" * 60)
        print("\n1. Conventional Activated Sludge (1 Aerobic Zone)")
        print("2. Modified Ludzack-Ettinger (Anoxic + Aerobic + MLR)")
        print("3. A2O Process (Anaerobic + Anoxic + Aerobic)")
        print("4. Oxidation Ditch (3 Aerobic Zones)")
        print("5. Four-Stage Bardenpho (Full BNR)")
        
        choice = input("\nSelect preset [2]: ") or "2"
        
        self.plant = MultiReactorWWTP(self.params)
        self.plant.flow_rate = 100.0
        
        if choice == '1':
            # Conventional AS
            self.plant.add_zone(ReactorZone("Aeration", 1000, 2.0, "aerobic"))
            
        elif choice == '2':
            # MLE
            self.plant.add_zone(ReactorZone("Anoxic", 400, 0.2, "anoxic"))
            self.plant.add_zone(ReactorZone("Aerobic", 1000, 2.0, "aerobic"))
            self.plant.add_recycle_stream("MLR", 1, 0, 3.0)
            
        elif choice == '3':
            # A2O
            self.plant.add_zone(ReactorZone("Anaerobic", 200, 0.0, "anaerobic"))
            self.plant.add_zone(ReactorZone("Anoxic", 400, 0.2, "anoxic"))
            self.plant.add_zone(ReactorZone("Aerobic", 1000, 2.0, "aerobic"))
            self.plant.add_recycle_stream("MLR", 2, 1, 3.0)
            self.plant.add_recycle_stream("RAS", 2, 0, 1.0)
            
        elif choice == '4':
            # Oxidation Ditch
            self.plant.add_zone(ReactorZone("OD-Zone1", 500, 2.0, "aerobic"))
            self.plant.add_zone(ReactorZone("OD-Zone2", 500, 1.5, "aerobic"))
            self.plant.add_zone(ReactorZone("OD-Zone3", 500, 2.0, "aerobic"))
            
        elif choice == '5':
            # Bardenpho
            self.plant.add_zone(ReactorZone("Anoxic-1", 400, 0.2, "anoxic"))
            self.plant.add_zone(ReactorZone("Aerobic-1", 800, 2.0, "aerobic"))
            self.plant.add_zone(ReactorZone("Anoxic-2", 200, 0.2, "anoxic"))
            self.plant.add_zone(ReactorZone("Aerobic-2", 200, 2.0, "aerobic"))
            self.plant.add_recycle_stream("MLR", 1, 0, 3.0)
        
        # Set default influent
        self.plant.set_influent({
            'S_S': 400, 'X_S': 100, 'X_I': 50, 'S_I': 30,
            'S_NH': 40, 'S_NO': 0, 'S_ALK': 5
        })
        
        print(f"\n✓ Loaded preset configuration!")
        input("Press Enter to continue...")
        
    def run(self):
        """Main program loop"""
        while True:
            self.display_menu()
            choice = input("\nSelect option: ")
            
            if choice == '1':
                self.configure_plant_interactive()
            elif choice == '2':
                if self.plant is None:
                    print("\n❌ Configure plant first!")
                    input("Press Enter...")
                else:
                    self.set_influent_interactive()
            elif choice == '3':
                self.adjust_parameters_interactive()
            elif choice == '4':
                self.run_simulation_interactive()
            elif choice == '5':
                self.view_results()
            elif choice == '6':
                self.export_data()
            elif choice == '7':
                self.load_preset()
            elif choice == '8':
                print("\n👋 Thanks for using WWTP Simulator!")
                sys.exit(0)
            else:
                print("\n❌ Invalid choice!")
                input("Press Enter...")


def main():
    """Main entry point"""
    print("\n" + "=" * 80)
    print(" " * 15 + "ADVANCED WASTEWATER TREATMENT PLANT SIMULATOR")
    print(" " * 25 + "with Real-Time Control")
    print("=" * 80)
    print("\nVersion 2.0 | Ubuntu 24.04 Compatible")
    print("Developed for Professional WWTP Analysis\n")
    
    simulator = InteractiveSimulator()
    
    try:
        simulator.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Simulation interrupted by user")
        sys.exit(0)


if __name__ == '__main__':
    main()
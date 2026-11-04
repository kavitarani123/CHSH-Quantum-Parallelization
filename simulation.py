"""
Quantum CHSH Inequality Simulation & Hardware Parallelization Framework
Author: Kavita Rani (Wright State University)
Target Environment: Local Simulator / IBM Quantum QPU Hardware
"""

import os
import numpy as np
from typing import Optional, Dict, List
import matplotlib.pyplot as plt

# Qiskit Core Engineering Elements
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.visualization import plot_histogram
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

# Aer Simulation & Live Infrastructure Services
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler

# =====================================================================
# SECTION 1: CORE CIRCUIT CONSTRUCTIONS
# =====================================================================

def build_bell_state_circuit(qreg_name: Optional[str] = 'q', creg_name: Optional[str] = 'c') -> QuantumCircuit:
    """
    Constructs a foundational 2-qubit Bell pair maximally entangled state.
    Generates the state: |Psi+> = (|00> + |11>) / sqrt(2)
    """
    qreg = QuantumRegister(2, qreg_name)
    creg = ClassicalRegister(2, creg_name)
    circuit = QuantumCircuit(qreg, creg)
    
    circuit.h(qreg[0])
    circuit.cx(qreg[0], qreg[1])
    circuit.barrier()
    
    return circuit

def configure_measurement_basis(circuit: QuantumCircuit, basis_view: str) -> QuantumCircuit:
    """
    Applies the exact structural coordinate rotations required to establish
    the non-orthogonal measurement directions for CHSH inequality verification.
    """
    basis_view = basis_view.strip()
    
    if basis_view == "AB":
        circuit.ry(-np.pi / 4, 1)
        circuit.measure([0, 1], [0, 1])
    elif basis_view == "Ab":
        circuit.ry(np.pi / 4, 1)
        circuit.measure([0, 1], [0, 1])
    elif basis_view == "aB":
        circuit.ry(-np.pi / 4, 1)
        circuit.h(0)  # Maps observer A into the X-basis
        circuit.measure([0, 1], [0, 1])
    elif basis_view == "ab":
        circuit.ry(np.pi / 4, 1)
        circuit.h(0)  # Maps observer A into the X-basis
        circuit.measure([0, 1], [0, 1])
    else:
        raise ValueError(f"Unknown CHSH basis coordinate key: {basis_view}")
        
    return circuit

def generate_parallelized_qpu_circuit(total_backend_qubits: int, view_modes: List[str]) -> QuantumCircuit:
    """
    Parallelizes multiple independent 2-qubit CHSH sub-circuits across 
    the hardware topology. Targets ~80% system utilization to maximize throughput
    while avoiding cross-talk and isolating bad physical connections.
    """
    allocated_qubit_limit = 8 * (int(0.8 * total_backend_qubits) // 8)
    parallel_execution_circuit = QuantumCircuit()
    
    for base_offset in range(0, allocated_qubit_limit, 8):
        for idx, view_key in enumerate(view_modes):
            register_id = f"{view_key}_block{base_offset // 8}"
            
            # Instantiate decoupled sub-registers
            sub_circuit = build_bell_state_circuit(f"q_{register_id}", f"c_{register_id}")
            configured_sub_circuit = configure_measurement_basis(sub_circuit, view_key)
            
            parallel_execution_circuit.add_register(configured_sub_circuit.qregs[0])
            parallel_execution_circuit.add_register(configured_sub_circuit.cregs[0])
            
            # Map registers onto global contiguous hardware index slots
            qubit_indices = [base_offset + 2 * idx, base_offset + 2 * idx + 1]
            clbit_indices = [base_offset + 2 * idx, base_offset + 2 * idx + 1]
            
            parallel_execution_circuit.compose(
                configured_sub_circuit,
                qubits=qubit_indices,
                clbits=clbit_indices,
                inplace=True
            )
            
    return parallel_execution_circuit

# =====================================================================
# SECTION 2: METRIC & ALGEBRAIC EVALUATION
# =====================================================================

def evaluate_expectation_value(counts: Dict[str, int]) -> float:
    """
    Computes the correlation metric <E> = P(00) + P(11) - P(01) - P(10)
    from the output bitstring distribution dictionary.
    """
    total_shots = sum(counts.values())
    if total_shots == 0:
        return 0.0
        
    p_00 = counts.get('00', 0) / total_shots
    p_11 = counts.get('11', 0) / total_shots
    p_01 = counts.get('01', 0) / total_shots
    p_10 = counts.get('10', 0) / total_shots
    
    return (p_00 + p_11) - (p_01 + p_10)

def compute_bell_parameter_s(e_ab: float, e_ab_prime: float, e_a_prime_b: float, e_a_prime_b_prime: float) -> float:
    """
    Calculates the Bell parameter S. Local hidden variable models are bounded by |S| <= 2.
    Quantum systems can reach the Tsirelson bound of 2 * sqrt(2) ~ 2.828.
    """
    return e_ab - e_ab_prime + e_a_prime_b + e_a_prime_b_prime

# =====================================================================
# SECTION 3: WORKFLOW EXECUTION ENTRYPOINT
# =====================================================================

if __name__ == "__main__":
    chsh_views = ["AB", "Ab", "aB", "ab"]
    print("Initializing ideal local simulation context...")
    
    ideal_simulator = AerSimulator()
    ideal_counts_archive = {}
    
    for view in chsh_views:
        base_circuit = build_bell_state_circuit(f"q_{view}", f"c_{view}")
        compiled_circuit = configure_measurement_basis(base_circuit, view)
        
        job = ideal_simulator.run(compiled_circuit, shots=1024)
        ideal_counts_archive[view] = job.result().get_counts()
        
    # Evaluate variables
    e_AB = evaluate_expectation_value(ideal_counts_archive["AB"])
    e_Ab = evaluate_expectation_value(ideal_counts_archive["Ab"])
    e_aB = evaluate_expectation_value(ideal_counts_archive["aB"])
    e_ab = evaluate_expectation_value(ideal_counts_archive["ab"])
    
    s_parameter = compute_bell_parameter_s(e_AB, e_Ab, e_aB, e_ab)
    
    print("\n" + "="*50)
    print("CHSH EXPERIMENTAL VERIFICATION REPORT")
    print("="*50)
    print(f"Correlation <E(A,B)> : {e_AB:+.4f}")
    print(f"Correlation <E(A,b)> : {e_Ab:+.4f}")
    print(f"Correlation <E(a,B)> : {e_aB:+.4f}")
    print(f"Correlation <E(a,b)> : {e_ab:+.4f}")
    print("-"*50)
    print(f"Calculated Bell Parameter S: {s_parameter:.4f}")
    print(f"Classical Limit (|S| <= 2) Violated: {s_parameter > 2.0}")
    print("="*50 + "\n")

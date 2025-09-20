import pydicom
from pydicom.errors import InvalidDicomError
import os

def parse_rtplan(file_path: str) -> dict:
    """
    Parses an RTPLAN DICOM file and extracts relevant information.

    Args:
        file_path: The path to the RTPLAN DICOM file.

    Returns:
        A dictionary containing the parsed RTPLAN data.

    Raises:
        FileNotFoundError: If the DICOM file is not found.
        InvalidDicomError: If the file is not a valid DICOM file.
        ValueError: If the Modality is not "RTPLAN", or if critical DICOM tags are missing.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error: DICOM file not found at {file_path}")

    try:
        ds = pydicom.dcmread(file_path)
    except InvalidDicomError:
        raise InvalidDicomError(f"Error: Invalid DICOM file at {file_path}")
    except Exception as e:
        raise IOError(f"Error reading DICOM file: {e}")

    # 1. Validate Modality
    if ds.get("Modality") != "RTPLAN":
        raise ValueError("Error: DICOM file is not an RTPLAN. Modality is '{}'.".format(ds.get("Modality")))

    rt_plan_data = {}

    # 2. Extract Top-Level Data
    try:
        rt_plan_data["patient_id"] = ds.PatientID
    except AttributeError:
        raise ValueError("Error: Missing critical tag PatientID (0010,0020)")
        
    rt_plan_data["rt_plan_label"] = ds.get("RTPlanLabel", None) # (300A,0003) - RTPlanName is (300A,0002)
    rt_plan_data["rt_plan_date"] = ds.get("RTPlanDate", None)  # (300A,0006)
    
    # Optional: Extract Number of Beams from FractionGroupSequence
    # This is more of a high-level info, actual beam data comes from IonBeamSequence
    num_beams_from_fraction_group = None
    if "FractionGroupSequence" in ds and ds.FractionGroupSequence:
        # Typically one item in this sequence for RTPLAN
        fraction_group = ds.FractionGroupSequence[0]
        if "NumberOfBeams" in fraction_group:
            num_beams_from_fraction_group = fraction_group.NumberOfBeams
            rt_plan_data["number_of_beams_in_fraction_group"] = num_beams_from_fraction_group
            
    rt_plan_data["beam_energy_unit"] = None # Will be extracted from the first control point of the first beam
    rt_plan_data["beams"] = []

    if not hasattr(ds, 'IonBeamSequence') or not ds.IonBeamSequence:
        # No ion beams, could be an empty plan or a different type of plan not covered
        # Depending on requirements, this could be an error or just return empty beams list.
        # For now, return with empty beams list if sequence is missing/empty.
        # If beams are expected, a stricter check might be needed.
        return rt_plan_data 

    first_beam_first_cp_energy_unit_found = False

    for i, beam_ds in enumerate(ds.IonBeamSequence):
        # Filter out Site Setup and SETUP beams
        beam_description = getattr(beam_ds, 'BeamDescription', '')
        beam_name = getattr(beam_ds, 'BeamName', '')
        
        if beam_description == "Site Setup" or beam_name == "SETUP":
            print(f"Skipping beam {i+1}: {beam_name} (Site Setup or SETUP beam)")
            continue
        
        beam_data = {}
        try:
            beam_data["beam_name"] = beam_ds.BeamName
        except AttributeError:
            beam_data["beam_name"] = f"Beam_{i+1}_Unnamed" # Or raise error
            # raise ValueError(f"Error: Missing BeamName for beam index {i}")

        beam_data["snout_position"] = None # From first control point of this beam
        beam_data["has_range_shifter"] = "RangeShifterSequence" in beam_ds and bool(beam_ds.RangeShifterSequence)
        beam_data["energy_layers"] = []
        
        # Extract TreatmentMachineName for each beam
        try:
            beam_data["treatment_machine_name"] = beam_ds.TreatmentMachineName
        except AttributeError:
            beam_data["treatment_machine_name"] = None

        if not hasattr(beam_ds, 'IonControlPointSequence') or not beam_ds.IonControlPointSequence:
            # No control points for this beam, skip MU calculation for it or error
            rt_plan_data["beams"].append(beam_data) # Add beam with empty energy layers
            continue

        control_points = beam_ds.IonControlPointSequence
        
        # Extract SnoutPosition from the first control point of this beam
        if control_points:
            try:
                beam_data["snout_position"] = control_points[0].SnoutPosition
            except AttributeError:
                # Optional: Log warning or handle as per requirements if missing
                pass 

        # Extract NominalBeamEnergyUnit from the first control point of the *first* beam
        if not first_beam_first_cp_energy_unit_found and control_points:
            try:
                rt_plan_data["beam_energy_unit"] = control_points[0].NominalBeamEnergyUnit
                first_beam_first_cp_energy_unit_found = True
            except AttributeError:
                 # Optional: Log warning if missing, but it's quite important
                pass


        beam_data["control_point_details"] = []
        # MU Calculation Logic
        processed_cps = [] # Stores (energy, cumulative_mu) for this beam
        for cp_ds in control_points:
            try:
                energy = cp_ds.NominalBeamEnergy
                cumulative_mu = cp_ds.CumulativeMetersetWeight
                processed_cps.append({"energy": float(energy), "cumulative_mu": float(cumulative_mu)})
            except AttributeError:
                raise ValueError(f"Error: Missing NominalBeamEnergy or CumulativeMetersetWeight in a control point for beam '{beam_data['beam_name']}'.")
            except (TypeError, ValueError):
                raise ValueError(f"Error: Non-numeric NominalBeamEnergy or CumulativeMetersetWeight in a control point for beam '{beam_data['beam_name']}'.")

        if not processed_cps:
            rt_plan_data["beams"].append(beam_data) # No control points with MU data
            continue

        # Sort by cumulative MU just in case control points are not strictly ordered by MU (should be, but defensive)
        # However, the primary sort/grouping key for layers is energy, and MU diffs are sequential.
        # The DICOM standard implies control points are ordered.

        current_layer_nominal_energy = None
        last_cumulative_mu_for_energy_layer_calculation = 0.0
        
        # Iterate through sorted control points to calculate MU per energy layer
        # This logic assumes control points are ordered correctly.
        # The MU for an energy layer is the difference between its CumulativeMetersetWeight 
        # and the CumulativeMetersetWeight of the previous distinct energy layer's last control point.
        # For the very first energy layer, its MU is its own CumulativeMetersetWeight.

        # Extract detailed control point data for interpolation
        for cp_ds in control_points:
            try:
                cp_detail = {
                    'energy': float(cp_ds.NominalBeamEnergy),
                    'cumulative_mu': float(cp_ds.CumulativeMetersetWeight),
                    'scan_spot_positions': [],
                    'scan_spot_meterset_weights': []
                }
                
                # Try to extract scan spot data using different methods
                # Method 1: Standard tags (for PBS)
                if hasattr(cp_ds, 'ScanSpotPositionMap') and cp_ds.ScanSpotPositionMap:
                    cp_detail['scan_spot_positions'] = [float(pos) for pos in cp_ds.ScanSpotPositionMap]
                    
                if hasattr(cp_ds, 'ScanSpotMetersetWeights') and cp_ds.ScanSpotMetersetWeights:
                    cp_detail['scan_spot_meterset_weights'] = [float(weight) for weight in cp_ds.ScanSpotMetersetWeights]
                
                # Method 2: Try Line Scanning Position Map (for line scanning)
                try:
                    # Check for Line Scanning Position Map - tag (300B,1094)
                    if hasattr(cp_ds, 'data_element') or (0x300b, 0x1094) in cp_ds:
                        import numpy as np
                        # Extract binary data and convert to float32
                        line_scan_data = cp_ds[0x300b, 0x1094].value
                        positions_array = np.frombuffer(line_scan_data, dtype=np.float32)
                        # Convert from mm to mm and reshape to (n, 2) pairs
                        positions_reshaped = np.reshape(0.1 * positions_array, (len(positions_array)//2, 2))
                        cp_detail['scan_spot_positions'] = positions_reshaped.flatten().tolist()
                        
                        # Extract Line Scanning Meterset Weights - tag (300B,1096)
                        if (0x300b, 0x1096) in cp_ds:
                            weights_data = cp_ds[0x300b, 0x1096].value
                            weights_array = np.frombuffer(weights_data, dtype=np.float32)
                            cp_detail['scan_spot_meterset_weights'] = weights_array.tolist()
                            
                except Exception as e:
                    # If line scanning data extraction fails, continue with empty arrays
                    pass
                
                beam_data["control_point_details"].append(cp_detail)
                
            except (AttributeError, TypeError, ValueError) as e:
                # Handle cases where tags are missing or data is invalid
                print(f"Warning: Could not extract full control point details for beam '{beam_data['beam_name']}'. Error: {e}")
                # Depending on strictness, you might want to raise an error here
                continue

        # Let's group by energy first, then process
        # No, the C++ logic iterates and calculates when energy changes or at the end.

        # Simplified logic attempt:
        # Group control points by energy, maintaining order of first appearance of that energy.
        # Then calculate MU for each energy block.

        # More direct approach based on iterating CPs and detecting energy changes:
        
        # Store (energy, cumulative_mu_at_end_of_layer)
        # This will hold the *final* cumulative MU for each energy layer block.
        # e.g. if energy 70 has CPs with MU 2, 5, 7, then (70, 7) is stored.
        # if energy 80 has CPs with MU 10, 12, then (80, 12) is stored.
        
        # Corrected MU calculation logic:
        # Iterate through control points. When energy changes, the MU for the *previous*
        # energy layer is the CumulativeMetersetWeight of the *last control point of that previous energy*
        # minus the CumulativeMetersetWeight of the *last control point of the layer before that*.
        
        layer_end_points = [] # list of (energy, cumulative_mu_at_end_of_layer)
        if processed_cps:
            current_energy = processed_cps[0]['energy']
            for k in range(len(processed_cps)):
                # If energy changes or it's the last CP, then the previous CP (k-1) was the end of an energy layer
                if k + 1 < len(processed_cps) and processed_cps[k+1]['energy'] != current_energy:
                    layer_end_points.append({'energy': current_energy, 'cumulative_mu': processed_cps[k]['cumulative_mu']})
                    current_energy = processed_cps[k+1]['energy']
                elif k == len(processed_cps) - 1: # Last control point
                    layer_end_points.append({'energy': current_energy, 'cumulative_mu': processed_cps[k]['cumulative_mu']})
        
        previous_layer_ending_mu = 0.0
        for layer_info in layer_end_points:
            mu_for_layer = layer_info['cumulative_mu'] - previous_layer_ending_mu
            if mu_for_layer < 0: # Should not happen in a valid plan
                # Potentially raise error or warning
                print(f"Warning: Negative MU calculated for energy {layer_info['energy']} in beam {beam_data['beam_name']}. MU: {mu_for_layer}")
            
            # Avoid adding layers with zero or negative MU if that's a requirement
            # For now, adding them as calculated.
            beam_data["energy_layers"].append({
                "nominal_energy": layer_info['energy'],
                "mu": round(mu_for_layer, 7) # Round to avoid floating point issues, precision can be adjusted
            })
            previous_layer_ending_mu = layer_info['cumulative_mu']
            
        rt_plan_data["beams"].append(beam_data)

    return rt_plan_data

if __name__ == '__main__':
    pass


def extract_aperture_data(beam_ds):
    """
    Extract aperture block information from a beam dataset.
    
    Args:
        beam_ds: DICOM beam dataset
        
    Returns:
        dict: Aperture data or None if no aperture found
    """
    aperture_data = None
    
    if hasattr(beam_ds, 'IonBlockSequence') and beam_ds.IonBlockSequence:
        block_sequence = beam_ds.IonBlockSequence
        if len(block_sequence) > 0:
            block = block_sequence[0]  # Take first block
            
            aperture_data = {
                'device_type': 'aperture',
                'thickness_cm': getattr(block, 'BlockThickness', 5.0) / 10.0,  # Convert mm to cm
                'material': getattr(block, 'BlockMaterial', 'CERROBEND'),
                'coordinate_system': 'DICOM_IEC',
                'block_data': []
            }
            
            # Extract block coordinates
            if hasattr(block, 'BlockData'):
                block_data = block.BlockData
                # BlockData is in 0.1mm units, convert to cm
                coords = []
                for i in range(0, len(block_data), 2):
                    if i + 1 < len(block_data):
                        x_coord = float(block_data[i]) / 100.0  # 0.1mm to cm
                        y_coord = float(block_data[i + 1]) / 100.0  # 0.1mm to cm
                        coords.append([x_coord, y_coord])
                aperture_data['block_data'] = coords
                
    return aperture_data


def extract_mlc_data(beam_ds):
    """
    Extract MLC information from a beam dataset.
    
    Args:
        beam_ds: DICOM beam dataset
        
    Returns:
        dict: MLC data or None if no MLC found
    """
    mlc_data = None
    
    if hasattr(beam_ds, 'IonBeamLimitingDeviceSequence') and beam_ds.IonBeamLimitingDeviceSequence:
        limiting_device_seq = beam_ds.IonBeamLimitingDeviceSequence
        
        # Find MLC device
        mlc_device = None
        for device in limiting_device_seq:
            if hasattr(device, 'RTBeamLimitingDeviceType') and 'MLC' in device.RTBeamLimitingDeviceType:
                mlc_device = device
                break
                
        if mlc_device:
            mlc_data = {
                'device_type': 'mlc',
                'coordinate_system': 'DICOM_IEC',
                'leaf_positions': []
            }
            
            # Extract leaf position boundaries
            leaf_boundaries = []
            if hasattr(mlc_device, 'LeafPositionBoundaries'):
                leaf_boundaries = [float(pos) / 10.0 for pos in mlc_device.LeafPositionBoundaries]  # mm to cm
                mlc_data['num_leaves'] = len(leaf_boundaries) - 1 if leaf_boundaries else 0
                mlc_data['leaf_width_cm'] = leaf_boundaries[1] - leaf_boundaries[0] if len(leaf_boundaries) > 1 else 0.5
            
            # Extract leaf positions from control points
            if hasattr(beam_ds, 'IonControlPointSequence') and beam_ds.IonControlPointSequence:
                for cp in beam_ds.IonControlPointSequence:
                    if hasattr(cp, 'NominalBeamEnergy') and hasattr(cp, 'BeamLimitingDevicePositionSequence'):
                        energy = float(cp.NominalBeamEnergy)
                        
                        for device_pos in cp.BeamLimitingDevicePositionSequence:
                            if hasattr(device_pos, 'RTBeamLimitingDeviceType') and 'MLC' in device_pos.RTBeamLimitingDeviceType:
                                if hasattr(device_pos, 'LeafJawPositions'):
                                    leaf_positions = device_pos.LeafJawPositions
                                    N = len(leaf_positions)
                                    
                                    if N < 2:
                                        continue
                                    
                                    # N must be even for proper MLC pair formation
                                    if N % 2 != 0:
                                        print(f"Warning: Odd number of MLC positions ({N}) in energy {energy}. Using N//2 for leaf pair calculation.")
                                    
                                    # Convert mm to cm and organize by leaf pairs
                                    # Use N//2 to ensure integer division
                                    num_leaves = N // 2
                                    
                                    if num_leaves == 0:
                                        continue
                                    
                                    for leaf_idx in range(num_leaves):
                                        left_pos = float(leaf_positions[leaf_idx]) / 10.0  # mm to cm
                                        right_pos = float(leaf_positions[leaf_idx + num_leaves]) / 10.0  # mm to cm
                                        
                                        mlc_data['leaf_positions'].append({
                                            'layer_energy_mev': energy,
                                            'leaf_index': leaf_idx + 1,
                                            'left_pos_cm': left_pos,
                                            'right_pos_cm': right_pos
                                        })
                                    
    return mlc_data

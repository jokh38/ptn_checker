import os

def parse_scv_init(file_path: str) -> dict:
    """
    Parses a scv_init file to extract configuration parameters.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    config = {}
    allowed_keys = {'XPOSGAIN', 'YPOSGAIN', 'XPOSOFFSET', 'YPOSOFFSET', 'TIMEGAIN', 'FILTERED_BEAM_ON_OFF'}

    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) == 2 and parts[0] in allowed_keys:
                key, value = parts
                if key == 'FILTERED_BEAM_ON_OFF':
                    # Handle string values for this parameter
                    config[key] = value.lower()
                else:
                    try:
                        config[key] = float(value)
                    except ValueError:
                        # Ignore if value is not a valid float
                        pass
    return config
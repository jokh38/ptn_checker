import os


def find_ptn_files(directory: str, *, sort_paths: bool = False) -> list[str]:
    """Return PTN files under ``directory`` with optional deterministic ordering."""
    ptn_files = []
    for root, _, files in os.walk(directory):
        for file_name in files:
            if file_name.endswith(".ptn"):
                ptn_files.append(os.path.join(root, file_name))

    if sort_paths:
        return sorted(ptn_files)
    return ptn_files

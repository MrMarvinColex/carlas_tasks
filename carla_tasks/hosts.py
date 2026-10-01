"""Non-secret execution-host identity for distinguishing local checks from exports."""
from __future__ import annotations

import hashlib
import platform
from pathlib import Path


def host_identity() -> str:
    values = [platform.system(), platform.node()]
    machine_id = Path("/etc/machine-id")
    try:
        if machine_id.is_file():
            values.append(machine_id.read_text().strip())
    except OSError:
        # Non-Linux hosts and restricted containers can still record provenance.
        pass
    # Never persist raw hostname or machine ID. This is provenance, not a
    # guarantee that two storage devices have independent failure domains.
    return hashlib.sha256("\n".join(values).encode()).hexdigest()

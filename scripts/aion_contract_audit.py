#!/usr/bin/env python3
"""Run the offline AION local contract auditor from a checkout root."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlasquant_aion_contract_auditor import main


if __name__ == "__main__":
    sys.exit(main())

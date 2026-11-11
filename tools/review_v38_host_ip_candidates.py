#!/usr/bin/env python3
"""Load compressed review-only RIPE/RDAP enrichment implementation."""
import gzip
from pathlib import Path

_source = Path(__file__).with_suffix(Path(__file__).suffix + ".gz")
_code = gzip.open(_source, "rt", encoding="utf-8").read()
exec(compile(_code, str(_source), "exec"), globals(), globals())

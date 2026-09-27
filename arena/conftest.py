"""Configure Django for Arena tests invoked from the repository root."""
import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "arc_backend.settings")
django.setup()

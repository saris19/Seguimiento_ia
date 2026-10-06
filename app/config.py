"""Global configuration for the process tracking platform."""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
STATIC_DIR = BASE_DIR / "static"

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'processes.db'}")

# Maximum upload size per document (bytes)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# AI supervisor thresholds
MIN_SCORE_TO_ADVANCE = 70          # minimum compliance score to let a phase advance
HIGH_RISK_THRESHOLD = 0.65         # delay probability considered high
MEDIUM_RISK_THRESHOLD = 0.40       # delay probability considered medium
DEADLINE_WARNING_RATIO = 0.80      # warn when 80% of the planned time has elapsed

# Words that usually indicate placeholder / incomplete content
PLACEHOLDER_WORDS = ["lorem", "ipsum", "xxx", "tbd", "por definir", "n/a", "asdf", "qwerty"]

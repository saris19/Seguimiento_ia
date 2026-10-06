"""Use an isolated temporary database and no demo data during tests."""
import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
os.environ.setdefault("SEED_DEMO", "0")

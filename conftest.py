"""Shared fixtures and setup for all tests."""

import os
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("MPLBACKEND", "Agg")

from ophyd_epicsrs import use_epicsrs_backend
use_epicsrs_backend()

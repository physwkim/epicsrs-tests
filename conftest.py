"""Shared fixtures and setup for all tests."""

import os
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("TEST_CL", "epicsrs")

from ophyd_epicsrs import use_epicsrs_backend
use_epicsrs_backend()

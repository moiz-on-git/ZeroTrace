"""
ZeroTrace Multi-Service Root Package.
Exposes orchestrator services (evidence_generator, lineage_discovery, orchestration, policy_engine)
seamlessly across root and subproject imports.
"""
import os
import sys

# Dynamically ensure orchestrator services are on this namespace package's search path
_orch_services_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "orchestrator", "src", "services")
)
if _orch_services_path not in __path__:
    __path__.append(_orch_services_path)

# Also ensure orchestrator/src is in sys.path
_orch_src_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "orchestrator", "src")
)
if _orch_src_path not in sys.path:
    sys.path.insert(0, _orch_src_path)

try:
    import evidence_generator  # type: ignore
    import lineage_discovery  # type: ignore
    import orchestration  # type: ignore
    import policy_engine  # type: ignore
except ImportError:
    pass

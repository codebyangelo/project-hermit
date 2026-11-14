"""Project Hermit - Autonomous Self-Evolving Code & Logic Engine.

Mobile-native closed-loop autonomous self-optimization engine and dynamic
Model Context Protocol (MCP) tool host.
"""

__version__ = "1.0.0"
__author__ = "Angelo Hershall Heith Ayton"
__license__ = "Apache-2.0"

from hermit.orchestrator import Orchestrator
from hermit.hermit_daemon import HermitDaemon
from hermit.sandbox import run_in_sandbox, SandboxResult, analyze_code_safety
from hermit.logger import ExecutionLogger
from hermit.observer import EvolutionObserver
from hermit.researcher import ResearcherAgent

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "Orchestrator",
    "HermitDaemon",
    "run_in_sandbox",
    "SandboxResult",
    "analyze_code_safety",
    "ExecutionLogger",
    "EvolutionObserver",
    "ResearcherAgent",
]

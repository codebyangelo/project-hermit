"""Command Line Interface for Project Hermit."""

import argparse
import os
import sys
import sqlite3
from hermit import __version__


def get_db_path(custom_path: str = None) -> str:
    if custom_path:
        return custom_path
    env_path = os.environ.get("HERMIT_DB_PATH")
    if env_path:
        return env_path
    # Default to current directory or package directory
    local_path = os.path.join(os.getcwd(), "hermit_memory.db")
    if os.path.exists(local_path):
        return local_path
    pkg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermit_memory.db")
    return pkg_path


def cmd_status(args):
    """Show Hermit database status and active skills."""
    db_path = get_db_path(args.db)
    print(f"[*] Project Hermit v{__version__}")
    print(f"[*] Database Path: {db_path}")

    if not os.path.exists(db_path):
        print("[-] Database does not exist yet. Run 'hermit init-db' to initialize.")
        return 0

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM active_skills")
        skills_count = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        skills_count = "Table missing"

    try:
        cursor.execute("SELECT COUNT(*) FROM reality_tests")
        tests_count = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        tests_count = "Table missing"

    try:
        cursor.execute("SELECT COUNT(*) FROM limit_telemetry")
        telemetry_count = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        telemetry_count = "Table missing"

    db_size = os.path.getsize(db_path) / (1024 * 1024)

    print(f"[+] Database Size:      {db_size:.2f} MB")
    print(f"[+] Active Skills:      {skills_count}")
    print(f"[+] Reality Tests:      {tests_count}")
    print(f"[+] Telemetry Records:  {telemetry_count}")
    conn.close()
    return 0


def cmd_init_db(args):
    """Initialize database tables."""
    from hermit.init_db import init_database
    db_path = args.db or os.path.join(os.getcwd(), "hermit_memory.db")
    print(f"[*] Initializing Hermit database schema at: {db_path}")
    init_database(db_path)
    print("[+] Database schema successfully initialized.")
    return 0


def cmd_daemon(args):
    """Run the autonomous evolution daemon."""
    from hermit.hermit_daemon import HermitDaemon
    print(f"[*] Starting Project Hermit Autonomous Daemon v{__version__}...")
    daemon = HermitDaemon(
        interval=args.interval,
        max_cycles=args.max_cycles,
        db_path=args.db
    )
    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\n[*] Daemon received shutdown interrupt. Halting cleanly.")
    return 0


def cmd_chat(args):
    """Start interactive chat console."""
    from hermit.hermit_chat import main as chat_main
    return chat_main()


def cmd_monitor(args):
    """Start real-time evolution monitor."""
    from hermit.monitor_evolution import main as monitor_main
    return monitor_main()


def cmd_mcp(args):
    """Run dynamic MCP server over stdio."""
    from hermit.dynamic_mcp_server import main as mcp_main
    return mcp_main()


def build_parser() -> argparse.ArgumentParser:
    db_parent = argparse.ArgumentParser(add_help=False)
    db_parent.add_argument(
        "--db",
        type=str,
        default=None,
        help="Custom SQLite database path"
    )

    parser = argparse.ArgumentParser(
        prog="hermit",
        description="Project Hermit: Autonomous Self-Evolving Code & Logic Engine",
        parents=[db_parent]
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"hermit {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # status
    p_status = subparsers.add_parser("status", parents=[db_parent], help="Show database status and active skills")
    p_status.set_defaults(func=cmd_status)

    # init-db
    p_init = subparsers.add_parser("init-db", parents=[db_parent], help="Initialize database schema")
    p_init.set_defaults(func=cmd_init_db)

    # daemon
    p_daemon = subparsers.add_parser("daemon", parents=[db_parent], help="Run autonomous self-evolution daemon")
    p_daemon.add_argument("--interval", type=float, default=10.0, help="Loop interval in seconds")
    p_daemon.add_argument("--max-cycles", type=int, default=None, help="Stop after N cycles")
    p_daemon.set_defaults(func=cmd_daemon)

    # chat
    p_chat = subparsers.add_parser("chat", parents=[db_parent], help="Start interactive CLI steering chat")
    p_chat.set_defaults(func=cmd_chat)

    # monitor
    p_monitor = subparsers.add_parser("monitor", parents=[db_parent], help="Start evolution monitor dashboard")
    p_monitor.set_defaults(func=cmd_monitor)

    # mcp
    p_mcp = subparsers.add_parser("mcp", parents=[db_parent], help="Start dynamic MCP tool server over stdio")
    p_mcp.set_defaults(func=cmd_mcp)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)

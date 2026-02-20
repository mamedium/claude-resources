#!/usr/bin/env python3
"""mac-health: read-only macOS RAM + storage inspector.

Prints reports and copy-paste commands. Never executes destructive actions.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

HOME = str(Path.home())

# Paths that must never appear in any suggested delete command
HARD_PROTECTED_ROOTS = [
    # Add your own protected paths here (e.g. cloud storage sync directories)
    f"{HOME}/.claude",
    f"{HOME}/Documents",
    f"{HOME}/Desktop",
    f"{HOME}/Library/Mobile Documents",  # iCloud
    "/System",
    "/Library",
    "/usr",
    "/bin",
    "/sbin",
]

# Process names that must never appear in any suggested kill command
BLOCKED_PROCESS_NAMES = {
    "launchd", "kernel_task", "WindowServer", "loginwindow",
    "systemstats", "hidd", "mds", "mds_stores", "coreaudiod",
    "bash", "zsh", "fish", "tmux", "sshd", "Finder",
}


def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""


def run_shell(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""


def self_pid_tree() -> set[int]:
    """PIDs of the current Claude Code session (self + all ancestors)."""
    pids = {os.getpid(), os.getppid()}
    cur = os.getppid()
    guard = 0
    while cur and cur != 1 and guard < 40:
        guard += 1
        out = run(["ps", "-o", "ppid=", "-p", str(cur)]).strip()
        try:
            cur = int(out) if out else 0
        except ValueError:
            break
        if cur:
            pids.add(cur)
    return pids


def is_safe_to_kill(pid: int, name: str, self_pids: set[int]) -> bool:
    if pid < 500:
        return False
    if pid in self_pids:
        return False
    base = os.path.basename(name).strip()
    if base in BLOCKED_PROCESS_NAMES:
        return False
    return True


def is_safe_to_suggest_delete(path: str) -> bool:
    if not path:
        return False
    abs_path = os.path.abspath(os.path.expanduser(path))
    for root in HARD_PROTECTED_ROOTS:
        root_abs = os.path.abspath(os.path.expanduser(root))
        if abs_path == root_abs or abs_path.startswith(root_abs + "/"):
            return False
    return True


# ---------- RAM ----------

def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def ram_report() -> None:
    print("=== macOS RAM Report ===\n")

    # Total RAM
    total_bytes = 0
    try:
        total_bytes = int(run(["sysctl", "-n", "hw.memsize"]).strip() or 0)
    except ValueError:
        pass

    # vm_stat
    vm = run(["vm_stat"])
    page_size = 4096
    m = re.search(r"page size of (\d+) bytes", vm)
    if m:
        page_size = int(m.group(1))

    def _pages(key: str) -> int:
        m = re.search(rf"{re.escape(key)}:\s+(\d+)", vm)
        return int(m.group(1)) if m else 0

    free_pages = _pages("Pages free") + _pages("Pages speculative")
    active = _pages("Pages active") * page_size
    wired = _pages("Pages wired down") * page_size
    compressed = _pages("Pages occupied by compressor") * page_size
    free_bytes = free_pages * page_size

    # Swap
    swap = run(["sysctl", "vm.swapusage"]).strip()
    swap_used = "unknown"
    m = re.search(r"used\s*=\s*([\d.]+[KMGT])", swap)
    if m:
        swap_used = m.group(1)

    # Pressure (best-effort; memory_pressure is interactive on some systems)
    pressure = "unknown"
    mp = run_shell("memory_pressure 2>&1 | head -20")
    m = re.search(r"System-wide memory free percentage:\s*(\d+)%", mp)
    if m:
        pct = int(m.group(1))
        pressure = "ok" if pct > 20 else "warn" if pct > 10 else "critical"

    free_pct = (free_bytes / total_bytes * 100) if total_bytes else 0
    print(
        f"Total: {_human_bytes(total_bytes):>9}  |  "
        f"Free: {_human_bytes(free_bytes):>9} ({free_pct:.0f}%)  |  "
        f"Active: {_human_bytes(active):>9}  |  "
        f"Wired: {_human_bytes(wired):>9}  |  "
        f"Compressed: {_human_bytes(compressed):>9}"
    )
    print(f"Swap used: {swap_used}   |   Pressure: {pressure}\n")

    # Top 15 by RSS (-m sorts by memory on BSD ps; NOT -r which is CPU)
    print("Top memory users (sorted by RSS):")
    print(f"  {'PID':>7}  {'RSS':>10}  {'COMMAND':<50}  SUGGESTED")
    ps_out = run(["ps", "-Ao", "pid,rss,comm", "-m"])
    self_pids = self_pid_tree()
    lines = ps_out.splitlines()[1:16]  # skip header, take 15
    for line in lines:
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            rss_kb = int(parts[1])
        except ValueError:
            continue
        comm = parts[2][:50]
        rss_h = _human_bytes(rss_kb * 1024)
        safe = is_safe_to_kill(pid, comm, self_pids)
        suggestion = f"kill {pid}" if safe else "(protected)"
        print(f"  {pid:>7}  {rss_h:>10}  {comm:<50}  {suggestion}")

    # Orphaned MCP processes (pgrep -E for alternation on BSD)
    print("\nOrphaned MCP processes (from prior Claude Code sessions):")
    mcp_out = run(["pgrep", "-Eaf", r"@playwright/mcp|beads-mcp|mcp-server|modelcontextprotocol"])
    found = False
    for line in mcp_out.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        if pid in self_pids:
            continue
        cmdline = parts[1][:70]
        if not is_safe_to_kill(pid, cmdline.split()[0] if cmdline else "", self_pids):
            continue
        print(f"  {pid:>7}  {cmdline:<70}  kill {pid}")
        found = True
    if not found:
        print("  (none found)")

    print('\nTo reclaim: copy any of the "kill <pid>" lines above and run them yourself.')


# ---------- STORAGE ----------

def _du_sh(path: str) -> str:
    out = run_shell(f'du -sh "{os.path.expanduser(path)}" 2>/dev/null')
    if not out:
        return "-"
    return out.split()[0]


def storage_report() -> None:
    print("=== macOS Storage Report ===\n")

    # df overview
    df = run(["df", "-h", "/"]).strip()
    if df:
        lines = df.splitlines()
        if len(lines) >= 2:
            print(lines[0])
            print(lines[1])
    print()

    # Categories: (label, measure_path_or_cmd, suggested_command, note)
    categories = [
        ("System caches",        f"{HOME}/Library/Caches",                          f"rm -rf {HOME}/Library/Caches/*",                             ""),
        ("System logs",          f"{HOME}/Library/Logs",                            f"rm -rf {HOME}/Library/Logs/*",                               ""),
        ("Xcode DerivedData",    f"{HOME}/Library/Developer/Xcode/DerivedData",     f"rm -rf {HOME}/Library/Developer/Xcode/DerivedData/*",        "ensure Xcode is idle"),
        ("Xcode Archives",       f"{HOME}/Library/Developer/Xcode/Archives",        "(manual — keep recent builds)",                                ""),
        ("pnpm store",           f"{HOME}/Library/pnpm/store",                      "pnpm store prune",                                             ""),
        ("npm cache",            f"{HOME}/.npm",                                    "npm cache clean --force",                                      ""),
        ("yarn cache",           f"{HOME}/.yarn/cache",                             "yarn cache clean",                                             ""),
        ("Trash",                f"{HOME}/.Trash",                                  f"rm -rf {HOME}/.Trash/*",                                      ""),
    ]

    print(f"{'Category':<22} {'Size':>10}   Suggested command")
    print("-" * 90)

    for label, path, cmd, note in categories:
        size = _du_sh(path)
        # Guard: if the cleanup command contains a path inside protected roots, skip it
        rm_paths = re.findall(r"(?:rm -rf|rm)\s+(\S+)", cmd)
        blocked = False
        for p in rm_paths:
            if not is_safe_to_suggest_delete(p):
                blocked = True
                break
        if blocked:
            display = "(protected — skipped)"
        else:
            display = cmd + (f"  ({note})" if note else "")
        print(f"{label:<22} {size:>10}   {display}")

    # Homebrew cache (dynamic path)
    brew_cache = run_shell("brew --cache 2>/dev/null").strip()
    if brew_cache:
        size = _du_sh(brew_cache)
        print(f"{'Homebrew cache':<22} {size:>10}   brew cleanup -s --prune=all")

    # iOS simulators (count-based, not size)
    sim_list = run_shell('xcrun simctl list devices unavailable 2>/dev/null | grep -c "("')
    try:
        sim_count = int(sim_list.strip() or 0)
    except ValueError:
        sim_count = 0
    if sim_count:
        print(f"{'iOS Simulators':<22} {str(sim_count)+' unav':>10}   xcrun simctl delete unavailable")

    # Downloads >30 days
    dl_out = run_shell(
        f'find "{HOME}/Downloads" -type f -mtime +30 2>/dev/null | wc -l'
    ).strip()
    try:
        dl_count = int(dl_out or 0)
    except ValueError:
        dl_count = 0
    if dl_count:
        dl_size = run_shell(
            f'find "{HOME}/Downloads" -type f -mtime +30 -print0 2>/dev/null | xargs -0 du -ch 2>/dev/null | tail -1'
        ).split()
        dl_size_str = dl_size[0] if dl_size else "-"
        print(f"{'Downloads >30d':<22} {dl_size_str:>10}   ({dl_count} files — ask Claude to list them)")

    print("\nTo reclaim: copy any command above and run it yourself.")


# ---------- CLI ----------

def main() -> int:
    p = argparse.ArgumentParser(prog="mac_health", description="macOS RAM + storage inspector (read-only)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ram", help="RAM pressure + top memory users + orphaned MCPs")
    sub.add_parser("storage", help="Disk overview + category sizes")
    args = p.parse_args()

    if args.cmd == "ram":
        ram_report()
    elif args.cmd == "storage":
        storage_report()
    else:
        p.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

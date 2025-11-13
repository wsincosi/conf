#!/usr/bin/env python3
"""
scan_ips.py - Recursively scan files in a directory for IP addresses.

Features:
- Detects IPv4 and IPv6 (including compressed and IPv4-mapped forms).
- Reads all files as UTF-8 with replacement (so it won't crash on weird encodings).
- Optionally parses .pcap/.pcapng files using scapy (if installed) to extract
  IPs from packet headers.
- Supports useful CLI options for coworkers and CI/pre-commit usage.
"""

import argparse
import ipaddress
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
import re


# --- IP detection helpers ----------------------------------------------------


# Candidate IPv4 pattern: four 1–3 digit groups separated by dots, not part of a longer number
CANDIDATE_IPV4_RE = re.compile(
    r"(?<!\d)(\d{1,3}(?:\.\d{1,3}){3})(?!\d)"
)

# Candidate IPv6 pattern: hex digits, colons, and dots (for IPv4-mapped), bounded
CANDIDATE_IPV6_RE = re.compile(
    r"(?<![0-9A-Fa-f:.])([0-9A-Fa-f:.]{2,45})(?![0-9A-Fa-f:.])"
)


def _find_ipv4(text: str) -> Set[str]:
    """Return a set of IPv4 addresses found in the given text.

    This is permissive with formatting (allows leading zeros),
    but enforces numeric range 0–255 for each octet.
    """
    results: Set[str] = set()
    for candidate in CANDIDATE_IPV4_RE.findall(text):
        parts = candidate.split(".")
        if len(parts) != 4:
            continue
        try:
            octets = [int(p) for p in parts]
        except ValueError:
            continue
        if all(0 <= o <= 255 for o in octets):
            # Keep the original string as it appeared in the file
            results.add(candidate)
    return results


def _find_ipv6(text: str) -> Set[str]:
    """Return a set of IPv6 addresses found in the given text.

    Uses a broad regex and validates candidates with ipaddress.ip_address.
    """
    results: Set[str] = set()
    for candidate in CANDIDATE_IPV6_RE.findall(text):
        try:
            ip = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        # Filter to IPv6 only here; IPv4 is handled separately.
        if isinstance(ip, ipaddress.IPv6Address):
            results.add(candidate)
    return results


def find_ips_in_text(
    text: str, *, ipv4: bool = True, ipv6: bool = True
) -> Tuple[Set[str], Set[str]]:
    """Return (ipv4_set, ipv6_set) of addresses found in text."""
    v4: Set[str] = set()
    v6: Set[str] = set()
    if ipv4:
        v4 = _find_ipv4(text)
    if ipv6:
        v6 = _find_ipv6(text)
    return v4, v6


# --- File scanning -----------------------------------------------------------


TEXT_LIKE_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".log",
    ".xml",
    ".html",
    ".htm",
    ".js",
    ".ts",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".sh",
    ".bat",
    ".ps1",
}


def is_probably_text(path: Path) -> bool:
    """Heuristic: treat as text if extension is in a known set.

    Currently not used to skip anything, but kept for potential future tuning.
    """
    return path.suffix.lower() in TEXT_LIKE_EXTENSIONS


def read_file_as_text(path: Path) -> Optional[str]:
    """Read a file as text using UTF-8 with replacement.

    Returns None if the file cannot be read.
    """
    try:
        data = path.read_bytes()
    except (OSError, PermissionError):
        return None
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        # Very unlikely given errors="ignore", but be defensive.
        return None


def scan_text_file(path: Path, *, ipv4: bool, ipv6: bool) -> Tuple[Set[str], Set[str]]:
    """Scan a regular text-like file for IPs."""
    text = read_file_as_text(path)
    if text is None:
        return set(), set()
    return find_ips_in_text(text, ipv4=ipv4, ipv6=ipv6)


def scan_pcap_file(path: Path) -> Tuple[Set[str], Set[str]]:
    """Scan a .pcap or .pcapng file using scapy, if available.

    Returns (ipv4_set, ipv6_set). If scapy is not installed or the file
    cannot be parsed, returns empty sets.
    """
    try:
        from scapy.all import IP, rdpcap  # type: ignore
    except Exception:
        # Scapy not available; skip pcap scanning.
        return set(), set()

    # We access IPv6 layer by string name to be compatible with scapy versions.
    v4: Set[str] = set()
    v6: Set[str] = set()
    try:
        packets = rdpcap(str(path))
    except Exception:
        return set(), set()

    for pkt in packets:
        # IPv4
        if IP in pkt:
            layer = pkt[IP]
            src = getattr(layer, "src", None)
            dst = getattr(layer, "dst", None)
            if src:
                v4.add(str(src))
            if dst:
                v4.add(str(dst))
        # IPv6
        if "IPv6" in pkt:
            layer = pkt["IPv6"]
            src = getattr(layer, "src", None)
            dst = getattr(layer, "dst", None)
            if src:
                v6.add(str(src))
            if dst:
                v6.add(str(dst))

    return v4, v6


def should_skip_dir(dirname: str, skip_dirs: Set[str]) -> bool:
    """Return True if this directory should be skipped."""
    return dirname in skip_dirs


def iter_paths(root: Path, skip_dirs: Set[str]) -> Iterable[Path]:
    """Yield all files under root, respecting directory skip rules."""
    if root.is_file():
        yield root
        return

    for dirpath, dirnames, filenames in os.walk(root):
        # Apply directory skipping in-place to avoid descending into them
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d, skip_dirs)]
        for name in filenames:
            yield Path(dirpath) / name


# --- CLI ---------------------------------------------------------------------


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recursively scan files in a directory for IPv4/IPv6 addresses."
    )
    parser.add_argument(
        "path",
        type=str,
        help="File or directory to scan.",
    )
    parser.add_argument(
        "--ipv4-only",
        action="store_true",
        help="Only search for IPv4 addresses.",
    )
    parser.add_argument(
        "--ipv6-only",
        action="store_true",
        help="Only search for IPv6 addresses.",
    )
    parser.add_argument(
        "--include-ext",
        nargs="*",
        metavar="EXT",
        default=None,
        help="Only scan files with these extensions (e.g. .py .txt .log). "
             "By default, all extensions are scanned.",
    )
    parser.add_argument(
        "--exclude-ext",
        nargs="*",
        metavar="EXT",
        default=None,
        help="Skip files with these extensions (e.g. .png .jpg .zip).",
    )
    parser.add_argument(
        "--skip-dirs",
        nargs="*",
        metavar="NAME",
        default=[".git", ".hg", ".svn", ".idea", ".vscode", ".venv", "venv", "node_modules"],
        help="Directory names to skip while scanning. Defaults to common tool directories.",
    )
    parser.add_argument(
        "--pcap",
        action="store_true",
        help="Also parse .pcap/.pcapng files using scapy (if installed).",
    )
    parser.add_argument(
        "--fail-on-found",
        action="store_true",
        help="Exit with code 1 if any IP addresses are found. "
             "Useful for CI or pre-commit hooks.",
    )
    parser.add_argument(
        "--relative",
        action="store_true",
        help="Print file paths relative to the provided root path.",
    )

    args = parser.parse_args(argv)

    if args.ipv4_only and args.ipv6_only:
        parser.error("Cannot use --ipv4-only and --ipv6-only at the same time.")

    return args


def normalize_ext_list(exts: Optional[List[str]]) -> Optional[Set[str]]:
    if exts is None:
        return None
    norm: Set[str] = set()
    for e in exts:
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        norm.add(e.lower())
    return norm or None


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    root = Path(args.path).resolve()
    if not root.exists():
        raise SystemExit(f"Path does not exist: {root}")

    include_ext = normalize_ext_list(args.include_ext)
    exclude_ext = normalize_ext_list(args.exclude_ext)
    skip_dirs = set(args.skip_dirs or [])

    search_ipv4 = not args.ipv6_only
    search_ipv6 = not args.ipv4_only

    found_any = False
    total_files = 0
    files_with_ips = 0

    root_for_rel = root if root.is_dir() else root.parent

    results: Dict[Path, Tuple[Set[str], Set[str]]] = {}

    for path in iter_paths(root, skip_dirs=skip_dirs):
        total_files += 1
        suffix = path.suffix.lower()

        if include_ext is not None and suffix not in include_ext:
            continue
        if exclude_ext is not None and suffix in exclude_ext:
            continue

        v4: Set[str] = set()
        v6: Set[str] = set()

        is_pcap = args.pcap and suffix in {".pcap", ".pcapng"}

        if is_pcap:
            v4, v6 = scan_pcap_file(path)

        # Always also scan the textual representation, even for pcaps;
        # this keeps behaviour consistent if someone has ASCII IPs in a pcap
        # wrapper or comments.
        tv4, tv6 = scan_text_file(path, ipv4=search_ipv4, ipv6=search_ipv6)
        v4 |= tv4
        v6 |= tv6

        if v4 or v6:
            found_any = True
            files_with_ips += 1
            results[path] = (v4, v6)

    # --- Reporting -----------------------------------------------------------

    if not results:
        print(f"No IP addresses found under {root}")
    else:
        print(f"IP addresses found under {root}:\n")

        for path, (v4, v6) in sorted(results.items(), key=lambda kv: str(kv[0])):
            display_path = path
            if args.relative:
                try:
                    display_path = path.relative_to(root_for_rel)
                except ValueError:
                    # Fallback to absolute if relative is not possible
                    display_path = path
            print(f"File: {display_path}")
            if v4:
                print("  IPv4:")
                for addr in sorted(v4):
                    print(f"    - {addr}")
            if v6:
                print("  IPv6:")
                for addr in sorted(v6):
                    print(f"    - {addr}")
            print()

    print(f"Scanned {total_files} file(s); {files_with_ips} file(s) contained IP addresses.")

    if args.fail_on_found and found_any:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

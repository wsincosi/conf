#!/usr/bin/env python3
"""
find_common_yara_traits.py

Analyze a directory of files and report traits that are common across all or most
samples, with a focus on helping you draft YARA rules.

What it looks for:
- Common file header bytes ("magic bytes")
- Stable byte runs at fixed offsets near the start of the file
- Common suffix bytes near the end of the file
- Candidate YARA hex pattern with wildcards for variable bytes
- Common ASCII and UTF-16LE strings
- Optional libmagic MIME/description clustering if python-magic is installed

Example:
    python find_common_yara_traits.py /path/to/samples --recursive --top-strings 30

    python find_common_yara_traits.py /path/to/samples \
        --recursive \
        --top-strings 30 \
        --min-run 4 \
        --string-presence 1.0 \
        --json-out report.json

Tip:
    Start by running this against a clean set of known-related files. Then use the
    strongest shared traits in a YARA rule and validate them against unrelated files.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import pathlib
import re
import statistics
from typing import Dict, Iterable, List, Sequence

ASCII_PRINTABLE_RE_TEMPLATE = rb"[\x20-\x7e]{%d,}"
UTF16LE_PRINTABLE_RE_TEMPLATE = rb"(?:[\x20-\x7e]\x00){%d,}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find common structural elements in a directory of files to help draft YARA rules."
    )
    parser.add_argument("directory", help="Directory containing sample files")
    parser.add_argument(
        "--recursive", action="store_true", help="Recurse into subdirectories"
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Only analyze the first N files (0 = all)",
    )
    parser.add_argument(
        "--head-bytes",
        type=int,
        default=4096,
        help="How many bytes to read from the start of each file",
    )
    parser.add_argument(
        "--tail-bytes",
        type=int,
        default=1024,
        help="How many bytes to read from the end of each file",
    )
    parser.add_argument(
        "--yara-window",
        type=int,
        default=64,
        help="How many starting bytes to include in the masked YARA hex pattern",
    )
    parser.add_argument(
        "--min-run",
        type=int,
        default=4,
        help="Minimum length for a stable byte run at a fixed offset",
    )
    parser.add_argument(
        "--min-string-len",
        type=int,
        default=6,
        help="Minimum length for extracted strings",
    )
    parser.add_argument(
        "--string-presence",
        type=float,
        default=1.0,
        help="Fraction of files a string must appear in (1.0 = all files)",
    )
    parser.add_argument(
        "--top-strings", type=int, default=25, help="How many common strings to print"
    )
    parser.add_argument(
        "--json-out", help="Optional path to write the full report as JSON"
    )
    return parser.parse_args()


def iter_files(directory: str, recursive: bool) -> Iterable[pathlib.Path]:
    root = pathlib.Path(directory)
    if recursive:
        for path in root.rglob("*"):
            if path.is_file():
                yield path
    else:
        for path in root.iterdir():
            if path.is_file():
                yield path


def safe_read_head_tail(
    path: pathlib.Path, head_bytes: int, tail_bytes: int
) -> tuple[bytes, bytes, int]:
    size = path.stat().st_size
    with path.open("rb") as f:
        head = f.read(head_bytes)
        if size <= tail_bytes:
            tail = head if len(head) == size else head + f.read()
        else:
            f.seek(max(size - tail_bytes, 0))
            tail = f.read(tail_bytes)
    return head, tail, size


def extract_strings(path: pathlib.Path, min_len: int) -> set[str]:
    ascii_re = re.compile(ASCII_PRINTABLE_RE_TEMPLATE % min_len)
    utf16_re = re.compile(UTF16LE_PRINTABLE_RE_TEMPLATE % min_len)
    found: set[str] = set()

    with path.open("rb") as f:
        data = f.read()

    for match in ascii_re.finditer(data):
        try:
            s = match.group().decode("ascii", errors="ignore").strip()
            if s:
                found.add(s)
        except Exception:
            pass

    for match in utf16_re.finditer(data):
        try:
            raw = match.group()
            s = raw.decode("utf-16le", errors="ignore").strip()
            if s:
                found.add(s)
        except Exception:
            pass

    return found


def common_prefix(chunks: Sequence[bytes]) -> bytes:
    if not chunks:
        return b""
    limit = min(len(c) for c in chunks)
    out = bytearray()
    for i in range(limit):
        b0 = chunks[0][i]
        if all(chunk[i] == b0 for chunk in chunks[1:]):
            out.append(b0)
        else:
            break
    return bytes(out)


def common_suffix(chunks: Sequence[bytes]) -> bytes:
    if not chunks:
        return b""
    limit = min(len(c) for c in chunks)
    out = bytearray()
    for i in range(1, limit + 1):
        b0 = chunks[0][-i]
        if all(chunk[-i] == b0 for chunk in chunks[1:]):
            out.append(b0)
        else:
            break
    out.reverse()
    return bytes(out)


def stable_runs_at_fixed_offsets(chunks: Sequence[bytes], min_run: int) -> list[dict]:
    if not chunks:
        return []
    limit = min(len(c) for c in chunks)
    runs = []
    current = bytearray()
    start = None

    def flush():
        nonlocal current, start, runs
        if start is not None and len(current) >= min_run:
            runs.append(
                {
                    "offset": start,
                    "length": len(current),
                    "hex": bytes(current).hex(" ").upper(),
                    "ascii": printable_preview(bytes(current)),
                }
            )
        current = bytearray()
        start = None

    for i in range(limit):
        values = {chunk[i] for chunk in chunks}
        if len(values) == 1:
            if start is None:
                start = i
            current.append(next(iter(values)))
        else:
            flush()

    flush()
    return runs


def stable_runs_from_end(chunks: Sequence[bytes], min_run: int) -> list[dict]:
    if not chunks:
        return []
    limit = min(len(c) for c in chunks)
    reversed_runs = []
    current = bytearray()
    start_from_end = None

    def flush():
        nonlocal current, start_from_end, reversed_runs
        if start_from_end is not None and len(current) >= min_run:
            data = bytes(reversed(current))
            reversed_runs.append(
                {
                    "offset_from_end": start_from_end,
                    "length": len(data),
                    "hex": data.hex(" ").upper(),
                    "ascii": printable_preview(data),
                }
            )
        current = bytearray()
        start_from_end = None

    for i in range(1, limit + 1):
        values = {chunk[-i] for chunk in chunks}
        if len(values) == 1:
            if start_from_end is None:
                start_from_end = i - 1
            current.append(next(iter(values)))
        else:
            flush()

    flush()
    return reversed_runs


def yara_mask_from_heads(chunks: Sequence[bytes], window: int) -> str:
    if not chunks:
        return ""
    limit = min(window, min(len(c) for c in chunks))
    tokens: list[str] = []
    wildcard_run = 0

    def flush_wildcards():
        nonlocal wildcard_run, tokens
        if wildcard_run == 0:
            return
        if wildcard_run <= 2:
            tokens.extend(["??"] * wildcard_run)
        else:
            tokens.append(f"[{wildcard_run}]")
        wildcard_run = 0

    for i in range(limit):
        values = {chunk[i] for chunk in chunks}
        if len(values) == 1:
            flush_wildcards()
            tokens.append(f"{next(iter(values)):02X}")
        else:
            wildcard_run += 1

    flush_wildcards()
    return "{ " + " ".join(tokens) + " }"


def printable_preview(data: bytes, max_len: int = 64) -> str:
    out = []
    for b in data[:max_len]:
        if 32 <= b <= 126:
            out.append(chr(b))
        else:
            out.append(".")
    s = "".join(out)
    if len(data) > max_len:
        s += "..."
    return s


def top_items(counter: collections.Counter, top_n: int) -> list[dict]:
    items = []
    for value, count in counter.most_common(top_n):
        items.append({"value": value, "count": count})
    return items


def try_magic_descriptions(paths: Sequence[pathlib.Path]) -> collections.Counter:
    counter: collections.Counter = collections.Counter()
    try:
        import magic  # type: ignore
    except Exception:
        return counter

    try:
        magic_desc = magic.Magic(mime=False)
    except Exception:
        return counter

    for path in paths:
        try:
            desc = magic_desc.from_file(str(path))
            if desc:
                counter[desc] += 1
        except Exception:
            pass
    return counter


def try_magic_mime(paths: Sequence[pathlib.Path]) -> collections.Counter:
    counter: collections.Counter = collections.Counter()
    try:
        import magic  # type: ignore
    except Exception:
        return counter

    try:
        magic_mime = magic.Magic(mime=True)
    except Exception:
        return counter

    for path in paths:
        try:
            mime = magic_mime.from_file(str(path))
            if mime:
                counter[mime] += 1
        except Exception:
            pass
    return counter


def build_report(paths: Sequence[pathlib.Path], args: argparse.Namespace) -> dict:
    heads: list[bytes] = []
    tails: list[bytes] = []
    sizes: list[int] = []
    string_counter: collections.Counter = collections.Counter()
    ext_counter: collections.Counter = collections.Counter()

    for path in paths:
        head, tail, size = safe_read_head_tail(path, args.head_bytes, args.tail_bytes)
        heads.append(head)
        tails.append(tail)
        sizes.append(size)
        ext_counter[path.suffix.lower() or "<no extension>"] += 1

        strings = extract_strings(path, args.min_string_len)
        for s in strings:
            string_counter[s] += 1

    num_files = len(paths)
    threshold = max(1, math.ceil(num_files * args.string_presence))
    common_strings = [
        {"string": s, "count": c}
        for s, c in sorted(
            ((s, c) for s, c in string_counter.items() if c >= threshold),
            key=lambda item: (-item[1], -len(item[0]), item[0]),
        )[: args.top_strings]
    ]

    report = {
        "file_count": num_files,
        "files": [str(p) for p in paths],
        "extensions": top_items(ext_counter, 20),
        "size_stats": {
            "min": min(sizes) if sizes else 0,
            "max": max(sizes) if sizes else 0,
            "mean": round(statistics.mean(sizes), 2) if sizes else 0,
            "median": int(statistics.median(sizes)) if sizes else 0,
        },
        "common_header_prefix": {
            "length": len(common_prefix(heads)),
            "hex": common_prefix(heads).hex(" ").upper(),
            "ascii": printable_preview(common_prefix(heads)),
        },
        "common_footer_suffix": {
            "length": len(common_suffix(tails)),
            "hex": common_suffix(tails).hex(" ").upper(),
            "ascii": printable_preview(common_suffix(tails)),
        },
        "stable_header_runs": stable_runs_at_fixed_offsets(heads, args.min_run),
        "stable_footer_runs": stable_runs_from_end(tails, args.min_run),
        "candidate_yara_header_hex": yara_mask_from_heads(heads, args.yara_window),
        "common_strings": common_strings,
        "libmagic_mime_top": top_items(try_magic_mime(paths), 10),
        "libmagic_description_top": top_items(try_magic_descriptions(paths), 10),
        "notes": [
            "Stable header runs are byte sequences that appear at the same offset in every analyzed file.",
            "The candidate YARA header hex pattern is masked with ?? or [N] where bytes vary.",
            "Common strings are counted once per file, not per occurrence.",
            "A strong YARA rule usually combines multiple traits: magic bytes, a few stable strings, and size/offset conditions.",
        ],
    }
    return report


def print_report(report: dict, args: argparse.Namespace) -> None:
    print("=" * 80)
    print("Common traits report for YARA drafting")
    print("=" * 80)
    print(f"Files analyzed       : {report['file_count']}")
    print(
        f"Size min/median/max  : {report['size_stats']['min']} / {report['size_stats']['median']} / {report['size_stats']['max']}"
    )
    print(f"Size mean            : {report['size_stats']['mean']}")
    print()

    print("Top extensions:")
    for item in report["extensions"]:
        print(f"  - {item['value']}: {item['count']}")
    print()

    header = report["common_header_prefix"]
    print(f"Common header prefix ({header['length']} bytes):")
    print(f"  HEX   : {header['hex'] or '<none>'}")
    print(f"  ASCII : {header['ascii'] or '<none>'}")
    print()

    footer = report["common_footer_suffix"]
    print(f"Common footer suffix ({footer['length']} bytes):")
    print(f"  HEX   : {footer['hex'] or '<none>'}")
    print(f"  ASCII : {footer['ascii'] or '<none>'}")
    print()

    print("Stable header runs at fixed offsets:")
    if report["stable_header_runs"]:
        for run in report["stable_header_runs"]:
            print(
                f"  - offset 0x{run['offset']:X} ({run['offset']}), len {run['length']}: {run['hex']}    ASCII: {run['ascii']}"
            )
    else:
        print("  <none found>")
    print()

    print("Stable footer runs from end:")
    if report["stable_footer_runs"]:
        for run in report["stable_footer_runs"]:
            print(
                f"  - from end -0x{run['offset_from_end']:X} (-{run['offset_from_end']}), len {run['length']}: "
                f"{run['hex']}    ASCII: {run['ascii']}"
            )
    else:
        print("  <none found>")
    print()

    print("Candidate masked YARA header pattern:")
    print(f"  {report['candidate_yara_header_hex'] or '<none>'}")
    print()

    presence_pct = int(args.string_presence * 100)
    print(f"Common strings (present in at least {presence_pct}% of files):")
    if report["common_strings"]:
        for item in report["common_strings"]:
            s = item["string"]
            if len(s) > 120:
                s = s[:117] + "..."
            print(f"  - [{item['count']} files] {s}")
    else:
        print("  <none found>")
    print()

    if report["libmagic_mime_top"] or report["libmagic_description_top"]:
        print("libmagic guesses:")
        for item in report["libmagic_mime_top"]:
            print(f"  MIME        - {item['value']}: {item['count']}")
        for item in report["libmagic_description_top"]:
            print(f"  Description - {item['value']}: {item['count']}")
        print()
    else:
        print("libmagic guesses:")
        print("  python-magic not installed, or file type detection unavailable.")
        print()

    print("How to use this for YARA:")
    print(
        "  1. Prefer the stable header runs and common strings with high specificity."
    )
    print("  2. Avoid traits that are common to many unrelated file formats.")
    print("  3. Combine several weak traits rather than trusting one weak string.")
    print("  4. Validate your rule against both positive and negative sample sets.")
    print()


def main() -> int:
    args = parse_args()

    root = pathlib.Path(args.directory)
    if not root.exists() or not root.is_dir():
        print(f"[!] Not a directory: {root}")
        return 2

    paths = sorted(iter_files(str(root), args.recursive))
    if args.max_files > 0:
        paths = paths[: args.max_files]

    if not paths:
        print("[!] No files found.")
        return 1

    report = build_report(paths, args)
    print_report(report, args)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"[+] Wrote JSON report to: {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

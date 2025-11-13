#!/usr/bin/env python3
"""
generate_testdata.py
Creates a directory named `ip_testdata` filled with files
containing various IP address patterns for testing scan_ips.py.
"""

import os
from pathlib import Path
import random

ROOT = Path("ip_testdata")

IPV4_SAMPLES = [
    "192.168.1.1",
    "10.0.0.254",
    "172.16.5.123",
    "8.8.8.8",
    "255.255.255.255",
]

IPV6_SAMPLES = [
    "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
    "2001:db8::1",
    "fe80::f2de:f1ff:fe3f:307e",
    "::1",
]

TEXT_FILES = {
    "readme.txt": [
        "This is a test file.\n",
        "It contains an IPv4 address: 192.168.1.1\n",
        "And here is an IPv6 address: 2001:db8::1\n",
    ],
    "config.cfg": [
        "server_ip=10.0.0.254\n",
        "backup_server=fe80::f2de:f1ff:fe3f:307e\n",
    ],
    "notes.md": [
        "Random text without IPs.\n",
        "Just to check behavior on clean files.\n",
    ],
    "weird.bin": None,  # Will contain binary garbage + an IP
    "script.py": [
        "# Sample script\n",
        "API_URL = 'http://8.8.8.8/api'\n",
    ],
}

def make_random_binary_with_ip(ip: str, size: int = 200) -> bytes:
    """Return random bytes with an embedded IP address."""
    data = bytearray(os.urandom(size))
    insert_at = random.randint(10, size - len(ip) - 1)
    data[insert_at:insert_at+len(ip)] = ip.encode()
    return bytes(data)

def maybe_create_pcap(path: Path):
    """
    Create a tiny pcap file if scapy is installed.
    This is optional; skip silently otherwise.
    """
    try:
        from scapy.all import IP, IPv6, Ether, wrpcap  # type: ignore
    except Exception:
        print("Scapy not found: skipping pcap generation.")
        return

    pkt1 = Ether() / IP(src="192.168.1.1", dst="8.8.8.8")
    pkt2 = Ether() / IPv6(src="2001:db8::1", dst="fe80::1")
    wrpcap(str(path), [pkt1, pkt2])
    print(f"Created pcap file: {path}")

def main():
    if ROOT.exists():
        print(f"Removing old directory: {ROOT}")
        for p in sorted(ROOT.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()

    print(f"Creating directory: {ROOT}")
    ROOT.mkdir(exist_ok=True)

    # Create hidden irrelevant directory
    hidden = ROOT / ".git"
    hidden.mkdir()

    # Create normal test files
    for filename, content in TEXT_FILES.items():
        path = ROOT / filename

        if content is None:
            # binary file + IP inserted inside
            test_ip = random.choice(IPV4_SAMPLES)
            print(f"Creating binary file {path} with IP {test_ip}")
            data = make_random_binary_with_ip(test_ip)
            path.write_bytes(data)
        else:
            print(f"Creating text file {path}")
            path.write_text("".join(content))

    # Add a nested directory
    nested = ROOT / "subfolder"
    nested.mkdir()
    (nested / "more_ips.txt").write_text(
        f"Nested IPv4: {IPV4_SAMPLES[2]}\nNested IPv6: {IPV6_SAMPLES[3]}\n"
    )

    # Optional: create a small PCAP
    maybe_create_pcap(ROOT / "traffic.pcap")

    print("\nFinished generating test data!")
    print(f"You can now run:  python scan_ips.py {ROOT}")

if __name__ == "__main__":
    main()

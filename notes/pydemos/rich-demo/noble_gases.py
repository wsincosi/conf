 # noble_gases.py

from rich.console import Console
from rich.table import Table

console = Console()
table = Table(title="Noble Gases")

table.add_column("Name", style="cyan", justify="center")

table.add_column("Symbol", style="magenta", justify="center")
table.add_column("Atomic Number", style="yellow", justify="right")
table.add_column("Atomic Mass", style="green", justify="right")
table.add_column("Main Properties", style="blue", justify="center")

noble_gases = [
    {"name": "Helium", "symbol": "He", "atomic_number": 2,
     "atomic_mass": 4.0026, "properties": "Inert gas"},
    {"name": "Neon", "symbol": "Ne", "atomic_number": 10,
     "atomic_mass": 20.1797, "properties": "Inert gas"},
    {"name": "Argon", "symbol": "Ar", "atomic_number": 18,
     "atomic_mass": 39.948, "properties": "Inert gas"},
    {"name": "Krypton", "symbol": "Kr", "atomic_number": 36,
     "atomic_mass": 83.798, "properties": "Inert gas"},
    {"name": "Xenon", "symbol": "Xe", "atomic_number": 54,
     "atomic_mass": 131.293, "properties": "Inert gas"},
    {"name": "Radon", "symbol": "Rn", "atomic_number": 86,
     "atomic_mass": 222.0, "properties": "Radioactive gas"},
    {"name": "Oganesson", "symbol": "Og", "atomic_number": 118,
     "atomic_mass": "(294)", "properties": "Synthetic radioactive gas"},
]

for noble_gas in noble_gases:
    table.add_row(
        noble_gas["name"],
        noble_gas["symbol"],
        str(noble_gas["atomic_number"]),
        str(noble_gas["atomic_mass"]),
        noble_gas["properties"],
    )

console.print(table)

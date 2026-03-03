# Enea Outages Python Library

A simple Python library to get information about power outages from the Enea Operator website.

## Installation

```bash
pip install enea-outages
```

---

## Usage (Python)

```python
from enea_outages.client import EneaOutagesClient
from enea_outages.models import OutageType

client = EneaOutagesClient()

# List available branches (oddziały)
branches = client.get_available_branches()
print(f"Available branches: {branches}")

# List distribution areas (rejony) for a branch
areas = client.get_available_distribution_areas("Szczecin")
for area_id, area_name in areas:
    print(f"  {area_id}: {area_name}")

# All planned outages for a branch
planned = client.get_outages_for_branch("Poznań", outage_type=OutageType.PLANNED)
print(f"Found {len(planned)} planned outages.")

# Outages narrowed to a distribution area (by ID or name)
outages = client.get_outages_for_branch(
    branch="Szczecin",
    outage_type=OutageType.UNPLANNED,
    distribution_area="23",           # numeric ID
)

outages = client.get_outages_for_branch(
    branch="Szczecin",
    outage_type=OutageType.UNPLANNED,
    distribution_area="Szczecin",  # or human-readable name
)

# Free-text search by city, street, or both
outages = client.get_outages_for_query(
    query="Nowogard Bohaterów Warszawy",
    branch="Szczecin",
    outage_type=OutageType.PLANNED,
    distribution_area="Goleniów",
)

if outages:
    o = outages[0]
    print(f"Area: {o.region}")
    print(f"Description: {o.description}")
    print(f"Start: {o.start_time}  End: {o.end_time}")
```

### Query matching

`get_outages_for_query()` performs client-side matching against the outage description. The description is a free-form string listing towns and streets, e.g.:

```
Kołczewo ul. Zwycięstwa 33, 34, 35, 36, 37, Domysłów 6
```

Every token in the query must appear somewhere in the description — order and punctuation are ignored, noise words (`ul`, `nr`, `al`, etc.) are stripped from both sides. Prefix matching is used, so partial words also match.

| Query | Matches |
|---|---|
| `"Kołczewo"` | ✓ |
| `"Zwycięstwa 37"` | ✓ |
| `"Kołczewo, Zwycięstwa 37"` | ✓ |
| `"Zwycięstwa Kołczewo"` | ✓ (order-independent) |
| `"Szczecin"` | ✗ |

---

## Usage (CLI)

```bash
# List all available branches
enea-outages --list-branches

# List distribution areas for a branch
enea-outages --branch "Szczecin" --list-distribution-areas

# All unplanned outages for a branch
enea-outages --branch "Poznań" --type unplanned

# Narrow to a distribution area (ID or name, case-insensitive)
enea-outages --branch "Szczecin" --distribution-area "23"
enea-outages --branch "Szczecin" --distribution-area "Szczecin"
enea-outages --branch "Szczecin" --distribution-area "szczecin"

# Free-text search by city and/or street
enea-outages --branch "Szczecin" --query "Nowogard Bohaterów Warszawy"

# Combine filters
enea-outages --branch "Szczecin" --type planned \
  --distribution-area "Goleniów" \
  --query "Kołczewo, Zwycięstwa"
```

---

## Branches and Distribution Areas

Below is a reference of all available branches (oddziały) and their distribution areas (rejony dystrybucji) with numeric IDs used by the Enea Operator website.

### Zielona Góra

| ID | Name |
|----|------|
| 1 | Zielona Góra |
| 2 | Żary |
| 3 | Wolsztyn |
| 4 | Świebodzin |
| 5 | Nowa Sól |
| 6 | Krosno Odrzańskie |

### Poznań

| ID | Name |
|----|------|
| 7 | Poznań |
| 8 | Wałcz |
| 9 | Września |
| 10 | Szamotuły |
| 11 | Piła |
| 12 | Opalenica |
| 13 | Leszno |
| 15 | Gniezno |
| 16 | Chodzież |

### Bydgoszcz

| ID | Name |
|----|------|
| 17 | Bydgoszcz |
| 18 | Świecie |
| 19 | Nakło |
| 20 | Mogilno |
| 21 | Inowrocław |
| 22 | Chojnice |

### Szczecin

| ID | Name |
|----|------|
| 23 | Szczecin |
| 24 | Stargard |
| 25 | Międzyzdroje |
| 26 | Gryfice |
| 27 | Goleniów |

### Gorzów Wlkp.

| ID | Name |
|----|------|
| 28 | Gorzów Wlkp. |
| 29 | Sulęcin |
| 30 | Międzychód |
| 31 | Dębno |
| 32 | Choszczno |

> **Note:** The exact names returned by `get_available_distribution_areas()` may differ slightly from those listed above. Use `--list-distribution-areas` or call `get_available_distribution_areas()` to get the current names as returned by the website — those are the values accepted by `--distribution-area` and `resolve_distribution_area_id()`.

---

*This project was developed with the assistance of AI tools. While the code has been reviewed, please use it with standard caution.*
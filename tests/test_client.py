import pytest
from datetime import datetime
from bs4 import BeautifulSoup
import httpx
from pytest_httpx import HTTPXMock

from enea_outages.client import EneaOutagesClient
from enea_outages.models import OutageType

# --- Test Data ---

SAMPLE_UNPLANNED_BLOCK = """
<div class="unpl block info">
    <h4 class="title_">Test Unplanned Area</h4>
    <p class="bold subtext">
        29 listopada 2025 r.  do godziny 14:30
    </p>
    <p class="description">Unplanned outage description.</p>
</div>
"""

SAMPLE_PLANNED_BLOCK = """
<div class="unpl block info">
    <h4 class="title_">Test Planned Area</h4>
    <p class="bold subtext">
        8 grudnia 2025 r. w godz. 08:00 - 16:00
    </p>
    <p class="description">Planned outage description.</p>
</div>
"""

SAMPLE_QUERY_BLOCK = """
<div class="unpl block info">
    <h4 class="title_">Obszar Wolin</h4>
    <p class="bold subtext">
        6 marca 2026 r. w godz. 11:30 - 16:00
    </p>
    <p class="description">Kołczewo ul. Zwycięstwa 33, 34, 35, 36, 37, Domysłów 6</p>
</div>
"""

SAMPLE_HTML_PAGE_WITH_BRANCHES = """
<html>
    <body>
        <select id="oddzial" name="oddzial">
            <option value="">wybierz oddział</option>
            <option value="Zielona Góra">Oddział Zielona Góra</option>
            <option value="Poznań" selected="selected">Oddział Poznań</option>
        </select>
    </body>
</html>
"""

SAMPLE_HTML_PAGE_WITH_DISTRIBUTION_AREAS = """
<html>
    <body>
        <select id="rejon" name="rejon">
            <option value="">wybierz rejon</option>
            <option value="101">Rejon Wolin</option>
            <option value="102">Rejon Szczecin</option>
        </select>
    </body>
</html>
"""

BASE = EneaOutagesClient.BASE_URL


def url(page: str, branch: str = "Poznań", distribution_area: str = "") -> str:
    """Helper to build expected request URLs."""
    from urllib.parse import quote
    u = f"{BASE}?page={page}&oddzial={quote(branch)}"
    if distribution_area:
        u += f"&rejon={distribution_area}"
    return u


# --- Fixtures ---


@pytest.fixture
def client():
    return EneaOutagesClient()


# --- Date Parsing Tests ---


def test_parse_planned_date_format(client: EneaOutagesClient):
    start, end = client._parse_date_formats("8 grudnia 2025 r. w godz. 08:00 - 16:00")
    assert start == datetime(2025, 12, 8, 8, 0)
    assert end == datetime(2025, 12, 8, 16, 0)


def test_parse_unplanned_date_format(client: EneaOutagesClient):
    start, end = client._parse_date_formats("29 listopada 2025 r. do godziny 14:30")
    assert start is None
    assert end == datetime(2025, 11, 29, 14, 30)


def test_parse_invalid_date_format(client: EneaOutagesClient):
    with pytest.raises(ValueError, match="Could not parse date information"):
        client._parse_date_formats("Invalid date string")


# --- Block Parsing Tests ---


def test_parse_outage_block_planned(client: EneaOutagesClient):
    soup = BeautifulSoup(SAMPLE_PLANNED_BLOCK, "html.parser")
    outage = client._parse_outage_block(soup.find("div"))
    assert outage.region == "Test Planned Area"
    assert outage.start_time == datetime(2025, 12, 8, 8, 0)
    assert outage.end_time == datetime(2025, 12, 8, 16, 0)


def test_parse_outage_block_unplanned(client: EneaOutagesClient):
    soup = BeautifulSoup(SAMPLE_UNPLANNED_BLOCK, "html.parser")
    outage = client._parse_outage_block(soup.find("div"))
    assert outage.region == "Test Unplanned Area"
    assert outage.start_time is None
    assert outage.end_time == datetime(2025, 11, 29, 14, 30)


# --- get_available_branches ---


def test_get_available_branches(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(text=SAMPLE_HTML_PAGE_WITH_BRANCHES)
    branches = client.get_available_branches()
    assert branches == ["Zielona Góra", "Poznań"]


# --- get_available_distribution_areas ---


def test_get_available_distribution_areas(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(text=SAMPLE_HTML_PAGE_WITH_DISTRIBUTION_AREAS)
    areas = client.get_available_distribution_areas("Poznań")
    assert areas == [("101", "Rejon Wolin"), ("102", "Rejon Szczecin")]


def test_get_available_distribution_areas_empty(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(text="<html><body></body></html>")
    areas = client.get_available_distribution_areas("Poznań")
    assert areas == []


# --- get_outages_for_branch ---


def test_get_outages_for_branch_unplanned(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.UNPLANNED.value),
        text=f"<html><body>{SAMPLE_UNPLANNED_BLOCK}</body></html>",
    )
    outages = client.get_outages_for_branch("Poznań", OutageType.UNPLANNED)
    assert len(outages) == 1
    assert outages[0].region == "Test Unplanned Area"
    assert outages[0].start_time is None
    assert outages[0].end_time == datetime(2025, 11, 29, 14, 30)


def test_get_outages_for_branch_planned(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.PLANNED.value),
        text=f"<html><body>{SAMPLE_PLANNED_BLOCK}</body></html>",
    )
    outages = client.get_outages_for_branch("Poznań", OutageType.PLANNED)
    assert len(outages) == 1
    assert outages[0].region == "Test Planned Area"
    assert outages[0].start_time == datetime(2025, 12, 8, 8, 0)
    assert outages[0].end_time == datetime(2025, 12, 8, 16, 0)


def test_get_outages_for_branch_with_distribution_area(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.UNPLANNED.value, distribution_area="101"),
        text=f"<html><body>{SAMPLE_UNPLANNED_BLOCK}</body></html>",
    )
    outages = client.get_outages_for_branch("Poznań", OutageType.UNPLANNED, distribution_area="101")
    assert len(outages) == 1


def test_get_outages_for_branch_empty(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.UNPLANNED.value),
        text="<html><body></body></html>",
    )
    outages = client.get_outages_for_branch("Poznań", OutageType.UNPLANNED)
    assert outages == []


# --- get_outages_for_query ---


def test_get_outages_for_query_city_only(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.PLANNED.value),
        text=f"<html><body>{SAMPLE_QUERY_BLOCK}</body></html>",
    )
    outages = client.get_outages_for_query("Kołczewo", "Poznań", OutageType.PLANNED)
    assert len(outages) == 1


def test_get_outages_for_query_street_only(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.PLANNED.value),
        text=f"<html><body>{SAMPLE_QUERY_BLOCK}</body></html>",
    )
    outages = client.get_outages_for_query("Zwycięstwa 37", "Poznań", OutageType.PLANNED)
    assert len(outages) == 1


def test_get_outages_for_query_city_and_street_with_comma(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.PLANNED.value),
        text=f"<html><body>{SAMPLE_QUERY_BLOCK}</body></html>",
    )
    outages = client.get_outages_for_query("Kołczewo, Zwycięstwa 37", "Poznań", OutageType.PLANNED)
    assert len(outages) == 1


def test_get_outages_for_query_reversed_phrase_order(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.PLANNED.value),
        text=f"<html><body>{SAMPLE_QUERY_BLOCK}</body></html>",
    )
    outages = client.get_outages_for_query("Zwycięstwa 37, Kołczewo", "Poznań", OutageType.PLANNED)
    assert len(outages) == 1


def test_get_outages_for_query_no_match(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.PLANNED.value),
        text=f"<html><body>{SAMPLE_QUERY_BLOCK}</body></html>",
    )
    outages = client.get_outages_for_query("Szczecin Bohaterów", "Poznań", OutageType.PLANNED)
    assert outages == []


def test_get_outages_for_query_with_distribution_area(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.PLANNED.value, distribution_area="101"),
        text=f"<html><body>{SAMPLE_QUERY_BLOCK}</body></html>",
    )
    outages = client.get_outages_for_query(
        "Kołczewo", "Poznań", OutageType.PLANNED, distribution_area="101"
    )
    assert len(outages) == 1


# --- get_outages_for_address (backwards compat alias) ---


def test_get_outages_for_address_match(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.UNPLANNED.value),
        text=f"<html><body>{SAMPLE_UNPLANNED_BLOCK}</body></html>",
    )
    outages = client.get_outages_for_address("Unplanned outage", "Poznań", OutageType.UNPLANNED)
    assert len(outages) == 1


def test_get_outages_for_address_no_match(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=url(OutageType.UNPLANNED.value),
        text=f"<html><body>{SAMPLE_UNPLANNED_BLOCK}</body></html>",
    )
    outages = client.get_outages_for_address("NonExistent Street", "Poznań", OutageType.UNPLANNED)
    assert outages == []


# --- Query Matching Unit Tests (no HTTP) ---


@pytest.mark.parametrize("query,expected", [
    ("Kołczewo", True),
    ("Zwycięstwa", True),
    ("Zwycięstwa 37", True),
    ("Kołczewo, Zwycięstwa 37", True),
    ("Zwycięstwa 37, Kołczewo", True),
    ("Zwycięstwa Kołczewo", True),
    ("Domysłów 6", True),
    ("Szczecin", False),
    ("Bohaterów Warszawy", False),
    ("Kołczewo, Bohaterów", False),
])
def test_description_matches_query(query: str, expected: bool):
    description = "Kołczewo ul. Zwycięstwa 33, 34, 35, 36, 37, Domysłów 6"
    result = EneaOutagesClient._description_matches_query(description, query)
    assert result == expected, f"query={query!r} expected={expected} got={result}"


# --- HTTP Error ---


def test_http_error(client: EneaOutagesClient, httpx_mock: HTTPXMock):
    httpx_mock.add_response(status_code=500)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_outages_for_branch("Poznań")
from __future__ import annotations

import re
from datetime import datetime
from typing import Tuple

import httpx
from bs4 import BeautifulSoup

from .models import Outage, OutageType


class EneaOutagesClient:
    """Synchronous client for Enea Operator power outages."""

    BASE_URL = "https://wylaczenia-eneaoperator.pl/index.php"
    MONTH_MAP = {
        "stycznia": 1,
        "lutego": 2,
        "marca": 3,
        "kwietnia": 4,
        "maja": 5,
        "czerwca": 6,
        "lipca": 7,
        "sierpnia": 8,
        "września": 9,
        "października": 10,
        "listopada": 11,
        "grudnia": 12,
    }

    def _parse_date_formats(self, date_info: str) -> Tuple[datetime | None, datetime | None]:
        """
        Parses different date formats and returns a tuple of (start_time, end_time).
        """
        # Planned outage format: "8 grudnia 2025 r. w godz. 08:00 - 16:00"
        planned_match = re.search(
            r"(\d{1,2})\s+(\w+)\s+(\d{4})\s+r\.\s+w\s+godz\.\s+(\d{1,2}):(\d{2})\s+-\s+(\d{1,2}):(\d{2})", date_info
        )
        if planned_match:
            day, month_name, year, start_hour, start_min, end_hour, end_min = planned_match.groups()
            month = self.MONTH_MAP.get(month_name.lower())
            if not month:
                raise ValueError(f"Unknown month name: {month_name}")

            start_time = datetime(int(year), month, int(day), int(start_hour), int(start_min))
            end_time = datetime(int(year), month, int(day), int(end_hour), int(end_min))
            return start_time, end_time

        # Unplanned outage format: "19 listopada 2025 r. do godziny 12:30"
        unplanned_match = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})\s+r\.\s+do\s+godziny\s+(\d{1,2}):(\d{2})", date_info)
        if unplanned_match:
            day, month_name, year, hour, minute = unplanned_match.groups()
            month = self.MONTH_MAP.get(month_name.lower())
            if not month:
                raise ValueError(f"Unknown month name: {month_name}")

            # For unplanned, we only have an end time. Start time is unknown.
            end_time = datetime(int(year), month, int(day), int(hour), int(minute))
            return None, end_time

        raise ValueError(f"Could not parse date information: {date_info}")

    def _parse_outage_block(self, block: BeautifulSoup) -> Outage:
        """Parses a single outage HTML block into an Outage object."""
        # Remove noise spans (e.g. <span class="dzisiaj alert ">dzisiaj</span>)
        for span in block.find_all("span", {"class": "dzisiaj"}):
            span.decompose()

        region_tag = block.find("h4", {"class": "title_"})
        description_tag = block.find("p", {"class": "description"})
        date_info_tag = block.find("p", {"class": "bold subtext"})

        region = region_tag.get_text(separator=" ", strip=True) if region_tag else "Nieznany obszar"
        description = description_tag.get_text(separator=" ", strip=True) if description_tag else "Brak opisu"
        date_info_str = date_info_tag.get_text(separator=" ", strip=True) if date_info_tag else ""

        start_time, end_time = self._parse_date_formats(date_info_str)

        return Outage(region=region, description=description, start_time=start_time, end_time=end_time)

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercases and collapses whitespace for comparison."""
        return re.sub(r"\s+", " ", text.lower().strip())

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """
        Splits text into lowercase alphanumeric tokens, stripping punctuation.
        Treats commas, spaces, and noise words ('ul', 'nr', 'al') as separators.

        Example:
            "Kołczewo ul. Zwycięstwa nr 37, 38a" → ["kołczewo", "zwycięstwa", "37", "38a"]
        """
        NOISE = {"ul", "nr", "al", "os", "pl", "dr", "św"}
        tokens = re.split(r"[^\w]+", text.lower())
        return [t for t in tokens if t and t not in NOISE]

    @staticmethod
    def _description_matches_query(description: str, query: str) -> bool:
        """
        Checks whether an outage description matches a free-text query.

        The description is a comma/space-separated string that may contain multiple
        towns, streets and house numbers, e.g.:
            "Kołczewo ul. Zwycięstwa 33, 34, 35, 36, 37, Domysłów 6"

        The query can be any combination of city / street / house number.
        All separators (spaces, commas, punctuation) are treated equally —
        every token in the query must appear somewhere in the description,
        regardless of order:
            "Kołczewo"                 → True
            "Zwycięstwa 37"            → True
            "Kołczewo, Zwycięstwa 37"  → True
            "Zwycięstwa Kołczewo"      → True  (order does not matter)
            "Szczecin"                 → False

        Matching uses prefix comparison so "Zwycięst" matches "Zwycięstwa".
        Noise words ("ul", "nr", "al", etc.) are ignored on both sides.
        """
        norm_desc = EneaOutagesClient._normalize(description)
        norm_query = EneaOutagesClient._normalize(query)

        # Fast path: exact substring match
        if norm_query in norm_desc:
            return True

        desc_tokens = EneaOutagesClient._tokenize(norm_desc)
        query_tokens = EneaOutagesClient._tokenize(norm_query)

        if not query_tokens:
            return False

        # Every query token must be found somewhere in the description tokens.
        # Prefix match so partial words still hit ("Zwycięst" → "Zwycięstwa").
        return all(
            any(desc_token.startswith(q_token) for desc_token in desc_tokens)
            for q_token in query_tokens
        )

    def _fetch_raw_html(
        self,
        branch: str,
        outage_type: OutageType,
        distribution_area: str = "",
    ) -> str:
        """
        Fetches the raw HTML content for a given branch, outage type and optional filters.

        Args:
            branch: The name of the Enea Operator branch/oddział (e.g., "Poznań").
            outage_type: The type of outage to fetch (PLANNED or UNPLANNED).
            distribution_area: Optional ID of the distribution area (rejon dystrybucji).
        """
        params: dict[str, str] = {"page": outage_type.value, "oddzial": branch}

        if distribution_area:
            params["rejon"] = distribution_area

        response = httpx.get(self.BASE_URL, params=params)
        response.raise_for_status()
        return response.text

    def get_outages_for_branch(
        self,
        branch: str = "Poznań",
        outage_type: OutageType = OutageType.UNPLANNED,
        distribution_area: str = "",
    ) -> list[Outage]:
        """
        Retrieves power outages for a specified branch (oddział) and type.

        Args:
            branch: The name of the Enea Operator branch/oddział (e.g., "Poznań").
            outage_type: The type of outage to fetch (PLANNED or UNPLANNED).
            distribution_area: Optional ID of the distribution area to narrow down results.

        Returns:
            A list of Outage objects.
        """
        html = self._fetch_raw_html(branch, outage_type, distribution_area=distribution_area)
        soup = BeautifulSoup(html, "html.parser")
        outage_blocks = soup.find_all("div", {"class": "unpl block info"})

        outages: list[Outage] = []
        for block in outage_blocks:
            try:
                outages.append(self._parse_outage_block(block))
            except (ValueError, AttributeError) as e:
                print(f"Error parsing outage block: {e}")
        return outages

    def get_outages_for_query(
        self,
        query: str,
        branch: str = "Poznań",
        outage_type: OutageType = OutageType.UNPLANNED,
        distribution_area: str = "",
    ) -> list[Outage]:
        """
        Retrieves power outages whose description matches the given free-text query.

        The query can be a city name, a street name, or a combination of both,
        e.g. "Nowogard", "Bohaterów Warszawy", or "Nowogard Bohaterów Warszawy".
        Matching is done client-side against the outage description using a
        normalised, token-aware algorithm that tolerates noise words such as
        "ul.", "nr", "kolonia" between the queried terms.

        Args:
            query: Free-text search string (city, street, or city + street).
            branch: The name of the Enea Operator branch/oddział.
            outage_type: The type of outage to fetch.
            distribution_area: Optional ID of the distribution area to narrow results.

        Returns:
            A list of Outage objects whose description matches the query.
        """
        all_outages = self.get_outages_for_branch(branch, outage_type, distribution_area=distribution_area)
        return [o for o in all_outages if self._description_matches_query(o.description, query)]

    def get_outages_for_address(
        self,
        address: str,
        branch: str = "Poznań",
        outage_type: OutageType = OutageType.UNPLANNED,
        distribution_area: str = "",
    ) -> list[Outage]:
        """
        Alias for get_outages_for_query() kept for backwards compatibility.

        Args:
            address: Street or address fragment to match in descriptions.
            branch: The name of the Enea Operator branch/oddział.
            outage_type: The type of outage to fetch.
            distribution_area: Optional ID of the distribution area to narrow results.

        Returns:
            A list of Outage objects whose description matches the address.
        """
        return self.get_outages_for_query(address, branch, outage_type, distribution_area)

    def resolve_distribution_area_id(self, branch: str, name_or_id: str) -> str:
        """
        Resolves a distribution area name or ID to a numeric ID.

        If the value is already a numeric ID it is returned as-is after
        validating that it exists for the given branch.  Otherwise the value
        is treated as a name: every word is title-cased before lookup so that
        e.g. "rejon wolin" and "Rejon Wolin" both work.

        Args:
            branch: The branch (oddział) to fetch available areas for.
            name_or_id: Numeric ID or human-readable name of the distribution area.

        Returns:
            The numeric ID string for the distribution area.

        Raises:
            ValueError: If the name or ID is not found among available areas.
        """
        areas = self.get_available_distribution_areas(branch)
        ids = {area_id for area_id, _ in areas}
        names = {area_name: area_id for area_id, area_name in areas}

        # Already a numeric ID — just validate
        if name_or_id.isdigit():
            if name_or_id not in ids:
                available = ", ".join(f"{aid} ({aname})" for aid, aname in areas)
                raise ValueError(
                    f"Distribution area ID '{name_or_id}' not found for branch '{branch}'.\n"
                    f"Available areas: {available}"
                )
            return name_or_id

        # Treat as name — title-case each word before lookup
        normalised_name = name_or_id.title()
        if normalised_name not in names:
            available = ", ".join(f"{aname} ({aid})" for aid, aname in areas)
            raise ValueError(
                f"Distribution area '{normalised_name}' not found for branch '{branch}'.\n"
                f"Available areas: {available}"
            )
        return names[normalised_name]

    def get_available_branches(self) -> list[str]:
        """
        Retrieves the list of available branches (oddziały) from the Enea website.

        Returns:
            A list of available branch names.
        """
        html = self._fetch_raw_html(branch="Poznań", outage_type=OutageType.PLANNED)
        soup = BeautifulSoup(html, "html.parser")

        region_select = soup.find("select", {"id": "oddzial"})
        if not region_select:
            return []

        return [
            option["value"]
            for option in region_select.find_all("option")
            if option.has_attr("value") and option["value"]
        ]

    def get_available_distribution_areas(self, branch: str = "") -> list[tuple[str, str]]:
        """
        Retrieves the list of available distribution areas (rejony dystrybucji)
        for a given branch from the Enea website.

        Args:
            branch: The name of the Enea Operator branch/oddział to fetch areas for.

        Returns:
            A list of tuples (id, name) for each distribution area.
        """
        html = self._fetch_raw_html(branch, outage_type=OutageType.PLANNED)
        soup = BeautifulSoup(html, "html.parser")

        region_select = soup.find("select", {"id": "rejon"})
        if not region_select:
            return []

        return [
            (option["value"], option.get_text(strip=True))
            for option in region_select.find_all("option")
            if option.has_attr("value") and option["value"]
        ]
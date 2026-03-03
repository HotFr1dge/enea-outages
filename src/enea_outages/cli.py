import argparse

from .client import EneaOutagesClient
from .models import OutageType


def run_cli_logic():
    """Main function to handle CLI logic."""
    parser = argparse.ArgumentParser(description="Enea Outages CLI Tool")
    parser.add_argument(
        "--type",
        choices=[t.name.lower() for t in OutageType],
        default=OutageType.UNPLANNED.name.lower(),
        help="Specify the type of outage to fetch. Default is 'unplanned'.",
    )
    parser.add_argument(
        "--branch",
        default="Poznań",
        help="Specify the branch (oddział) to check for outages. Default is 'Poznań'.",
    )
    parser.add_argument(
        "--distribution-area",
        default="",
        metavar="NAME_OR_ID",
        help=(
            "Narrow results to a specific distribution area (rejon dystrybucji). "
            "Accepts either a numeric ID or a name (e.g. 'Rejon Wolin' or 'rejon wolin'). "
            "Use --list-distribution-areas to see available options."
        ),
    )
    parser.add_argument(
        "--query",
        default="",
        help="Free-text search: city name, street name, or both (e.g. 'Nowogard Bohaterów Warszawy').",
    )
    parser.add_argument(
        "--list-branches",
        action="store_true",
        help="List all available branches (oddziały) and exit.",
    )
    parser.add_argument(
        "--list-distribution-areas",
        action="store_true",
        help="List all available distribution areas (rejony dystrybucji) for --branch and exit.",
    )
    args = parser.parse_args()

    outage_type = OutageType[args.type.upper()]
    client = EneaOutagesClient()

    if args.list_branches:
        print("Fetching available branches...")
        try:
            branches = client.get_available_branches()
            if branches:
                print("Available branches:")
                for branch in branches:
                    print(f"  - {branch}")
            else:
                print("Could not retrieve branches.")
        except Exception as e:
            print(f"An error occurred: {e}")
        return

    if args.list_distribution_areas:
        print(f"Fetching available distribution areas for branch: {args.branch}...")
        try:
            areas = client.get_available_distribution_areas(args.branch)
            if areas:
                print("Available distribution areas:")
                for area_id, area_name in areas:
                    print(f"  {area_id}: {area_name}")
            else:
                print("Could not retrieve distribution areas.")
        except Exception as e:
            print(f"An error occurred: {e}")
        return

    # Resolve distribution area name/id → numeric id
    distribution_area_id = ""
    if args.distribution_area:
        try:
            distribution_area_id = client.resolve_distribution_area_id(
                args.branch, args.distribution_area
            )
        except ValueError as e:
            print(f"Error: {e}")
            return

    # Build a human-readable summary of what we're searching for
    search_info = f"branch: {args.branch}"
    if distribution_area_id:
        search_info += f", distribution area: {args.distribution_area} (ID: {distribution_area_id})"
    if args.query:
        search_info += f", query: '{args.query}'"

    print(f"Fetching {args.type} outages — {search_info}...")
    try:
        if args.query:
            outages = client.get_outages_for_query(
                args.query,
                branch=args.branch,
                outage_type=outage_type,
                distribution_area=distribution_area_id,
            )
        else:
            outages = client.get_outages_for_branch(
                branch=args.branch,
                outage_type=outage_type,
                distribution_area=distribution_area_id,
            )

        if not outages:
            print("No outages found for the specified criteria.")
            return

        print(f"\nFound {len(outages)} outage notice(s):")
        for outage in outages:
            print("-" * 40)
            print(f"  Obszar:   {outage.region}")
            print(f"  Opis:     {outage.description}")
            if outage.start_time:
                print(f"  Początek: {outage.start_time.strftime('%Y-%m-%d %H:%M')}")
            if outage.end_time:
                print(f"  Koniec:   {outage.end_time.strftime('%Y-%m-%d %H:%M')}")
        print("-" * 40)

    except Exception as e:
        print(f"An error occurred: {e}")


def main():
    """Main entry point for the CLI."""
    try:
        run_cli_logic()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")


if __name__ == "__main__":
    main()
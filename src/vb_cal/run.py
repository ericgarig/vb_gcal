"""
Create events for upcoming games.

todo:
 - check for events before adding duplicates
 - ensure/add/remove attendees separately since they may be added after event is created
"""

from pathlib import Path

from app_props import AppProps

from gcal import GCal
from vb_scrape import VbScrape


def main():
    # config
    AppProps("", str(Path(__file__).parents[2] / "config/config.yml"))
    scrape = VbScrape()
    gcal = GCal()

    # get schedule for latest team
    team_data = scrape.get_schedule()
    [team_name, schedule] = scrape.parse_schedule(team_data, upcoming_only=True)

    # create/update events
    gcal.authenticate_service()
    existing_events = gcal.get_upcoming_events(duration=gcal.max_offset)
    gcal.add_events(team_name, schedule, existing_events)


if __name__ == "__main__":
    main()

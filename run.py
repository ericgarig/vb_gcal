"""
Create events for upcoming games.

todo:
 - check for events before adding duplicates
 - ensure/add/remove attendees separately since they may be added after event is created
"""

from pathlib import Path

from app_props import AppProps

from gcal import GCal
from user_input import UserInput
from vb_scrape import VbScrape


def main():
    # config
    AppProps("", str(Path(__file__).parents[2] / "config/config.yml"))
    scrape = VbScrape()
    gcal = GCal()

    # get schedule for latest team(s)
    schedule = scrape.get_schedule()
    games = scrape.parse_schedule(upcoming_only=True)

    # confirm settings
    email_groups = UserInput().execute(schedule[0])

    # create/update events
    gcal.authenticate_service()
    existing_events = gcal.get_upcoming_events(duration=gcal.max_offset)
    gcal.add_events(games, existing_events, email_groups)


if __name__ == "__main__":
    main()

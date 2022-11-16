"""
Create events for upcoming games.

todo:
 - check for events before adding duplicates
 - ensure/add/remove attendees separately since they may be added after event is created
"""

from config import Config
from gcal import GCal
from vb_scrape import VbScrape


def main():
    # config
    cnf = Config()
    cnf.read_config("config/config.yml")
    scrape = VbScrape(cnf)
    gcal = GCal(cnf)

    # get schedule for latest team
    team_data = scrape.get_schedule()
    [team_name, schedule] = scrape.parse_schedule(team_data, upcoming_only=True)

    # create/update events
    gcal.authenticate_service()
    gcal.add_events(team_name, schedule)


if __name__ == "__main__":
    main()

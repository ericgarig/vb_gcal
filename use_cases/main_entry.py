from pathlib import Path

from app_props import AppProps

from use_cases.gcal import GCal
from use_cases.gcal_attendance_manager import AttendanceManager
from use_cases.ref_quest import RefQuest
from use_cases.vb_scrape import VbScrape


class MainEntry:
    def __init__(self):
        config_path = str(Path(__file__).parents[1] / "config/config.yml")
        AppProps("", config_path)

        self.gcal = GCal()
        self.add_cal_id = AppProps("calendar.calendar_id_vb")
        self._existing_events = None

    @property
    def existing_events(self):
        """Lazy loader for existing calendar events."""
        if self._existing_events is None:
            self._existing_events = self.gcal.get_upcoming_events(self.add_cal_id)
        return self._existing_events

    def execute(self, param: str):
        """Main router for command-line arguments."""
        match param.lower():
            case "ny urban":
                self.scrape_latest_ny_urban()
            case "rq+":
                self.req_quest()
            case _:
                print(f"Unknown command: {param}")
                print("Usage: python main.py ['ny urban' | 'rq+']")

    def scrape_latest_ny_urban(self):
        scrape = VbScrape()
        attends = AttendanceManager()

        # get schedule for latest team(s)
        raw_games, gyms = scrape.get_schedule()
        games = scrape.parse_schedule(raw_games, gyms, upcoming_only=True)

        # confirm settings
        email_groups = attends.get_team_email_map(games)

        # create/update events
        events = [game.to_gcal_dict(email_groups.get(game.team)) for game in games]
        self.gcal.process_all_events(self.add_cal_id, events, self.existing_events)

    def req_quest(self):
        rq = RefQuest(self.gcal)
        matches = rq.execute()

        self.gcal.process_all_events(self.add_cal_id, matches, self.existing_events)

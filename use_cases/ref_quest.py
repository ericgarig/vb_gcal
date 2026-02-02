import re

from app_props import AppProps

from use_cases.gcal import GCal


class RefQuest:
    def __init__(self, google_cal: GCal):
        self.google_cal = google_cal

    def execute(self) -> list[dict]:
        upcoming = []
        upcoming.extend(self.google_cal.get_upcoming_events(AppProps("calendar.calendar_id_rq1")))
        upcoming.extend(self.google_cal.get_upcoming_events(AppProps("calendar.calendar_id_rq2")))
        return [self.normalize_data(i) for i in upcoming]

    @staticmethod
    def normalize_data(e: dict) -> dict:
        """Normalize RQ+ data"""
        desc = re.sub(r"\s*\([^)]*\)", "", e.get("description"))
        return {
            "summary": f"Ref: {desc}",
            "location": e.get("location"),
            "description": e.get("summary"),
            "start": e.get("start"),
            "end": e.get("end"),
        }

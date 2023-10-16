import os.path
import re
from datetime import datetime, timedelta
from typing import Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import Config

UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


class GCal:
    def __init__(self, cnf: Config) -> None:
        self.cnf = cnf
        self.service = None

        # If modifying these scopes, delete the file token.json.
        self.scopes = self.cnf.cnf_list("calendar.scopes")

        self.calendar_id = self.cnf.cnf_value("calendar.calendar_id")
        self.max_offset = self.cnf.cnf_value("calendar.max_offset")
        self.print_events = self.cnf.cnf_value("flag.print_events")
        self.create_events = self.cnf.cnf_value("flag.create_events")

    def get_email_attendees(self):
        # TODO confirm email obj
        if self.cnf.cnf_value("flag.add_email_guests"):
            return [{"email": i, "optional": True} for i in self.cnf.get_email_list()]
        return []

    def authenticate_service(self) -> None:
        """Authenticate a service."""

        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.

        path_token = self.cnf.cnf_value("calendar.token_path")
        path_creds = self.cnf.cnf_value("calendar.creds_path")

        if os.path.exists(path_token):
            creds = Credentials.from_authorized_user_file(path_token, self.scopes)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    path_creds, self.scopes
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(path_token, "w") as token:
                token.write(creds.to_json())

        self.service = build("calendar", "v3", credentials=creds)

    def get_upcoming_events(
        self,
        num_events: int = 100,
        time_from: datetime = None,
        time_until: datetime = None,
        duration: str = None,
    ) -> list:
        """Prints the start and name of the next 'num_events' on the user's calendar."""
        events = []
        try:
            if not self.service:
                self.authenticate_service()
            if not time_from:
                # 'Z' indicates UTC time
                time_from = datetime.utcnow().isoformat() + "Z"
            if duration:
                time_until = (
                    datetime.strptime(time_from, "%Y-%m-%dT%H:%M:%S.%fZ")
                    + timedelta(seconds=GCal.convert_to_seconds(duration))
                ).isoformat() + "Z"
            if self.print_events:
                print(f"...getting the upcoming {num_events} events")
            events_result = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_from,
                    timeMax=time_until,
                    maxResults=num_events,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
        except HttpError as error:
            print("An error occurred: %s" % error)
        if not events and self.print_events:
            print("No upcoming events found.")
        if self.print_events:
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                print(f"     {start} {event['summary']}")
        return events

    def add_events(self, team_name: str, schedule: dict, existing_events: list) -> list:
        print(f"...creating events")
        status = []
        for one_game in schedule:
            details = self.get_event_details(
                title=team_name,
                description=f"vs. {one_game[2]} @{one_game[1]}",
                location=one_game[4] if one_game[4] else one_game[3],
                start_dt=one_game[0],
            )
            existing_event = GCal.get_existing_event(details, existing_events)
            status.append(self.add_one_event(details, existing_event))
        return status

    def add_one_event(
        self, details: dict = None, existing_event: dict = {}
    ) -> Tuple[str, str]:
        """Create an event."""
        if self.create_events:
            event_id = existing_event.get("id")
            if event_id is None:
                status = "created"
                event = (
                    self.service.events()
                    .insert(calendarId=self.calendar_id, body=details)
                    .execute()
                )
            elif GCal.update_needed(details, existing_event):
                status = "updated"
                event = (
                    self.service.events()
                    .update(calendarId=self.calendar_id, body=details, eventId=event_id)
                    .execute()
                )
            else:
                status = "skip, no changes"
                event = {**details, "id": event_id}
        else:
            status = "dry_run"
            event = {**details, "id": "999__dry_run"}
        if self.print_events:
            print(
                f"     {status}: "
                f"{event.get('summary')} {event.get('description')} @ {event.get('start', {}).get('dateTime')}"
            )
        return event.get("id"), status

    @staticmethod
    def update_needed(details: dict, existing: dict) -> bool:
        for i in details.keys():
            if existing[i] != details[i]:
                return False
        return True

    def get_event_details(
        self,
        title="event_from_py",
        description=None,
        location=None,
        start_dt=None,
        tz=None,
    ) -> dict:
        """Prepare event details."""
        if not start_dt:
            raise Exception("missing start date or time")
        event = {"summary": title}
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        event["start"] = self.event_dt(start_dt)
        event["end"] = self.event_dt(start_dt + timedelta(hours=1))
        event["attendees"] = self.get_email_attendees()
        return event

    @staticmethod
    def get_existing_event(details: dict, existing_events: list) -> dict:
        min_match = {k: details[k] for k in ("summary", "start", "end") if k in details}
        for i in existing_events:
            if min_match.items() <= i.items():
                return i
        return {}

    @staticmethod
    def dt_to_str(dt: datetime) -> str:
        dt_str = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        if dt_str[-2] != ":":
            dt_str = dt_str[:-2] + ":" + dt_str[-2:]
        return dt_str

    def event_dt(self, dt: datetime, tz=None):
        tz = tz if tz else self.cnf.cnf_value("timezone")
        return {"dateTime": GCal.dt_to_str(dt), "timeZone": tz}

    @staticmethod
    def convert_to_seconds(s):
        return int(
            timedelta(
                **{
                    UNITS.get(m.group("unit").lower(), "seconds"): float(m.group("val"))
                    for m in re.finditer(
                        r"(?P<val>\d+(\.\d+)?)(?P<unit>[smhdw]?)", s, flags=re.I
                    )
                }
            ).total_seconds()
        )

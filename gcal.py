from datetime import datetime, timedelta
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import Config


class GCal:
    def __init__(self, cnf: Config):
        self.cnf = cnf
        self.service = None
        # If modifying these scopes, delete the file token.json.
        self.scopes = self.cnf.cnf_list("calendar.scopes")
        self.calendar_id = self.cnf.cnf_value("calendar.calendar_id")
        self.print_events = self.cnf.cnf_value("flag.print_events")
        self.create_events = self.cnf.cnf_value("flag.create_events")
        self.emails = (
            [{"email": i, "optional": True} for i in cnf.get_email_list()]
            if self.cnf.cnf_value("flag.add_email_guests`")
            else []
        )

    def authenticate_service(self):
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

    def get_upcoming_events(self, num_events: int = 10, now: datetime = None):
        """Prints the start and name of the next 'num_events' on the user's calendar."""
        try:
            if not self.service:
                self.authenticate_service()
            if not now:
                # 'Z' indicates UTC time
                now = datetime.utcnow().isoformat() + "Z"

            if self.print_events:
                print(f"Getting the upcoming {num_events} events")
            events_result = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=now,
                    maxResults=num_events,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])

            if not events and self.print_events:
                print("No upcoming events found.")
            if self.print_events:
                for event in events:
                    start = event["start"].get("dateTime", event["start"].get("date"))
                    print(start, event["summary"])
            return events

        except HttpError as error:
            print("An error occurred: %s" % error)

    def add_events(self, team_name: str, schedule: dict):
        for one_game in schedule:
            details = self.get_event_details(
                title=team_name,
                description=f"vs. {one_game[2]} @{one_game[1]}",
                location=one_game[4] if one_game[4] else one_game[3],
                start_dt=one_game[0],
            )
            self.add_one_event(details)

    def add_one_event(self, details: dict = None, event_id: str = None) -> str:
        """Create an event."""
        event_action = "created" if event_id is None else "updated"
        if self.create_events:
            if event_id is None:
                event = (
                    self.service.events()
                    .insert(calendarId=self.calendar_id, body=details)
                    .execute()
                )
            else:
                event = (
                    self.service.events()
                    .update(calendarId=self.calendar_id, body=details, eventId=event_id)
                    .execute()
                )
        else:
            event = {
                "id": "999 - email send skipped",
                "summary": details.get("summary"),
                "description": details.get("description"),
            }
        if self.print_events:
            print(
                f"Event {event_action}: "
                f"{event.get('summary')} {event.get('description')} @ {event.get('start').get('dateTime')}"
            )

        return event["id"]

    def get_event_details(
        self,
        title="event_from_py",
        description=None,
        location=None,
        start_dt=None,
        tz="America/New_York",
    ):
        """Prepare event details."""
        if not start_dt:
            raise Exception("missing start date or time")
        event = {"summary": title}
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        event["start"] = GCal.event_dt(start_dt, tz)
        event["end"] = GCal.event_dt(start_dt + timedelta(hours=1), tz)
        # TODO confirm email obj
        event["attendees"] = self.emails
        return event

    @staticmethod
    def dt_to_str(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    @staticmethod
    def event_dt(dt: datetime, tz="America/New_York"):
        return {"dateTime": GCal.dt_to_str(dt), "timeZone": tz}

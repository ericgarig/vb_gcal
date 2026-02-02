import os.path
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app_props import AppProps
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from common.durations import convert_to_seconds


class GCal:
    RFC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    def __init__(self) -> None:
        self._service: Any = None

        # If modifying these scopes, delete the file token.json.
        self.scopes = AppProps("calendar.scopes").split(",")

        # config
        self.max_offset = AppProps("calendar.max_offset")
        self.tz = ZoneInfo(AppProps("timezone"))

        # flags
        self.print_events = AppProps("flag.print_events")
        self.create_events = AppProps("flag.create_events")

    @property
    def service(self) -> Any:
        """Lazy load service, property to ensure it's always authenticated before use."""
        if self._service is None:
            self.authenticate_service()
        return self._service

    def authenticate_service(self) -> None:
        """Authenticate a service."""
        path_token = AppProps("calendar.token_path")
        path_creds = AppProps("calendar.creds_path")
        creds = None

        if os.path.exists(path_token):
            creds = Credentials.from_authorized_user_file(path_token, self.scopes)

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(path_creds, self.scopes)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(path_token, "w") as token:
                token.write(creds.to_json())

        self._service = build("calendar", "v3", credentials=creds)

    def get_calendar_details(self, calendar_id: str) -> dict:
        """Retrieves metadata for a specific calendar by ID."""
        try:
            # Using calendarList().get() to get metadata like 'summary' (name)
            calendar_meta = self.service.calendarList().get(calendarId=calendar_id).execute()
            return {
                "name": calendar_meta.get("summary"),
                "description": calendar_meta.get("description"),
                "timezone": calendar_meta.get("timeZone"),
                "role": calendar_meta.get("accessRole"),
            }
        except HttpError as error:
            print(f"Google API Error: {error}")
            return {}

    def get_upcoming_events(
            self,
            calendar_id: str = None,
            num_events: int = 250,
            time_from: datetime | None = None,
            time_until: datetime | None = None,
    ) -> list[dict]:
        """Prints the start and name of the next 'num_events' on the user's calendar."""
        # get start/end times
        start_dt = time_from or datetime.now(timezone.utc)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        if not time_until:
            end_dt = start_dt + timedelta(seconds=convert_to_seconds(self.max_offset))
        else:
            end_dt = time_until if time_until.tzinfo else time_until.replace(tzinfo=timezone.utc)

        try:
            cal_info = self.get_calendar_details(calendar_id)
            if self.print_events:
                print(f" ...getting the upcoming {num_events} events for: {cal_info.get('name')}")

            events_result = (
                self.service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start_dt.strftime(self.RFC_FORMAT),
                    timeMax=end_dt.strftime(self.RFC_FORMAT),
                    maxResults=num_events,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except HttpError as error:
            print(f"Google API Error: {error}")
            return []

        events = events_result.get("items", [])
        normalized_events = [self.normalize_event_data(e) for e in events]

        if self.print_events:
            for e in normalized_events:
                print(f"     {self.as_local(e)} - {e.get('summary')}")
        return normalized_events

    def process_all_events(self, cal_id: str, events: list[dict], existing_events: list[dict]) -> list[tuple[str, str]]:
        """Processes a list of proposed event dictionaries, returning a list of event ids and tuples"""
        print(f" ...processing {len(events)} events")
        status = []
        for e in events:
            existing_event = self.find_match(e, existing_events)
            status.append(self.process_one_event(cal_id, e, existing_event))
        return status

    def process_one_event(self, cal_id: str, details: dict, existing_event: dict) -> tuple[str, str]:
        """Inserts, updates, or skips an event based on changes. Returns a tuple of event id and status"""
        if not self.create_events:
            return "999__dry_run", "dry_run"

        event_id = existing_event.get("id")
        try:
            if not event_id:
                status = "created"
                res = self.service.events().insert(calendarId=cal_id, body=details).execute()
                event_id = res.get("id")
            elif self.update_needed(details, existing_event):
                status = "updated"
                self.service.events().update(calendarId=cal_id, body=details, eventId=event_id).execute()
            else:
                status = "skip, no changes"
        except HttpError as e:
            status = f"error: {e.resp.status}"
            event_id = event_id or "error"

        if self.print_events:
            info = f"{details.get('summary')} {details.get('description')}"
            start = self.as_local(details)
            print(f"     {status.ljust(8)}: {info} @ {start}")
        return event_id, status

    def update_needed(self, details: dict, existing: dict) -> bool:
        """Returns True if any field in details differs from existing."""
        for field in ["summary", "description", "location", "start", "end"]:
            if details.get(field) != existing.get(field):
                return True

        # Check normalized email list
        return self.get_email_list(details) != self.get_email_list(existing)

    @staticmethod
    def get_email_list(e: dict) -> list[str]:
        """Get a list of attendees from an event dict, stripping other attrs and case sensitivity."""
        return sorted([i.get("email").lower() for i in e.get("attendees", [])])

    def normalize_event_data(self, e: dict) -> dict:
        """Normalize event data."""
        for f in ["start", "end"]:
            dt = datetime.fromisoformat(e.get(f, {}).get("dateTime")).astimezone(timezone.utc)
            e[f]["dateTime"] = dt.strftime(self.RFC_FORMAT)
        return e

    def as_local(self, data: str | dict) -> str:
        """Show UTC datetime string (or event start time from dict) in local timezone"""
        utc_val = data.get("start", {}).get("dateTime") if isinstance(data, dict) else data
        return datetime.fromisoformat(utc_val).astimezone(self.tz).isoformat()

    @staticmethod
    def find_match(details: dict, existing_events: list) -> dict:
        """Finds an existing event that matches summary and start/end times."""
        fields = ["summary", "start", "end"]
        for ee in existing_events:
            if all(details.get(f) == ee.get(f) for f in fields):
                return ee
        return {}

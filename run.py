"""Create events for upcoming games."""
import pickle
import os.path
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from helpers import read_creds
from team_data import get_schedule

"""
todo:
 - convert gym code/location to address
 - print something more useful than the event URL
 - check for events before adding duplicates
"""


# If modifying these scopes, delete the file token.pickle.
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def authenticate_service():
    """Authenticate a service."""
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    service = build("calendar", "v3", credentials=creds)
    return service


def get_events(service=None, calendar_id="primary", num_events=10):
    """Print the start and name of the next 'num_events'."""
    # 'Z' indicates UTC time
    now = datetime.utcnow().isoformat() + "Z"
    print("Getting the upcoming 10 events")
    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=now,
            maxResults=num_events,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    if not events:
        print("No upcoming events found.")
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        print(start, event["summary"])
    return True


def create_event(service=None, calendar_id="primary", details=None):
    """Create an event."""
    event = (
        service.events().insert(calendarId=calendar_id, body=details).execute()
    )
    print("Event created: {}".format(event.get("htmlLink")))
    return True


def add_game_event(
    title="event_from_py",
    description=None,
    location=None,
    start_dt=None,
    start_time=None,
    year=None,
    tz="America/New_York",
    emails=[],
):
    """Add a game to the calendar."""
    if not start_dt or not start_time:
        raise Exception(message="missing start date or time")
    if not year:
        year = datetime.now().year
    event = {}
    event["summary"] = title
    if description:
        event["description"] = description
    if location:
        event["location"] = location
    dt_obj = datetime.strptime(
        "{} {} {} pm".format(year, start_dt, start_time), "%Y %m/%d %I:%M %p"
    )
    dt_to_str = "%Y-%m-%dT%H:%M:%S"
    event["start"] = {"dateTime": dt_obj.strftime(dt_to_str), "timeZone": tz}
    event["end"] = {
        "dateTime": (dt_obj + timedelta(hours=1)).strftime(dt_to_str),
        "timeZone": tz,
    }
    emails = [{"email": i} for i in emails]
    if emails:
        event["attendees"] = emails
    return event


def get_emails():
    """Get list of teammate emails."""
    data = []
    with open("teammate_emails.txt", "r") as f:
        data = f.readlines()
        data = [i.strip() for i in data]
    return data


def main():
    """Main script."""
    creds = read_creds()
    service = authenticate_service()
    calendar_id = creds["calendar_id"]
    # get_events(service, calendar_id)
    event_info = get_schedule()
    [team_name, events] = event_info
    emails = get_emails()
    for i in events:
        event_details = add_game_event(
            team_name,
            description=i[3],
            location=i[1],
            start_dt=i[0],
            start_time=i[2],
            emails=emails,
        )
        create_event(service, calendar_id, event_details)
        # print(event_details)
    return True


if __name__ == "__main__":
    main()

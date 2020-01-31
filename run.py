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


def get_events(
    service=None,
    calendar_id="primary",
    num_events=10,
    now=None,
    print_events=True,
):
    """Print the start and name of the next 'num_events'."""
    # 'Z' indicates UTC time
    if not now:
        now = datetime.utcnow().isoformat() + "Z"
    if print_events:
        print("Getting the upcoming {} events".format(num_events))
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
    if not events and print_events:
        print("No upcoming events found.")
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        if print_events:
            print(start, event["summary"])
    return events


def create_event(
    service=None, calendar_id="primary", details=None, creds={}, event_id=None
):
    """Create an event."""
    event_action = "created" if event_id is None else "updated"
    details.pop("dt_obj", None)
    if creds.get("create_events"):
        if event_id is None:
            event = (
                service.events()
                .insert(calendarId=calendar_id, body=details)
                .execute()
            )
        else:
            event = (
                service.events()
                .update(calendarId=calendar_id, body=details, eventId=event_id)
                .execute()
            )
    else:
        event = {
            "id": "999 - email send skipped",
            "summary": details.get("summary"),
            "description": details.get("description"),
        }
    print(
        "Event {}: {} v. {}".format(
            event_action, event.get("summary"), event.get("description")
        )
    )
    return event["id"]


def event_details(
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
    event["dt_obj"] = dt_obj
    dt_to_str = "%Y-%m-%dT%H:%M:%S"
    event["start"] = {"dateTime": dt_obj.strftime(dt_to_str), "timeZone": tz}
    event["end"] = {
        "dateTime": (dt_obj + timedelta(hours=1)).strftime(dt_to_str),
        "timeZone": tz,
    }
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


def get_event_id(event_list=[], details=None):
    """Get the id of an event."""
    if not details:
        return None
    # print("-----")
    # print("EVENT_LIST", event_list)
    # print("DETAILS", details)
    existing_event = next(
        (
            one_event
            for one_event in event_list
            if one_event.get("summary") == details.get("summary")
            and one_event.get("description") == details.get("description")
            and one_event.get("start").get("dateTime")[:19]
            == details.get("start").get("dateTime")
        ),
        None,
    )
    if existing_event is not None:
        # print("EXISTING_EVENT:   ", existing_event)
        # print("DETAILS:   ", details)
        return existing_event["id"]
    return None


def main():
    """Main script."""
    now = datetime.utcnow()
    creds = read_creds()
    service = authenticate_service()
    calendar_id = creds.get("calendar_id")
    schedule_info = get_schedule()
    # print("schedule_info", schedule_info)
    [team_name, game_schedule] = schedule_info
    emails = []
    if creds.get("send_emails"):
        emails = [{"email": i, "optional": True} for i in get_emails()]
    existing_events = get_events(
        service,
        calendar_id,
        num_events=len(game_schedule),
        now=now.isoformat() + "Z",
        print_events=False,
    )
    # for i in existing_events:
    #     print("EXISTING EVENT:   ", i)
    for i in game_schedule:
        one_game_details = event_details(
            team_name,
            description=i[3],
            location=i[1],
            start_dt=i[0],
            start_time=i[2],
            emails=emails,
        )
        if now <= one_game_details["dt_obj"]:
            event_id = get_event_id(existing_events, one_game_details)
            # print("ONE DETAIL:   ", one_game_details)
            # print("EVENT ID", event_id)
            create_event(
                service, calendar_id, one_game_details, creds, event_id
            )
    return True


if __name__ == "__main__":
    main()

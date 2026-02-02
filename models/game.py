from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional


@dataclass
class Game:
    start: datetime
    team: str
    opponent: str
    gym_code: str
    gym_name: Optional[str] = None
    gym_address: Optional[str] = None

    def to_gcal_dict(self, attendees: list[str] = None) -> dict:
        """
        Converts the Game object into the RFC 3339 dictionary format
        required by the Google Calendar API.
        """
        # We strip microseconds to make comparison with GCal easier later
        start_utc = self.start.astimezone(timezone.utc).replace(microsecond=0)
        end_utc = start_utc + timedelta(hours=1)
        rfc_format = "%Y-%m-%dT%H:%M:%SZ"

        return {
            "summary": self.team,
            "description": f"vs. {self.opponent} @{self.gym_code}",
            # TODO: confirm using gym name (if specified)
            "location": self.gym_name or self.gym_address or self.gym_code,
            "start": {"dateTime": start_utc.strftime(rfc_format), "timeZone": "UTC"},
            "end": {"dateTime": end_utc.strftime(rfc_format), "timeZone": "UTC"},
            "attendees": [{"email": email, "optional": True} for email in (attendees or [])],
        }

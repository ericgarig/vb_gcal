from sys import exit

from app_props import AppProps

from models.Game import Game


class UserInput:
    def __init__(self):
        self.num_teams = AppProps("flag.num_teams")

    def execute(self, games: list[Game]):
        teams = self.get_team_names(games)
        email_groups = self.get_email_attendees()
        if len(teams) < self.num_teams:
            raise Exception(f">>> expected {self.num_teams} teams, have only {len(teams)} ({', '.join(teams)})")
        if len(email_groups) < self.num_teams:
            email_groups.extend([[]] * (self.num_teams - len(email_groups)))

        attendees = dict(zip(teams, email_groups))
        msg = "Confirm team emails:\n"
        for k, v in attendees.items():
            # TODO: confirm extraction of emails from dict if none are specified
            msg += f"    '{k}': {', '.join([i.get('email') for i in v])}\n"
        if not self.confirm_with_user(msg):
            raise Exception(">>> Rejected email confirmation")
        return attendees

    @staticmethod
    def get_email_attendees() -> list[list[dict[str, str | bool]]]:
        # TODO confirm email obj
        if not AppProps("flag.add_email_guests"):
            return []

        with open(AppProps("calendar.email_path"), "r") as f:
            raw_emails = [i.strip() for i in f.readlines()]
        raw_emails = raw_emails if raw_emails else []

        groups = []
        emails = []
        for i in raw_emails:
            if i == "":
                continue
            if i == "-":
                groups.append(emails)
                emails = []
                continue
            emails.append({"email": i, "optional": True})
        else:
            groups.append(emails)
        return groups

    @staticmethod
    def get_team_names(games: list[Game]) -> list[str]:
        teams = []
        teams_set = set()
        for i in games:
            if i.team not in teams_set:
                teams.append(i.team)
                teams_set.add(i.team)
        return teams

    @staticmethod
    def confirm_with_user(msg: str) -> bool:
        while True:  # Loop until a valid response is given
            reply = input(f"Q: {msg} (y/n): ").strip().lower()
            if reply in ["y", "yes"]:
                return True
            elif reply in ["n", "no"]:
                exit("User declined confirmation")
            else:
                print("Please respond with 'y' or 'n'.")

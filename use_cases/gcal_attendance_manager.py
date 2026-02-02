from app_props import AppProps

from models.game import Game


class AttendanceManager:
    def __init__(self):
        self.expected_team_count = AppProps("flag.num_teams")
        self.add_guests = AppProps("flag.add_email_guests")
        self.email_file_path = AppProps("calendar.email_path")

    def get_team_email_map(self, games: list[Game]) -> dict[str, list[str]]:
        """Get a dict of a team name and a list of attendees dicts (email and optional bool)"""
        teams = self._extract_unique_teams(games)
        if len(teams) != self.expected_team_count:
            raise Exception(
                f">>> expected {self.expected_team_count} teams, have only {len(teams)} ({', '.join(teams)})"
            )

        email_groups = self._load_email_groups()
        while len(email_groups) < len(teams):
            email_groups.append([])

        team_mapping = dict(zip(teams, email_groups))
        self._confirm_mapping_with_user(team_mapping)
        return team_mapping

    @staticmethod
    def _extract_unique_teams(games: list[Game]) -> list[str]:
        """Returns ordered list of unique team names found in games."""
        teams = []
        for g in games:
            if g.team not in teams:
                teams.append(g.team)
        return teams

    def _load_email_groups(self) -> list[list[str]]:
        """Reads email file and splits groups by the '-' delimiter."""
        if not self.add_guests:
            return [[]]

        try:
            with open(self.email_file_path, "r") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
        except FileNotFoundError:
            print(f">>> Warning: Email file not found at {self.email_file_path}")
            return [[]]

        groups = []
        current_group = []
        for line in lines:
            if line == "":
                continue
            if line == "-":
                # team grouping separator
                groups.append(current_group)
                current_group = []
                continue
            current_group.append(line)

        groups.append(current_group)  # Add the last group
        return groups

    @staticmethod
    def _confirm_mapping_with_user(mapping: dict[str, list[str]]) -> None:
        """Prints the mapping and requires terminal input to proceed."""
        msg = "Confirm team emails:\n"
        for team, emails in mapping.items():
            email_list = ", ".join(emails) if emails else ">>>No guests<<<"
            email_count = f" ({len(emails)})" if emails else ""
            msg += f"    '{team}'{email_count}: {email_list}\n"

        # Loop until a valid response is given
        print(msg)
        while True:
            reply = input("Q: Does this mapping look correct? (y/n): ").strip().lower()
            if reply in ["y", "yes"]:
                return
            if reply in ["n", "no"]:
                raise Exception(">>> Rejected email confirmation")
            print("Please respond with 'y' or 'n'.")

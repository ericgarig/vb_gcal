"""Get most recent team data for NYUrban."""
from datetime import datetime, timezone
from urllib.parse import parse_qs

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as e_c
from selenium.webdriver.chrome.options import Options

import os

from config import Config

DRIVER_URL = "https://sites.google.com/chromium.org/driver/"


class VbScrape:
    def __init__(self, cnf: Config):
        self.cnf = cnf
        self.url = self.cnf.cnf_value("scrape.url")
        self.log_scrape = self.cnf.cnf_value("flag.log_scrape")
        self.scrape_headless = self.cnf.cnf_value("flag.scrape_headless")
        self.driver = None
        self.html_doc = None
        self.team_name = None
        self.games = []
        self.gym = {}

    def get_schedule(self) -> list:
        """Get schedule for the current NY Urban season."""
        try:
            options = Options()
            if self.scrape_headless:
                options.headless = True
            if self.log_scrape:
                print(
                    f"...setting up {'headless ' if self.scrape_headless else ''}driver"
                )
            self.driver = webdriver.Chrome(
                executable_path=self.get_chromedriver_path(), options=options
            )
            try:
                self.login()
                self.get_latest_team_page()
                self.parse_team_data()
                self.parse_gym_info()
            finally:
                self.driver.close()
                self.driver = None
        except SessionNotCreatedException as e:
            print(
                f">>>ERROR: {e.msg}Get the version matching your Chrome browser and place it in '/vendor' from:\n{DRIVER_URL}"
            )
        except WebDriverException as e:
            print(
                f">>>ERROR: Get the latest 'chromedriver' binary from the link below and place it in '/vendor':\n{DRIVER_URL}"
            )
        except Exception as e:
            print(f">>> Some other exception with selenium: {e}")
        return [self.team_name, self.games, self.gym]

    def get_chromedriver_path(self) -> str:
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "vendor",
            self.cnf.cnf_value("scrape.chromedriver"),
        )

    def login(self) -> None:
        """Authenticate into NY Urban."""
        if not self.driver:
            return None
        if self.log_scrape:
            print(f"...logging in: {self.url}")
        self.driver.get(self.url)
        assert "Volleyball League" in self.driver.title
        user = self.driver.find_element_by_id("username")
        user.clear()
        user.send_keys(self.cnf.cnf_value("scrape.user"))
        pwd = self.driver.find_element_by_id("password")
        pwd.clear()
        pwd.send_keys(self.cnf.cnf_value("scrape.pwd"))
        pwd.send_keys(Keys.RETURN)
        if self.driver.title == "Login Problems":
            raise ValueError("invalid credentials")
        WebDriverWait(self.driver, 10).until(e_c.title_is("Team Listing"))

    def get_latest_team_page(self) -> None:
        """Get the page source for the most recent team."""
        if not self.driver:
            return
        if self.log_scrape:
            print("...navigating to latest team details")
        assert "Team Listing" in self.driver.title
        team_link = self.driver.find_element_by_xpath("//tbody/tr[2]/td/a")
        team_link.click()
        WebDriverWait(self.driver, 10).until(e_c.title_is("Team Detail"))
        source = self.driver.page_source
        assert "Division:" in source
        self.html_doc = source

    def parse_team_data(self) -> None:
        """
        Parse team data into a list.

        Returns a list of games. Each game is a list with the following items:
        [datetime, location, opponent]
        """
        if self.log_scrape:
            print("...retrieving schedule")
        soup = BeautifulSoup(self.html_doc, "html.parser")
        self.team_name: str = soup.find("div", class_="team").h1.span.text.strip()
        team_table = soup.find("div", class_="team_div").div.table.tbody
        rows = team_table.findChildren("tr", recursive=False)
        for row in rows[1:]:
            cols = row.findChildren("td", recursive=False)
            if "No Game This Week" not in cols[3].text:
                self.games.append(
                    [
                        # TODO check for next-year rollover
                        datetime.strptime(
                            f"{cols[0].text.split()[1].strip()} {datetime.now().year} {cols[2].text.strip()}PM -0500",
                            "%m/%d %Y %I:%M%p %z",
                        ),
                        cols[1].div.a.text.strip(),
                        cols[3].text.split()[0].strip(),
                    ]
                )

    def parse_gym_info(self) -> None:
        """Get a dict mapping of gym code to name and address."""
        if self.log_scrape:
            print("...retrieving gyms")
        soup = BeautifulSoup(self.html_doc, "html.parser")
        gym_table = soup.find("div", class_="locationcontent").div.table.tbody
        rows = gym_table.findChildren("tr", recursive=False)
        for row in rows[1:]:
            cols = row.findChildren("td", recursive=False)
            gym_code = cols[0].string
            if gym_code in self.gym:
                continue
            gym_name = cols[1].contents[0].text.strip()
            try:
                address = parse_qs(cols[2].a.attrs.get("href")).get("address")[0]
            except Exception:
                address = None
            self.gym[gym_code] = [gym_name, address]

    @staticmethod
    def parse_schedule(schedule: list, upcoming_only=False) -> list:
        """Get the schedule with gym names and locations."""
        from_ts = datetime.now(timezone.utc) if upcoming_only else datetime(2000, 1, 1)
        games = []
        for one_game in schedule[1]:
            if one_game[0] < from_ts:
                continue
            one_game.extend(schedule[2][one_game[1]])
            games.append(one_game)
        return [schedule[0], games]

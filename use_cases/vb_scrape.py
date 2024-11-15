"""Get most recent team data for NYUrban."""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

import pytz
from app_props import AppProps
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as e_c
from selenium.webdriver.support.ui import WebDriverWait

from models.Game import Game


class VbScrape:
    def __init__(self):
        self.url = AppProps("scrape.vb_url")
        self.driver_url = AppProps("scrape.driver_url")
        self.log_scrape = AppProps("flag.log_scrape")
        self.scrape_headless = AppProps("flag.scrape_headless")
        self.num_teams = AppProps("flag.num_teams")
        self.tz = AppProps("timezone")

        self.driver = None
        self.html_doc = []
        self.games: list[Game] = []
        self.gyms: dict[str, list[str]] = {}

        self.get_driver()

    def get_driver(self):
        err_msg = None
        try:
            options = Options()
            if self.scrape_headless:
                options.add_argument("--headless=new")
            if self.log_scrape:
                print(f"...setting up {'headless ' if self.scrape_headless else ''}driver")
            self.driver = webdriver.Chrome(options=options, service=Service(VbScrape.get_chromedriver_path()))
        except SessionNotCreatedException as e:
            err_msg = (
                f"{e.msg}"
                f"Get the version matching your Chrome browser and place it in '/vendor' from:"
                f"\n{self.driver_url}"
            )
        except WebDriverException as e:
            err_msg = (
                f"{e.msg}"
                f"Get the latest 'chromedriver' binary from the link below and place it in '/vendor':"
                f"\n{self.driver_url}"
            )
        except Exception as e:
            err_msg = f"Some other exception with selenium: {e}"
        if err_msg:
            print(f">>>ERROR: {err_msg}")
            sys.exit()

    def get_schedule(self) -> tuple[list[Game], dict[str, list[str]]]:
        """Get schedule for the current NY Urban season."""
        try:
            self.login()
            self.get_latest_team_page()
            self.parse_team_data()
            self.parse_gym_info()
        finally:
            self.driver.close()
            self.driver = None
        return self.games, self.gyms

    @staticmethod
    def get_chromedriver_path() -> str:
        return str(Path(__file__).parents[2] / "vendor" / AppProps("scrape.chromedriver"))

    def login(self) -> None:
        """Authenticate into NY Urban."""
        if not self.driver:
            return None
        if self.log_scrape:
            print(f"...logging in: {self.url}")
        self.driver.get(self.url)
        assert "Volleyball League" in self.driver.title
        user = self.driver.find_element(By.ID, "username")
        user.clear()
        user.send_keys(AppProps("scrape.user"))
        pwd = self.driver.find_element(By.ID, "password")
        pwd.clear()
        pwd.send_keys(AppProps("scrape.pwd"))
        pwd.send_keys(Keys.RETURN)
        if self.driver.title == "Login Problems":
            raise ValueError("invalid credentials")
        WebDriverWait(self.driver, 10).until(e_c.title_is("Team Listing"))

    def get_latest_team_page(self) -> None:
        """Get the page source for the most recent team(s)."""
        if not self.driver:
            return
        if self.log_scrape:
            print("...navigating to latest team details")
        for i in range(self.num_teams):
            # ensure on team list page
            assert "Team Listing" in self.driver.title

            # navigate to team page and grab content
            team_link = self.driver.find_element(By.XPATH, f"//tbody/tr[{i + 2}]/td/a")
            print(f"     ...getting info for '{team_link.text}'")
            team_link.click()
            WebDriverWait(self.driver, 10).until(e_c.title_is("Team Detail"))
            source = self.driver.page_source
            assert "Division:" in source
            self.html_doc.append(source)

            # go back
            self.driver.execute_script("window.history.go(-1)")

    def parse_team_data(self) -> None:
        """
        Parse team data into a list.

        Returns a list of games. Each game is a list with the following items:
        [datetime, location, opponent]
        """
        if self.log_scrape:
            print("...retrieving schedule(s)")
        for one_team in self.html_doc:
            soup = BeautifulSoup(one_team, "html.parser")
            team_name = soup.find("div", class_="team").h1.span.text.strip()
            team_table = soup.find("div", class_="team_div").div.table.tbody
            rows = team_table.findChildren("tr", recursive=False)
            for row in rows[1:]:
                cols = row.findChildren("td", recursive=False)
                if "No Game This Week" in cols[3].text:
                    continue
                self.games.append(
                    # TODO check for next-year rollover
                    # TODO check daylight savings
                    Game.parse_obj(
                        {
                            "start": self.game_time(cols),
                            "team": team_name,
                            "gym_code": cols[1].div.a.text.strip(),
                            "opponent": next(sub for sub in re.split(r"\n|\t", cols[3].text) if sub),
                        },
                    )
                )

    def game_time(self, data) -> datetime:
        month_date = data[0].text.split()[1].strip()
        year = datetime.now().year
        time = data[2].text.strip()
        dt = datetime.strptime(f"{month_date} {year} {time} PM", "%m/%d %Y %I:%M %p")
        return pytz.timezone(self.tz).localize(dt)

    def parse_gym_info(self) -> None:
        """Get a dict mapping of gym code to name and address."""
        if self.log_scrape:
            print("...retrieving gyms")
        soup = BeautifulSoup(self.html_doc[0], "html.parser")
        gym_table = soup.find("div", class_="locationcontent").div.table.tbody
        rows = gym_table.findChildren("tr", recursive=False)
        for row in rows[1:]:
            cols = row.findChildren("td", recursive=False)
            gym_code = cols[0].string
            if gym_code in self.gyms:
                continue
            gym_name = cols[1].contents[0].text.strip()
            try:
                address = parse_qs(cols[2].a.attrs.get("href")).get("address")[0]
            except (Exception,):
                address = None
            self.gyms[gym_code] = [gym_name, address]

    def parse_schedule(self, schedule: tuple[list[Game], dict] = None, upcoming_only=False) -> list[Game]:
        """Get the schedule with gym names and locations, optionally filtering out past games."""
        scheduled_games = schedule[0] if schedule else self.games
        gyms = schedule[1] if schedule else self.gyms

        from_ts = datetime.now(timezone.utc) if upcoming_only else datetime(2000, 1, 1)
        games = []
        for one_game in scheduled_games:
            if one_game.start < from_ts:
                continue
            gym_info = gyms[one_game.gym_code]
            one_game.gym_name = gym_info[0]
            one_game.gym_address = gym_info[1]
            games.append(one_game)
        return games

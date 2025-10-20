"""Get most recent team data for NYUrban."""

import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

import pytz
import requests
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

    # TODO: move get_driver() and all logic associated with setting-up/downloading/etc... the driver into separate use case

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
            match = re.search(r"Chrome version (\d+).*?Current browser version is (\d+)", e.msg, re.DOTALL)
            if match and "ChromeDriver" in e.msg:
                current_version = match.group(1)
                latest_version = match.group(2)
                print(f"     ...outdated chromedriver detected (v. {current_version}), downloading v. {latest_version}")
                self.get_latest_chromedriver(int(latest_version))
                err_msg = (
                    f"Downloaded latest chromedriver. Update 'scrape.chromedriver' evn variable. Please try again."
                )

            else:
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
        vendor_path = Path(__file__).parents[1] / "vendor"
        driver_name = AppProps("scrape.chromedriver")
        if not driver_name or driver_name == "latest":
            driver_path = max(vendor_path.iterdir(), key=lambda p: p.name)
        else:
            driver_path = vendor_path / driver_name
        return str(driver_path)

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

    def get_latest_chromedriver(self, latest_version: int):
        driver_info = requests.get(self.driver_url)
        if driver_info.status_code != 200:
            raise Exception(f"Error getting driver info: {driver_info.status_code}")
        driver_info = driver_info.json()
        platform_data = driver_info.get("channels", {}).get("Stable", {}).get("downloads", {}).get("chromedriver", {})
        platform_key = self.get_platform_key()
        print(f"         ...detected platform: '{platform_key}'")

        for item in platform_data:
            if item.get("platform") == platform_key:
                new_driver_url = item.get("url")
                break
        else:
            raise Exception("Error: Platform not supported or could not be determined.")
        self.install_chromedriver(new_driver_url, latest_version)

    @staticmethod
    def get_platform_key():
        """Maps the current system's OS and architecture to a platform key."""
        os_name = platform.system().lower()
        machine = platform.machine().lower()

        if os_name == "linux":
            return "linux64"

        elif os_name == "darwin":
            if "arm" in machine:
                return "mac-arm64"
            elif "64" in machine or "x86" in machine:
                return "mac-x64"

        elif os_name == "windows":
            if "64" in machine or "amd64" in machine:
                return "win64"
            elif "32" in machine:
                return "win32"

        raise Exception(f"Unsupported platform: {os_name} {machine}")

    def install_chromedriver(self, url: str, version: int):
        repo_root = Path(__file__).resolve().parents[1]
        vendor_dir = repo_root / "vendor"
        temp_download_path = vendor_dir / "chromedriver_temp.zip"
        uncompressed_driver_path = vendor_dir / url.split("/")[-1].split(".")[0]
        final_path = vendor_dir / f"chromedriver_{version}"
        extracted_driver_path = uncompressed_driver_path / "chromedriver"

        self.download_by_stream(url, temp_download_path)

        print("         ...unzipping file and finding chromedriver...")
        try:
            with zipfile.ZipFile(temp_download_path, "r") as zip_ref:
                zip_ref.extractall(vendor_dir)
        except (zipfile.BadZipFile, FileNotFoundError) as e:
            os.remove(temp_download_path)
            raise Exception(f"Error during extraction: {e}")
        if not extracted_driver_path or not extracted_driver_path.exists():
            raise FileNotFoundError("Chromedriver executable not found in the zip file's top level.")
        if os.name != "nt":
            os.chmod(extracted_driver_path, 0o755)

        print(f"         ...moving driver to '{vendor_dir}'")
        try:
            shutil.move(extracted_driver_path, final_path)
        except Exception as e:
            print(f"Error during move/rename: {e}")

        print("         ...cleaning up temporary zip file.")
        if temp_download_path.exists():
            os.remove(temp_download_path)
        if uncompressed_driver_path.exists() and uncompressed_driver_path.is_dir():
            shutil.rmtree(uncompressed_driver_path)
        self.approve_driver_for_macos(final_path)

    @staticmethod
    def download_by_stream(url: str, download_file_path: Path):
        print(f"         ...downloading driver from: {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(download_file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print("             ...download successful.")

    @staticmethod
    def approve_driver_for_macos(driver_path: Path):
        """
        Removes the macOS Gatekeeper quarantine attribute from the driver executable.
        This resolves the "cannot be verified is free of malware" error.
        """
        if os.name != "posix" or platform.system().lower() != "darwin":
            # skip, not on a mac
            return

        print("         ...removing quarantine attribute for driver")
        try:
            command = ["xattr", "-d", "com.apple.quarantine", str(driver_path)]
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"   -> Warning: Failed to remove quarantine attribute. Error: {e.stderr.strip()}")
            print(
                "   -> You may need to run this script with elevated permissions (sudo) or manually approve the driver."
            )

        except FileNotFoundError:
            print("   -> Error: 'xattr' command not found. Cannot remove quarantine attribute.")

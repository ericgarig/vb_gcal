"""Get most recent team data for NYUrban."""
import os

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
    SessionNotCreatedException,
    WebDriverException,
)
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as e_c

from helpers import read_creds


def get_schedule():
    """Get data using selenium."""
    team_data = [None, []]
    chrome_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "vendor", "chromedriver"
    )
    try:
        driver = webdriver.Chrome(executable_path=chrome_path)
        login(driver)
        team_page = get_latest_team_page(driver)
        team_data = parse_team_data(team_page)
        driver.close()
    except SessionNotCreatedException as e:
        print(
            "{}Get the version matching your Chrome browser and place it in "
            + "'/vendor':\n{}".format(
                str(e),
                "https://sites.google.com/a/chromium.org/chromedriver/downloads",
            )
        )
    except WebDriverException:
        print(
            "Get the latest 'chromedriver' binary from the link below and "
            + "place it in '/vendor':\n{}".format(
                "https://sites.google.com/a/chromium.org/chromedriver/downloads"
            )
        )
    return team_data


def login(driver=None):
    """Authenticate into NY Urban."""
    if not driver:
        return None
    driver.get("https://www.nyurban.com/volleyball/")
    assert "Volleyball League" in driver.title
    creds = read_creds()
    user = driver.find_element_by_id("username")
    user.clear()
    user.send_keys(creds["urban_user"])
    pwd = driver.find_element_by_id("password")
    pwd.clear()
    pwd.send_keys(creds["urban_pwd"])
    pwd.send_keys(Keys.RETURN)
    WebDriverWait(driver, 10).until(e_c.title_is("Team Listing"))
    return True


def get_latest_team_page(driver):
    """Navigate to the latest team page after logging in."""
    if not driver:
        return None
    assert "Team Listing" in driver.title
    team_link = driver.find_element_by_xpath("//tbody/tr[2]/td/a")
    team_link.click()
    WebDriverWait(driver, 10).until(e_c.title_is("Team Detail"))
    source = driver.page_source
    assert "Division:" in source
    return source


def parse_team_data(html_doc):
    """
    Parse team data into a list.

    Returns a list of games. Each game is a list with the following items:
    [mm/dd, location, time, opponent]
    """
    games = []
    soup = BeautifulSoup(html_doc, "html.parser")
    team_name = soup.find("div", class_="team").h1.span.text.strip()
    team_table = soup.find("div", class_="team_div").div.table.tbody
    rows = team_table.findChildren("tr", recursive=False)
    for row in rows[1:]:
        cols = row.findChildren("td", recursive=False)
        if "No Game This Week" not in cols[3].text:
            games.append(
                [
                    cols[0].text.split()[1].strip(),
                    cols[1].div.a.text.strip(),
                    cols[2].text.strip(),
                    cols[3].text.split()[0].strip(),
                ]
            )
    return [team_name, games]

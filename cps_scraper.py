import requests
from bs4 import BeautifulSoup
import duckdb
import re
import os

URL = "https://it.muni.cz/en/services/university-computer-centre"
DB_NAME = "cps_tracker"

token = os.getenv("MOTHERDUCK_TOKEN")
if not token:
    raise ValueError("MOTHERDUCK_TOKEN not found in environment variables.")


def scrape_and_save():
    print("Scraping website...")
    response = requests.get(URL, timeout=10)
    response.raise_for_status()

    free_entries_text = BeautifulSoup(response.text, "html.parser").find(
        "strong",
        string=re.compile("Number of free entries")
    )

    if not free_entries_text:
        raise ValueError("Could not find the 'Number of free entries'.")

    free_entries = int(
        free_entries_text.next_sibling
        .strip()
        .split()[0]
    )

    print("Saving to db...")
    db = duckdb.connect(f"md:{DB_NAME}?motherduck_token={token}")
    db.sql(f"INSERT INTO occupancy_log VALUES (now(), {free_entries})")

    print("Data successfully saved")


if __name__ == "__main__":
    scrape_and_save()

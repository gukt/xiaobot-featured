import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from notion_client import Client

NOTION_TOKEN = os.environ.get("secret_6YvX4moThJGblR4OcfQXk84b58QLY9JYeANeXdGmnmo")
NOTION_DATABASE_ID = os.environ.get("1043b7f82e0b80f8b9c5ebcf3f88026e")

notion = Client(auth=NOTION_TOKEN)


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)


def scrape_xiaobot(author_id):
    url = f"https://xiaobot.net/p/{author_id}"
    driver = setup_driver()
    driver.get(url)

    try:
        # Wait for the title element to be present
        title_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".paper_title h1"))
        )
        title = title_element.text

        # Wait for the icon element to be present
        icon_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".header img"))
        )
        icon = icon_element.get_attribute("alt")

        return {
            "title": title,
            "icon": icon,
            "url": url,
            "author_id": author_id
        }
    finally:
        driver.quit()


def save_to_notion(data):
    notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "Title": {"title": [{"text": {"content": data["title"]}}]},
            "Icon": {"rich_text": [{"text": {"content": data["icon"]}}]},
            "URL": {"url": data["url"]},
            "Author ID": {"rich_text": [{"text": {"content": data["author_id"]}}]},
            "Last Updated": {"date": {"start": datetime.now().isoformat()}}
        }
    )


def main():
    with open('../authors.txt', 'r') as f:
        authors = f.read().splitlines()

    for author in authors:
        data = scrape_xiaobot(author)
        save_to_notion(data)
        print(f"Saved data for author: {author}")


if __name__ == "__main__":
    main()
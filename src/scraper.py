import requests
from bs4 import BeautifulSoup
from notion_client import Client
import os
from datetime import datetime

NOTION_TOKEN = os.environ.get("secret_6YvX4moThJGblR4OcfQXk84b58QLY9JYeANeXdGmnmo")
NOTION_DATABASE_ID = os.environ.get("1043b7f82e0b80f8b9c5ebcf3f88026e")

notion = Client(auth=NOTION_TOKEN)

def scrape_xiaobot(author_id):
    url = f"https://xiaobot.net/p/{author_id}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    title = soup.select_one('#app > div > div > div.app-container > div:nth-child(2) > div.paper-info > div.paper_title > h1')['alt']
    
    icon = soup.select_one('#app > div > div > div.app-container > div:nth-child(2) > div.paper-info > div.header > img')['alt']
    
    return {
        "title": title,
        "icon": icon,
        "url": url,
        "author_id": author_id
    }

def save_to_notion(data):
    notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "Title": {"title": [{"text": {"content": data["title"]}}]},
            "Description": {"rich_text": [{"text": {"content": data["description"]}}]},
            "URL": {"url": data["url"]},
            "Author ID": {"rich_text": [{"text": {"content": data["author_id"]}}]},
            "Last Updated": {"date": {"start": datetime.now().isoformat()}}
        }
    )

def main():
    with open('authors.txt', 'r') as f:
        authors = f.read().splitlines()
    
    for author in authors:
        data = scrape_xiaobot(author)
        save_to_notion(data)

if __name__ == "__main__":
    main()
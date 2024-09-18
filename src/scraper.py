import os
from datetime import datetime
import time  # 添加这一行
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from notion_client import Client

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

NOTION_TOKEN = "secret_XKLyoisWT09GFbcYNmDfvYNkpcFIfgtrXQzvulVSfnA"
NOTION_DATABASE_ID = "1043b7f8-2e0b-806e-9e31-dd541a1ed332"

notion = Client(auth=NOTION_TOKEN)


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)


def scrape_xiaobot(author_id):
    url = f"https://xiaobot.net/p/{author_id}"
    driver = setup_driver()

    print(f"Scraping data from URL: {url}")
    driver.get(url)
    print(f"Successfully loaded page: {url}")

    try:
        # 获取专栏名称
        title = driver.title

        # 获取 Icon 链接地址
        icon_elem = driver.find_element(By.CSS_SELECTOR, "img.avatar")
        icon = icon_elem.get_attribute("src")

        # 获取阅读人数
        reader_count_elem = driver.find_element(By.CSS_SELECTOR, ".paper-info .stats div.stat:nth-child(1) .num")
        reader_count = reader_count_elem.text

        # 获取文章数
        article_count_elem = driver.find_element(By.CSS_SELECTOR, ".paper-info .stats div.stat:nth-child(2) .num")
        article_count = article_count_elem.text

        # 获取描述
        intro_elem = driver.find_element(By.CSS_SELECTOR, ".paper-info p.intro")
        intro = intro_elem.text

        # 获取标签列表，如果找不到 tags, 就点击 category_elem 下的第二个元素
        category_elem = driver.find_element(By.CSS_SELECTOR, ".category")

        # 如果找不到 tags, 就点击 category_elem 下的第二个元素
        if not driver.find_elements(By.CSS_SELECTOR, "span.tag"):
            category_elem.find_elements(By.CSS_SELECTOR, "div")[1].click()

        # 等待 tags 元素加载完成
        tags_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.tags"))
        )

        # 一旦 tags 元素加载完成，首先要将它的 overflow 设置为 auto，这样才能获取到所有的 tags
        # 由于 div.tags 元素的父级定义了 overflow: hidden; 这将会导致取到的 tags 列表虽然是全的，但后面有部分 tag 的内容是空的
        # 将 div.tags 元素上设置 overflow 设置为 auto 可以解决这个问题
        driver.execute_script("document.querySelector('.tags').style.overflow = 'auto';")

        tag_elements = tags_elem.find_elements(By.CSS_SELECTOR, "span.tag")
        # 遍历 tags，去掉第一个标签（全部），并将前缀 # 字符去掉，以及后面的空格与数字。
        tags = [tag.text.replace("#", "").split(" ")[0] for tag in tag_elements[1:]]

        # 获取主理人
        # 助理人和内容标签，都是位于页面的 “内容” 标签下，所以放在一起获取
        author_elem = driver.find_element(By.CSS_SELECTOR, ".post .name")
        author = author_elem.text

        # 获取佣金比例，要想获取到佣金比例数据，需要点击 div.share-paper 元素，点击后会在底部弹出一个模态对话框，里面有推广佣金比例信信息，
        share_paper_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".share-paper"))
        )
        # 这里经常会出现错误：selenium.common.exceptions.ElementClickInterceptedException: Message: element click intercepted: Element <div data-v-5d99e6a8="" class="share-paper">...</div> is not clickable at point (922, 838). Other element would receive the click: <a data-v-7230098e="" class="btn btn-primary btn-large">...</a>
        # 所以下面多做一些保护措施：
        # 1. 有时候元素不在当前视口中，导致被其他元素遮挡，所以需要滚动到元素
        driver.execute_script("arguments[0].scrollIntoView(true);", share_paper_elem)
        time.sleep(1)  # 等待滚动完成
        # 2. 等待元素可点击
        share_paper_elem = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".share-paper"))
        )
        # 3. 点击元素
        share_paper_elem.click()
        
        # span.text-theme 是推广佣金比例信息，如果找不到，就点击 share-paper 元素
        if not driver.find_elements(By.CSS_SELECTOR, "span.text-theme"):
            share_paper_elem.click()

        # 获取佣金比例，等待 span.text-theme 元素出现
        commission_rate_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "span.text-theme"))
        )
        # 去掉百分号
        commission_rate = commission_rate_elem.text.replace("%", "")
        # 如果为空，则设置为 0
        commission_rate = commission_rate if commission_rate else '0'

        data = {
            "title": title,
            "url": url,
            "author_id": author_id,
            "author": author,
            "icon": icon,
            "reader_count": reader_count,
            "article_count": article_count,
            "intro": intro,
            # 如果 commission_rate 为空，就设置为 0
            "commission_rate": commission_rate,
            "tags": tags,
        }

        print(f"Scraped data: {data}")
        return data
    finally:
        driver.quit()


def save_to_notion(data):
    author_id = data["author_id"]
    properties = {
        "名称": {"title": [{"text": {"content": data["title"]}}]},
        "URL": {"url": data["url"]},
        "专栏 ID": {"rich_text": [{"text": {"content": author_id}}]},
        "主理人": {"rich_text": [{"text": {"content": data["author"]}}]},
        "读者数": {"number": int(data["reader_count"])},
        "文章数": {"number": int(data["article_count"])},
        "介绍": {"rich_text": [{"text": {"content": data["intro"]}}]},
        "内容标签": {"multi_select": [{"name": tag} for tag in data["tags"]]},
        "佣金比例": {"number": int(data["commission_rate"])},
    }

    # 查询是否已存在该专栏 ID 的页面
    existing_page = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "专栏 ID",
            "rich_text": {
                "equals": author_id
            }
        }
    )
    # 如果已存在该专栏 ID 的页面，则更新该页面
    if existing_page["results"]:
        page_id = existing_page["results"][0]["id"]
        print(f"Updating page: {page_id}")
        notion.pages.update(
            page_id=page_id,
            properties=properties
        )
    # 如果未找到该专栏 ID 的页面，则创建新页面
    else:
        print(f"Creating new page for author: {author_id}")
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties,
            children=[
                {
                    "object": "block",
                    "type": "image",
                    "image": {
                        "external": {
                            "url": data["icon"]
                        }
                    }
                }
            ]
        )
        print(f"Created new page for author: {author_id}")

def main():
    with open('../authors.txt', 'r') as f:
        authors = f.read().splitlines()

    for author in authors:
        data = scrape_xiaobot(author)
        save_to_notion(data)
        print(f"Saved data for author: {author}")


if __name__ == "__main__":
    main()

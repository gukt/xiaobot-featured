import os
from datetime import datetime
from datetime import timezone
import time
import json
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

notion = Client(auth=NOTION_TOKEN)


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 运行在无头模式下
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def get_commission_rate(driver):
    # 获取佣金比例，要想获取到佣金比例数据，需要点击 div.share-paper 元素，点击后会在底部弹出一个模态对话框，里面有推广佣金比例信信息，
    share_paper_elem = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".share-paper"))
    )

    # span.text-theme 是推广佣金比例信息，如果找不到，就点击 share-paper 元素
    if not driver.find_elements(By.CSS_SELECTOR, "span.text-theme"):
        share_paper_elem.click()

    # 做一些保护措施：有时候元素不在当前视口中，导致被其他元素遮挡，所以需要滚动到元素
    driver.execute_script("arguments[0].scrollIntoView(true);", share_paper_elem)
    time.sleep(1)  # 等待滚动完成

    # 获取佣金比例，等待 span.text-theme 元素出现
    rate_elem = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "span.text-theme"))
    )
    # 去掉百分号
    commission_rate = rate_elem.text.replace("%", "")
    # 如果为空，则设置为 0
    return int(commission_rate) if commission_rate else 0


def get_tags_and_author(driver):
    # 获取标签列表，如果找不到 tags, 就点击 category_elem 下的第二个元素
    category_elem = driver.find_element(By.CSS_SELECTOR, "div.category")
    if not driver.find_elements(By.CSS_SELECTOR, "span.tag"):
        category_elem.find_elements(By.CSS_SELECTOR, "div")[1].click()

    # 等待 tags 列表加载完成
    tags_elem = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.tags"))
    )

    # 设置 overflow:auto 来解决 tags 列表中部分标签被隐藏的问题
    driver.execute_script("document.querySelector('.tags').style.overflow = 'auto';")

    tag_elements = tags_elem.find_elements(By.CSS_SELECTOR, "span.tag")
    # 遍历 tags，去掉第一个标签（全部），并将前缀 # 字符去掉，以及后面的空格与数字。
    tags = [tag.text.replace("#", "").split(" ")[0] for tag in tag_elements[1:]]

    # 获取主理人
    author_elem = driver.find_element(By.CSS_SELECTOR, ".post .name")
    author = author_elem.text

    return tags, author


def scrape_xiaobot(author_id):
    url = f"https://xiaobot.net/p/{author_id}"
    driver = setup_driver()

    print(f'正在访问专栏页面：{url} ...')
    driver.get(url)

    try:
        print(f'正在解析页面数据...')

        # 获取专栏名称
        title = driver.title

        # 根据 id=app 查找并等待元素加载成功
        WebDriverWait(driver, 10).until( EC.presence_of_element_located((By.ID, "app")) )

        # 获取 Icon 链接地址
        icon_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "img.avatar"))
        )
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

        # 获取标签列表以及主理人信息
        tags, author = get_tags_and_author(driver)

        # 获取佣金比例，要想获取到佣金比例数据，需要点击 div.share-paper 元素，点击后会在底部弹出一个模态对话框，里面有推广佣金比例信信息，
        commission_rate = get_commission_rate(driver)

        data = {
            "title": title,
            "url": url,
            "author_id": author_id,
            "author": author,
            "icon": icon,
            "reader_count": int(reader_count),
            "article_count": int(article_count),
            "intro": intro,
            "commission_rate": commission_rate,
            "tags": tags,
        }

        import json
        print(f"解析完毕: {json.dumps(data, ensure_ascii=False, indent=4)}")
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
        "介绍": {"rich_text": [{"text": {"content": data["intro"]}}]},
        "订阅数": {"number": data["reader_count"]},
        "文章数": {"number": data["article_count"]},
        "佣金比例": {"number": data["commission_rate"]},
        "内容标签": {"multi_select": [{"name": tag} for tag in data["tags"]]},
        "同步时间": {"date": {"start": datetime.now(timezone.utc).isoformat()}}, # 注意这里要使用 UTC 时间
        "状态": {"status": {"name": "Done"}},
        }

    print(f"[Notion] 正在检查专栏 {author_id} 页面是否存在...")

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
        print(f"[Notion] 页面已存在, 执行更新操作")
        notion.pages.update(
            page_id=page_id,
            properties=properties
        )
    # 如果未找到该专栏 ID 的页面，则创建新页面
    else:
        print(f"[Notion] 页面不存在, 创建新页面.")
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
    print(f"[Notion] 保存成功")    


def save_to_file(data):
    # 获取当前日期并创建目录
    current_date = datetime.now().strftime("%Y-%m-%d")
    data_directory = f"./data/{current_date}"
    os.makedirs(data_directory, exist_ok=True)  # 创建目录，如果已存在则不报错

    # 生成文件路径
    file_path = os.path.join(data_directory, f"{data['author_id']}.json")
    
    # 将数据写入 JSON 文件，使用 'w' 模式覆盖文件
    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4)  # 写入 JSON 数据
    
    print(f"Saved to file: {file_path} successfully.")


def main():
    with open('authors.txt', 'r') as f:
        authors = f.read().splitlines()

    for author in authors:
        data = scrape_xiaobot(author)
        # 保存到本地文件
        save_to_file(data)
        # 保存到 Notion
        save_to_notion(data)

if __name__ == "__main__":
    main()
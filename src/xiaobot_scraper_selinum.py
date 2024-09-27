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
from selenium.common.exceptions import WebDriverException 

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

notion = Client(auth=NOTION_TOKEN)


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        '''
    })
    return driver

def get_commission_rate(driver):
    # 获取佣金比例，要想获取到佣金比例数据，需要点击 div.share-paper 元素，点击后会在底部弹出一个模态对话框，里面有推广佣金比例信信息，
    share_paper_elem = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".share-paper"))
    )

    # 移除页面中的 div.bottom_fixed 元素，这个元素会遮挡住 share-paper 元素
    bottom_fixed_elem =  WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "bottom_fixed"))
    )
    driver.execute_script("arguments[0].remove();", bottom_fixed_elem)

    # span.text-theme 是推广佣金比例信息，如果找不到，就点击 share-paper 元素
    if not driver.find_elements(By.CSS_SELECTOR, "span.text-theme"):
        print(f"点击 share-paper 元素")
        share_paper_elem.location_once_scrolled_into_view  # 滚动到元素位置
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
    return int(commission_rate) / 100 if commission_rate else 0


def get_tags_and_author_and_last_update(driver):

    # category_elem 是标签栏，第一个标签内容为专栏描述内容，它是默认显示的。
    category_elem = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.category"))
    )

    # 获取专栏最后更新时间
    # 查找所有 .post 元素，排除带有 .pin_label 的元素，取第一个元素的 .date 作为最后更新时间。如果没有剩余元素，则使用带有 .pin_label 的元素的 .date 作为最后更新时间。
    posts_elem = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".posts"))
    )
    posts = posts_elem.find_elements(By.CSS_SELECTOR, ".post")
    for post in posts:
        if not post.find_elements(By.CSS_SELECTOR, ".pin_label"):
            last_update_elem = post.find_element(By.CSS_SELECTOR, ".date")
            break
    else:
        last_update_elem = posts[0].find_element(By.CSS_SELECTOR, ".date")
    last_update = last_update_elem.text # '2024/01/02'
    last_update = last_update if last_update else None
    # # 转换为 date 类型
    # NOTE：这里转换为 datetime 后，json 序列化时出错，所以保持字符串格式
    # last_update = datetime.strptime(last_update, '%Y/%m/%d').date() if last_update else None

    # 获取标签列表，如果找不到 tags, 就点击 category_elem 下的第二个元素
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

    return tags, author, last_update


def scrape_xiaobot(author_id):
    url = f"https://xiaobot.net/p/{author_id}"
    driver = setup_driver()

    print(f'正在获取专栏页面数据：{url} ...')
    try:
        driver.get(url)
        time.sleep(5)  # 等待页面加载
    except WebDriverException as e:
        print(f"打开专栏页面时发生错误: {e}")
        driver.quit()
        return None
    except Exception as e:
        print(f"发生未知错误: {e}")
        driver.quit()
        return None

    try:
        print(f'正在解析页面数据...')

        # 专栏名称
        title = driver.title

        # 根据 id=app 查找并等待元素加载成功
        WebDriverWait(driver, 10).until( 
            EC.presence_of_element_located((By.ID, "app")) 
        )

        # 获得详细介绍
        description_elem = WebDriverWait(driver, 10).until( 
            EC.presence_of_element_located((By.CSS_SELECTOR, ".description")) 
        )
        print('description: ', description_elem.get_attribute('innerHTML'))
        description = description_elem.get_attribute('innerHTML')


        # 头像地址
        avatar_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".paper-info img.avatar"))
        )
        avatar = avatar_elem.get_attribute("src")

        # 获取阅读人数
        reader_count_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".paper-info .stats div.stat:nth-child(1) .num"))
        )
        reader_count = reader_count_elem.text

        # 获取文章数
        article_count_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".paper-info .stats div.stat:nth-child(2) .num"))
        )
        article_count = article_count_elem.text

        # 获取描述
        intro_elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".paper-info p.intro"))
        )
        intro = intro_elem.text

        # 获取标签列表以及主理人信息
        tags, author, last_update = get_tags_and_author_and_last_update(driver)

        # 获取佣金比例，要想获取到佣金比例数据，需要点击 div.share-paper 元素，点击后会在底部弹出一个模态对话框，里面有推广佣金比例信信息，
        commission_rate = get_commission_rate(driver)

        data = {
            "title": title,
            "url": url + "?refer=f45527a5-d021-4bc8-958b-f28d2e90e7f7",
            "author_id": author_id,
            "author": author,
            "avatar": avatar,
            "reader_count": int(reader_count),
            "article_count": int(article_count),
            "intro": intro,
            "description": description,
            "commission_rate": commission_rate,
            "last_update": last_update,
            "tags": tags,
        }

        import json
        print(f"解析完毕: {json.dumps(data, ensure_ascii=False, indent=4)}")
        return data
    finally:
        driver.quit()


def save_to_notion(data):
    author_id = data["author_id"]
    cover = { "external": { "url": data["avatar"] } }
    properties = {
        # 带链接地址的名称
        "名称": {
            "title": [
                {
                    "text": {
                        "content": data["title"],
                        "link": { "url": data["url"] }
                    }
                }
            ]
        },
        "链接": {"url": data["url"]},
        "头像": {"url": data["avatar"]},
        "专栏 ID": {"rich_text": [{"text": {"content": author_id}}]},
        "主理人": {"rich_text": [{"text": {"content": data["author"]}}]},
        "介绍": {"rich_text": [{"text": {"content": data["intro"]}}]},
        "订阅数": {"number": data["reader_count"]},
        "文章数": {"number": data["article_count"]},
        "佣金比例": {"number": data["commission_rate"]},
        "内容标签": {"multi_select": [{"name": tag} for tag in data["tags"]]},
        "同步时间": {
            "date": {
                "start": datetime.now(timezone.utc).isoformat() # 使用 UTC 时间
            }
        },
        "专栏最近更新时间": {
            "date": {
                "start": data["last_update"].replace("/", "-") # ISO 8601
            }
        },
        "同步状态": {"status": {"name": "Done"}},
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
            cover=cover,
            icon=cover,
            properties=properties
        )
    # 如果未找到该专栏 ID 的页面，则创建新页面
    else:
        print(f"[Notion] 页面不存在, 创建新页面.")
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            cover=cover,
            icon=cover,
            properties=properties,
            children=[
                {
                    "object": "block",
                    "type": "image",
                    "image": { "external": { "url": data["avatar"] } }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "text": [{"text": {"content": data["description"]}}]
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
        # 忽略空行
        authors = [author for author in f.read().splitlines() if author.strip()]

    for author in authors:
        data = scrape_xiaobot(author)

        if data:
            # 保存到本地文件
            save_to_file(data)
            # 保存到 Notion
            save_to_notion(data)

        print(f"等待 10 秒...")
        time.sleep(10)

if __name__ == "__main__":
    main()
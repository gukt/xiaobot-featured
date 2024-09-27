import os
import time
import random
import json
import hashlib
from datetime import datetime, timezone
from collections import OrderedDict
import requests
from notion_client import Client
from bs4 import BeautifulSoup

# TODO 研究如何让 Cursor 编辑器使用 Black 格式化代码？
# TODO 是不是 Python 的函数之间要空两行？
# TODO 保存 Notion 文章时，不需要在内容中加入 cover，因为 cover 和 icon 已经定义了封面
# TODO 添加对价格字段的填充
# TODO Notion 中如何存储两个价格？

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

notion = Client(auth=NOTION_TOKEN)


def md5_hash(t: str, e: str = 'hex') -> str:
    md5 = hashlib.md5()
    md5.update(t.encode('utf-8'))
    if e == 'hex':
        return md5.hexdigest()
    elif e == 'binary':
        return md5.digest()
    else:
        raise ValueError("Unsupported hash format. Use 'hex' or 'binary'.")

def get_sign(query: dict, t: int) -> str:
    # Sort the dictionary by keys
    sorted_query = OrderedDict(sorted(query.items()))
    
    # Create the query string
    query_string = "&".join([f"{k}={v}" for k, v in sorted_query.items() if v is not None])
    
    # Append the secret key and timestamp
    secret_key = "dbbc1dd37360b4084c3a69346e0ce2b2"
    sign_string = f"{query_string}{secret_key}.{t}"
    
    # Generate and return the hash
    return md5_hash(sign_string)


def make_headers(query: dict = {}):
    """
    生成请求头
    """
    timestamp = int(time.time())
    headers = {
        'Sign': get_sign(query, timestamp),
        'Timestamp': str(timestamp),
        'Api-Key': os.environ.get("XIAOBOT_API_KEY"),
        'App-Version': os.environ.get("XIAOBOT_APP_VERSION"),
        # "Referer": "https://xiaobot.net/",
        # 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    }
    print(f"生成请求头: {headers}")
    return headers

def http_get(url, query):
    """
    发送 GET 请求
    """
    try:
        response = requests.get(url, headers=make_headers(query), params=query)
        response.raise_for_status()
        result = response.json()    
        print(f"GET {url}, Query: {query}, Response: {result}")
        if result['code'] != 200:
            raise Exception(result['message'])
        return result['data']
    except requests.RequestException as e:
        print(f"发送 GET 请求时发生错误: URL: {url}, Query: {query}, Error: {e}")
        return None


def fetch_tags(author_id) -> list[str] | None:
    """
    获取专栏标签
    """
    url = f'https://api.xiaobot.net/paper/{author_id}/tag'
    try:
        data = http_get(url, {})
        return [tag['name'] for tag in data]
    except (requests.RequestException, Exception) as e:
        print(f"获取标签数据时生错误: {e}")
        return None


def fetch_description(author_id) -> str | None:
    """
    获取专栏描述
    """
    url = f'https://api.xiaobot.net/paper/{author_id}/post/description'
    try:
        data = http_get(url, {})
        return data['content']
    except (requests.RequestException, Exception) as e:
        print(f"获取专栏描述数据时发生错误: {e}")
        return None
    

def fetch_recent_updated_at(author_id) -> str | None:
    """
    获取专栏最后更新时间（即最近一篇文章的创建时间）
    """
    url = f'https://api.xiaobot.net/paper/{author_id}/post'
    query = {
        "limit": 20,
        "offset": 0,
        "tag_name": "",
        "keyword": "",
        "order_by": "created_at+desc"
    }
    try:
        data = http_get(url, query)
        # 遍历每个元素的 created_at 属性���找出时间最近的时间返回
        latest_post = min(data, key=lambda x: x['created_at'])
        return latest_post['created_at']
    except (requests.RequestException, Exception) as e:
        print(f"获取专栏最后更新时间时发生错误: {e}")
        return None


def scrape_xiaobot(author_id) -> dict:
    """
    获取专栏数据
    """
    url = f'https://api.xiaobot.net/paper/{author_id}'
    query = {"refer_channel": ''}
    try:
        # 获取专栏基本数据
        print(f'正在获取专栏数据：{url} ...')
        data = http_get(url, query)

        # 获取标签
        data['tags'] = fetch_tags(author_id)

        # 获取专栏描述
        data['description'] = fetch_description(author_id)

        # 获取专栏最后更新时间
        data['recent_updated_at'] = fetch_recent_updated_at(author_id)

        print(f"解析完毕: {json.dumps(data, ensure_ascii=False, indent=4)}")
        return data
    except requests.RequestException as e:
        print(f"获取专栏数据时发生错误: {e}")
        return None

def save_to_notion(data):
    """
    保存到 Notion
    """
    author_id = data["slug"]
    refer_id = "f45527a5-d021-4bc8-958b-f28d2e90e7f7"
    # 专栏 URL
    channel_url = f"https://xiaobot.net/p/{author_id}?refer={refer_id}"
    channel_name = data.get("name", "")
    tags = data.get("tags", [])
    
    external_avatar = { "external": { "url": data["avatar_url"] } }
    # 将 HTML 转换为 Notion 块
    page_content = html_to_notion_blocks(data["description"])
    
    properties = {
        "名称": {
            "title": [
                {
                    "text": {
                        "content": channel_name,
                        "link": { "url": channel_url }
                    }
                }
            ]
        },
        "链接": {"url": channel_url},
        "头像": {"url": data["avatar_url"]},
        "ID": {"rich_text": [{"text": {"content": author_id}}]},
        "主理人": {"rich_text": [
            {"text": {"content": data["creator"]["nickname"]}},
        ]},
        "简介": {"rich_text": [
            {"text": {"content": data.get("intro", "")}},
        ]},
        "订阅数": {"number": data.get("subscriber_count", 0)},
        "文章数": {"number": data.get("post_count", 0)},
        "免费文章数": {"number": data.get("free_post_count", 0)},
        "佣金比例": {"number": data.get("refer_ratio", 0)},
        "内容标签": {"multi_select": [{"name": tag} for tag in tags]},
        "同步时间": {
            "date": {
                "start": datetime.now(timezone.utc).isoformat()
            }
        },
        "创建时间": { "date": { "start": data["created_at"] } },
        "同步状态": {"status": {"name": "Done"}},
        "分类": {"select": {"name": data["type"]}},
        "价格": {"number": data["prices"][0]["price"] / 100},
        "价格类型": {"select": {"name": data["prices"][0]["name"]}},
    }

    print(f"[Notion] 正在检查专栏 {author_id} 页面是否存在...")

    existing_page = notion.databases.query(
        database_id=NOTION_DATABASE_ID,
        filter={
            "property": "ID",
            "rich_text": {
                "equals": author_id
            }
        }
    )
    if existing_page["results"]:
        page_id = existing_page["results"][0]["id"]
        print(f"[Notion] 页面已存在, 执行更新操作")
        notion.pages.update(
            page_id=page_id,
            cover=external_avatar,
            icon=external_avatar,
            properties=properties,
            children=page_content,
        )
    else:
        print(f"[Notion] 页面不存在, 创建新页面.")
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            cover=external_avatar,
            icon=external_avatar,
            properties=properties,
            children=page_content,
        )
    print(f"[Notion] 保存成功")    

def save_to_file(data):
    """
    保存到本地文件
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    data_directory = f"./data/{current_date}"
    os.makedirs(data_directory, exist_ok=True)

    file_path = os.path.join(data_directory, f"{data['slug']}.json")
    
    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4)
    
    print(f"Saved to file: {file_path} successfully.")

def html_to_notion_blocks(html_content) -> list[dict]:
    """
    将 HTML 转换为 Notion 块。
    注意：Notion API 最多支持 100 个块，多余的要截取。
    """
    if not html_content:
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    blocks = []

    for element in soup.find_all(['h1', 'h2', 'h3', 'p', 'img', 'ul']):
        # 排除掉 p 标签在 ul 标签中的情况
        if element.name == 'p' and element.find_parents('ul'):
            continue

        if element.name == 'h1':
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"type": "text", "text": {"content": element.get_text()}}]
                }
            })
        elif element.name == 'h2':
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": element.get_text()}}]
                }
            })
        elif element.name == 'h3':
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": element.get_text()}}]
                }
            })
        elif element.name == 'p':
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": element.get_text()}}]
                }
            })
        elif element.name == 'img':
            blocks.append({
                "object": "block",
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {
                        "url": element.get('src', '')
                    }
                }
            })
        elif element.name == 'ul':
            list_items = []
            for li in element.find_all('li'):
                list_items.append({
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": li.get_text()}}]
                    }
                })
            blocks.extend(list_items)

    # 限制块数为 100
    return blocks[:100]

def main():
    """
    主函数
    """
    with open('authors.txt', 'r') as f:
        authors = [author for author in f.read().splitlines() if author.strip()]

    for author in authors:
        data = scrape_xiaobot(author)

        if data:
            save_to_file(data)
            try:
                save_to_notion(data)
            except Exception as e:
                print(f"保存到 Notion 时发生错误: {e}")

        # 等待随机的 5-10 秒
        wait_time = random.uniform(5, 10)
        print(f"等待 {wait_time:.2f} 秒...")
        time.sleep(wait_time)

if __name__ == "__main__":
    main()
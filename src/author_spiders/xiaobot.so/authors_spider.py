import scrapy
import re
from scrapy.crawler import CrawlerProcess

class AuthorsSpider(scrapy.Spider):
    name = 'authors_spider'
    start_urls = ['https://www.xiaobot.so/all/1']
    
    def parse(self, response):
        # 遍历专栏详情链接
        for link in response.css('.xbt-body-content-list a::attr(href)'):
            print(link)
            from scrapy.shell import inspect_response
            inspect_response(link, self)

            yield response.follow(link, self.parse_author)
        
        # 查找下一页
        current_page = response.css('.pagination a::text').get()
        next_page_index = int(current_page) + 1
        next_page_url = response.css(f'.pagination a:has-text({next_page_index})::attr(href)').get()
        if next_page_url is not None:
            print(next_page_url)
            
            from scrapy.shell import inspect_response
            inspect_response(response, self)

            yield response.follow(next_page_url, self.parse)

    def parse_author(self, response):
        print('parse_author', response.url)
        from scrapy.shell import inspect_response
        inspect_response(response, self)
        # 提取作者ID
        author_link = response.css('.xbt-aside-column-price a::attr(href)').get()
        if author_link is not None:
            author_id = re.search(r'/p/(?P<id>[^?]+)', author_link)
            if author_id:
                print(author_id, author_id.group('id'))
                yield {'author_id': author_id.group('id')}

# class AuthorPipeline:
#     def open_spider(self, spider):
#         # 读取现有的authors.txt文件
#         try:
#             with open('authors.txt', 'r') as f:
#                 self.existing_authors = set(f.read().splitlines())
#         except FileNotFoundError:
#             self.existing_authors = set()
        
#         self.new_authors = set()

#     def process_item(self, item, spider):
#         author_id = item['author_id']
#         if author_id not in self.existing_authors:
#             self.new_authors.add(author_id)
#             spider.logger.info(f"新增作者: {author_id}")
#         return item

#     def close_spider(self, spider):
#         # 更新authors.txt文件
#         all_authors = self.existing_authors.union(self.new_authors)
#         with open('authors.txt', 'w') as f:
#             for author in sorted(all_authors):
#                 f.write(f"{author}\n")
        
#         spider.logger.info(f"总共新增了 {len(self.new_authors)} 个作者")
#         spider.logger.info(f"更新后的作者总数: {len(all_authors)}")

# # 配置和运行爬虫
# process = CrawlerProcess(settings={
#     'ITEM_PIPELINES': {'__main__.AuthorPipeline': 300},
# })

# process.crawl(XiaobotAuthorSpider)
# process.start()
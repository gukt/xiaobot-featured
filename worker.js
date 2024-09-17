addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

addEventListener('scheduled', event => {
  event.waitUntil(handleScheduled(event))
})

async function handleRequest(request) {
  // 处理 HTTP 请求的逻辑
  return new Response('Hello World')
}

async function handleScheduled(event) {
  // 这里调用你的爬虫逻辑
  await scrapeXiaobot()
  return new Response('Scraping completed')
}

async function scrapeXiaobot() {
  // 在这里实现你的爬虫逻辑
  // 你可能需要使用 fetch API 来获取作者列表和爬取数据
  // 然后使用 Notion API 来保存数据
}
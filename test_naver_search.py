import urllib.parse
import requests
from bs4 import BeautifulSoup

query = "정국 위블로 앰버서더"
encoded_query = urllib.parse.quote(query)
search_url = f"https://search.naver.com/search.naver?where=nexearch&query={encoded_query}"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

resp = requests.get(search_url, headers=headers)
soup = BeautifulSoup(resp.text, "html.parser")

# 블로그/인플루언서/웹/뉴스 등 스니펫 수집
snippets = []

# 제목과 본문을 포함하는 컨테이너들
containers = soup.select(".total_wrap.api_ani_send, .news_wrap.api_ani_send")
for c in containers:
    title_elem = c.select_one(".total_tit, .news_tit")
    desc_elem = c.select_one(".total_dsc, .news_dsc, .api_txt_lines.dsc_txt_wrap")
    if title_elem and desc_elem:
        title = title_elem.get_text(strip=True)
        desc = desc_elem.get_text(strip=True)
        snippets.append(f"제목: {title}\n내용: {desc}")

print(f"찾은 스니펫: {len(snippets)}")
for s in snippets[:5]:
    print("-" * 20)
    print(s)

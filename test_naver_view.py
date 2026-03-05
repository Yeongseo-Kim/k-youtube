import urllib.parse
import requests
from bs4 import BeautifulSoup

query = "정국 위블로 앰버서더"
encoded_query = urllib.parse.quote(query)
search_url = f"https://search.naver.com/search.naver?where=view&query={encoded_query}"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
}

resp = requests.get(search_url, headers=headers)
soup = BeautifulSoup(resp.text, "html.parser")

titles = soup.select(".title_link, .api_txt_lines.total_tit")
dscs = soup.select(".dsc_link, .api_txt_lines.dsc_txt, .total_dsc")

print(f"찾은 스니펫: len(titles)={len(titles)}, len(dscs)={len(dscs)}")
for t, d in zip(titles[:5], dscs[:5]):
    print("-" * 20)
    print(f"제목: {t.get_text(strip=True)}")
    print(f"내용: {d.get_text(strip=True)}")

import requests
from bs4 import BeautifulSoup
import time
from fastapi import FastAPI, BackgroundTasks
from typing import List

app = FastAPI()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
}

# دالة سحب محتوى فصل واحد
def fetch_chapter_data(novel_slug: str, chapter_num: int):
    url = f"https://rewayat.club/novel/{novel_slug}/{chapter_num}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # استخراج العنوان
            title_tag = soup.find('div', class_='v-card__subtitle')
            chapter_title = title_tag.get_text(strip=True) if title_tag else f"فصل {chapter_num}"
            
            # استخراج المحتوى
            paragraphs = soup.find_all('p')
            clean_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text()) > 30]
            content = "\n\n".join(clean_paragraphs)
            
            return {"chapter": chapter_num, "title": chapter_title, "content": content}
    except Exception as e:
        print(f"Error in chapter {chapter_num}: {e}")
    return None

# Endpoint لجلب فصل واحد مباشرة (للتجربة من التطبيق)
@app.get("/fetch-chapter/{novel_slug}/{chapter_num}")
async def get_chapter(novel_slug: str, chapter_num: int):
    data = fetch_chapter_data(novel_slug, chapter_num)
    if data:
        return data
    return {"error": "Could not fetch chapter"}

# Endpoint لجلب معلومات الرواية الأساسية (صورة، عنوان، وصف)
@app.get("/novel-info/{novel_slug}")
async def get_novel_info(novel_slug: str):
    url = f"https://rewayat.club/novel/{novel_slug}"
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # استخراج البيانات الأساسية (بناءً على بنية الموقع)
    title = soup.find('h1').get_text(strip=True) if soup.find('h1') else novel_slug
    # ملاحظة: استخراج الصورة والوصف يعتمد على الكلاسات الحالية في الموقع
    
    return {
        "title": title,
        "slug": novel_slug,
        "source": "نادي الروايات"
    }

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

import os
import json
import time
import threading
import requests
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
from datetime import datetime

# ==========================================
# إعدادات التطبيق
# ==========================================
app = Flask(__name__)
CORS(app)

# مفتاح سري لحماية الرابط
API_SECRET = os.environ.get('API_SECRET', 'Zeusndndjddnejdjdjdejekk29393838msmskxcm9239484jdndjdnddjj99292938338zeuslojdnejxxmejj82283849')

# رابط الخادم الرئيسي (Node.js)
NODE_BACKEND_URL = os.environ.get('NODE_BACKEND_URL', 'https://c-production-3db6.up.railway.app')

# ==========================================
# أدوات السحب (Scraper Tools)
# ==========================================

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ar,en-US;q=0.7,en;q=0.3'
    }

def extract_from_nuxt(soup):
    """استخراج رابط الصورة من بيانات Nuxt الخام (الأكثر دقة)"""
    try:
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'window.__NUXT__' in script.string:
                content = script.string
                # البحث عن poster_url أو poster
                match = re.search(r'poster_url:"(.*?)"', content)
                if not match:
                    match = re.search(r'poster:"(.*?)"', content)
                
                if match:
                    raw_url = match.group(1)
                    # فك تشفير الرابط
                    clean_url = raw_url.encode('utf-8').decode('unicode_escape')
                    return clean_url
    except Exception as e:
        print(f"Error extracting from Nuxt: {e}")
    return None

def extract_background_image(style_str):
    """استخراج الرابط من ستايل background-image"""
    if not style_str: return ''
    clean_style = style_str.replace('&quot;', '"').replace("&#39;", "'")
    match = re.search(r'url\s*\((.*?)\)', clean_style, re.IGNORECASE)
    if match:
        url = match.group(1).strip()
        url = url.strip('"\'')
        return url
    return ''

def is_valid_tag(text):
    """التحقق مما إذا كان النص تصنيفاً صالحاً"""
    text = text.strip()
    if not text: return False
    if text in ['مكتملة', 'متوقفة', 'مستمرة', 'مترجمة', 'رواية', 'عمل']: return False
    clean_text = text.replace(',', '').replace('.', '').replace('x', '').strip()
    if clean_text.isdigit(): return False
    if re.search(r'^\d+\s*x$', text, re.IGNORECASE): return False 
    if not re.search(r'[\u0600-\u06FF]', text): return False
    return True

def fix_image_url(url):
    """إصلاح الرابط النسبي وإضافة النطاق الصحيح"""
    if not url: return ""
    base_api_url = 'https://api.rewayat.club'
    if url.startswith('//'):
        return 'https:' + url
    elif url.startswith('/'):
        return base_api_url + url
    elif not url.startswith('http'):
        return base_api_url + '/' + url
    return url

def fetch_novel_metadata_html(url):
    """جلب معلومات الرواية من HTML الصفحة مباشرة"""
    try:
        print(f"📡 Fetching metadata from HTML: {url}")
        response = requests.get(url, headers=get_headers(), timeout=15)
        if response.status_code != 200:
            print(f"❌ HTTP Error: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Title
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"
        
        # 2. Cover
        cover_url = ""
        nuxt_image = extract_from_nuxt(soup)
        if nuxt_image:
            cover_url = nuxt_image
        
        if not cover_url:
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                cover_url = og_image["content"]
        
        if not cover_url:
            img_div = soup.find('div', class_='v-image__image--cover')
            if img_div and img_div.has_attr('style'):
                cover_url = extract_background_image(img_div['style'])
        
        cover_url = fix_image_url(cover_url)

        # 3. Description
        desc_div = soup.find(class_='text-pre-line') or soup.find('div', class_='v-card__text')
        description = desc_div.get_text(strip=True) if desc_div else ""
        
        # 4. Status & Category
        status = "مستمرة"
        tags = []
        category = "عام"
        
        chip_groups = soup.find_all(class_='v-chip-group')
        target_chips = []
        if chip_groups:
            for group in chip_groups[:2]: 
                target_chips.extend(group.find_all(class_='v-chip__content'))
        else:
            target_chips = soup.find_all(class_='v-chip__content')

        for chip in target_chips:
            text = chip.get_text(strip=True)
            if text in ['مكتملة', 'متوقفة', 'مستمرة']:
                status = text
            elif is_valid_tag(text):
                tags.append(text)
        
        tags = list(set(tags))
        if tags:
            category = tags[0]

        # 5. Total Chapters
        total_chapters = 0
        all_text = soup.get_text()
        chapter_match = re.search(r'الفصول\s*\((\d+)\)', all_text)
        if chapter_match:
            total_chapters = int(chapter_match.group(1))
        else:
            tabs = soup.find_all(class_='v-tab')
            for tab in tabs:
                tab_text = tab.get_text(strip=True)
                if "الفصول" in tab_text:
                    match = re.search(r'\((\d+)\)', tab_text)
                    if match:
                        total_chapters = int(match.group(1))
                        break
        
        return {
            'title': title,
            'description': description,
            'cover': cover_url,
            'status': status,
            'tags': tags,
            'category': category,
            'total_chapters': total_chapters
        }

    except Exception as e:
        print(f"❌ Error scraping metadata: {e}")
        return None

def scrape_chapter_content_html(novel_url, chapter_num):
    """سحب نص الفصل"""
    url = f"{novel_url.rstrip('/')}/{chapter_num}"
    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        if response.status_code != 200:
            return None, None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        paragraphs = soup.find_all('p')
        clean_paragraphs = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20]
        
        if clean_paragraphs:
            text_content = "\n\n".join(clean_paragraphs)
        else:
            content_div = soup.find('div', class_='pre-formatted') or soup.find('div', class_='v-card__text')
            if content_div:
                text_content = content_div.get_text(separator="\n\n", strip=True)
            else:
                return None, None
            
        if len(text_content.strip()) < 50:
            return None, None

        title_tag = soup.find(class_='v-card__subtitle') or soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else f"الفصل {chapter_num}"
        title = re.sub(r'^\d+\s*-\s*', '', title)

        return title, text_content
            
    except Exception as e:
        print(f"Error scraping chapter {chapter_num}: {e}")
        return None, None

def send_data_to_backend(payload):
    """إرسال البيانات إلى الخادم الرئيسي Node.js"""
    try:
        endpoint = f"{NODE_BACKEND_URL}/api/scraper/receive"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': API_SECRET,
            'x-api-secret': API_SECRET
        }
        response = requests.post(endpoint, json=payload, headers=headers, timeout=60)
        
        if response.status_code == 200:
            print("✅ Data sent to backend successfully.")
            return True
        else:
            print(f"❌ Backend Error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to send data to backend: {e}")
        return False

# ==========================================
# دالة الخلفية المعدلة (تدعم إكمال النواقص)
# ==========================================
def background_worker(url, admin_email, author_name, start_from=1, update_info=True):
    """الوظيفة التي تعمل في الخلفية"""
    print(f"🚀 Starting Scraper for: {url} | Start Chapter: {start_from} | Update Info: {update_info}")
    
    # 1. جلب البيانات الوصفية للرواية
    metadata = fetch_novel_metadata_html(url)
    if not metadata:
        print("❌ Failed to fetch metadata")
        send_data_to_backend({'adminEmail': admin_email, 'error': 'فشل في جلب بيانات الرواية (تأكد من الرابط)'})
        return

    print(f"📖 Found Novel: {metadata['title']} ({metadata['total_chapters']} Chapters)")

    # 2. إرسال البيانات الوصفية (Initial Payload)
    # نرسلها فقط إذا كنا نبدأ من البداية ونريد التحديث الكامل.
    # إذا كنا نكمل النواقص، نتخطى هذه الخطوة لمنع الكتابة فوق الصورة/الوصف القديم في الباك اند.
    if start_from == 1 and update_info:
        init_payload = {
            'adminEmail': admin_email,
            'novelData': metadata,
            'chapters': [] 
        }
        if not send_data_to_backend(init_payload):
            print("❌ Stopping execution because initial handshake failed.")
            return
    else:
        print(f"ℹ️ Skipping initial metadata push (Start From: {start_from}).")

    # 3. حلقة سحب الفصول وإرسالها على دفعات (Batches)
    total = metadata['total_chapters']
    if total == 0:
        total = 2000 # احتياط
        
    batch_size = 5 
    current_batch = []

    # نبدأ الحلقة من start_from بدلاً من 1
    for num in range(start_from, total + 1):
        chap_title, content = scrape_chapter_content_html(url, num)
        
        if content:
            chapter_data = {
                'number': num,
                'title': chap_title,
                'content': content
            }
            current_batch.append(chapter_data)
            print(f"📄 Scraped Chapter {num}")
        else:
            print(f"⚠️ Failed to scrape content for Ch {num}")

        if len(current_batch) >= batch_size or num == total:
            if current_batch:
                print(f"📤 Sending batch of {len(current_batch)} chapters...")
                payload = {
                    'adminEmail': admin_email,
                    'novelData': metadata, 
                    'chapters': current_batch,
                    'isUpdate': (start_from > 1) # علامة للباك اند أن هذا تحديث
                }
                send_data_to_backend(payload)
                current_batch = [] 
                time.sleep(1) 

    print("✨ Scraping Task Completed Successfully!")

# ==========================================
# نقاط النهاية (Endpoints)
# ==========================================

@app.route('/', methods=['GET'])
def health_check():
    return "ZEUS Scraper Service (Relay Mode - Update Supported) is Running ⚡", 200

@app.route('/scrape', methods=['POST'])
def trigger_scrape():
    auth_header = request.headers.get('Authorization')
    if auth_header != API_SECRET:
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.json
    if not data:
        return jsonify({'message': 'No data provided'}), 400
        
    url = data.get('url')
    admin_email = data.get('adminEmail')
    author_name = data.get('authorName', 'ZEUS Bot')
    
    # استقبال خيارات التحديث وإكمال النواقص
    # الافتراضي يبدأ من 1 ويحدث كل شيء
    start_from = int(data.get('startFrom', 1))
    
    # إذا بدأنا من 1، فالافتراضي تحديث المعلومات، غير ذلك الافتراضي عدم التحديث
    default_update = True if start_from == 1 else False
    update_info = data.get('updateInfo', default_update)

    if not url or 'rewayat.club' not in url:
        return jsonify({'message': 'Invalid URL. Must be from rewayat.club'}), 400

    # بدء العمل في الخلفية مع المعاملات الجديدة
    thread = threading.Thread(target=background_worker, args=(url, admin_email, author_name, start_from, update_info))
    thread.daemon = True 
    thread.start()

    return jsonify({
        'message': f'تم بدء العملية من الفصل {start_from}.',
        'status': 'started'
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

import os
import json
import time
import threading
import requests
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
from pymongo import MongoClient
import certifi
from datetime import datetime

# ==========================================
# إعدادات التطبيق
# ==========================================
app = Flask(__name__)
CORS(app)

# مفتاح سري لحماية الرابط
API_SECRET = os.environ.get('API_SECRET', 'Zeusndndjddnejdjdjdejekk29393838msmskxcm9239484jdndjdnddjj99292938338zeuslojdnejxxmejj82283849')

# ==========================================
# إعداد قواعد البيانات
# ==========================================

# 1. MongoDB Setup
MONGO_URI = os.environ.get('MONGODB_URI')
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        mongo_db = mongo_client['zeus'] 
        novels_collection = mongo_db['novels']
        print("✅ Connected to MongoDB")
    except Exception as e:
        print(f"❌ MongoDB Connection Error: {e}")
else:
    print("⚠️ MONGODB_URI not found in env vars")

# 2. Firebase Setup
FIREBASE_KEY = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
firestore_db = None
if FIREBASE_KEY:
    try:
        # تنظيف النص بشكل شامل
        firebase_key_cleaned = FIREBASE_KEY.strip()
        # إزالة أي BOM أو أحرف خفية
        firebase_key_cleaned = firebase_key_cleaned.encode('utf-8').decode('utf-8-sig')
        # تحويل إلى JSON
        cred_dict = json.loads(firebase_key_cleaned)
        
        # إصلاح المفتاح الخاص بشكل دقيق
        if 'private_key' in cred_dict:
            private_key = cred_dict['private_key']
            private_key = private_key.replace('\\n', '\n')
            lines = private_key.split('\n')
            cleaned_lines = []
            for line in lines:
                if '-----BEGIN' in line or '-----END' in line:
                    cleaned_lines.append(line.strip())
                else:
                    cleaned_line = line.strip().replace(' ', '').replace('\t', '')
                    if cleaned_line:
                        cleaned_lines.append(cleaned_line)
            cred_dict['private_key'] = '\n'.join(cleaned_lines)
        
        # تهيئة Firebase
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        firestore_db = firestore.client()
        print("✅ Connected to Firebase Firestore")
        
    except Exception as e:
        print(f"❌ Firebase Connection Error: {e}")
else:
    print("⚠️ FIREBASE_SERVICE_ACCOUNT not found in env vars")

# ==========================================
# أدوات السحب (Scraper Tools)
# ==========================================

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ar,en-US;q=0.7,en;q=0.3'
    }

def get_slug_from_url(url):
    """استخراج المعرف الفريد للرواية من الرابط"""
    # Example: https://rewayat.club/novel/my-novel -> my-novel
    # Example: https://rewayat.club/novel/my-novel/ -> my-novel
    try:
        parts = url.rstrip('/').split('/novel/')
        if len(parts) > 1:
            return parts[1].split('/')[0]
    except:
        pass
    return None

def extract_background_image(style_str):
    """استخراج الرابط من ستايل background-image"""
    if not style_str: return ''
    match = re.search(r'url\(&quot;(.*?)&quot;\)', style_str)
    if not match:
        match = re.search(r'url\("(.*?)"\)', style_str)
    if not match:
        match = re.search(r'url\((.*?)\)', style_str)
    return match.group(1) if match else ''

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
        img_div = soup.find('div', class_='v-image__image--cover')
        if img_div and img_div.has_attr('style'):
            cover_url = extract_background_image(img_div['style'])
            
        # 3. Description
        desc_div = soup.find(class_='text-pre-line')
        description = desc_div.get_text(strip=True) if desc_div else ""
        
        # 4. Status & Category
        # البحث عن الشارات (Chips)
        chips = soup.find_all(class_='v-chip__content')
        status = "مستمرة"
        tags = []
        category = "عام"
        
        for chip in chips:
            text = chip.get_text(strip=True)
            if text in ['مكتملة', 'متوقفة', 'مستمرة']:
                status = text
            elif text not in ['مترجمة', 'رواية']: # استبعاد الكلمات العامة
                tags.append(text)
        
        if tags:
            category = tags[0]

        # 5. Total Chapters (Critical for loop)
        total_chapters = 0
        # البحث عن نص مثل "الفصول (220)"
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
    """سحب نص الفصل من صفحة الفصل مباشرة"""
    url = f"{novel_url.rstrip('/')}/{chapter_num}"
    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        if response.status_code != 200:
            return None, None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Content
        # البحث عن الكلاس المحدد في ملفات الـ HTML المرفقة
        content_div = soup.find('div', class_='pre-formatted')
        if not content_div:
            # محاولة بديلة
            content_div = soup.find('div', class_='v-card__text')
            
        if content_div:
            # تنظيف النص: استخراج الفقرات
            paragraphs = content_div.find_all('p')
            if paragraphs:
                text_content = "\n\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            else:
                # إذا لم تكن هناك وسوم P، خذ النص كاملاً
                text_content = content_div.get_text(separator="\n\n", strip=True)
        else:
            return None, None

        # 2. Title
        # عادة العنوان يكون في subtitle أو header
        title_div = soup.find(class_='v-card__subtitle')
        if not title_div:
            # محاولة الاستخراج من العنوان الرئيسي إذا فشل
            title_div = soup.find('h1')
            
        title = title_div.get_text(strip=True) if title_div else f"الفصل {chapter_num}"
        
        # تنظيف العنوان (إزالة الرقم إذا وجد، مثلا "1 - العنوان")
        title = re.sub(r'^\d+\s*-\s*', '', title)

        return title, text_content
            
    except Exception as e:
        print(f"Error scraping chapter {chapter_num}: {e}")
        return None, None

def background_worker(url, admin_email, author_name):
    """الوظيفة التي تعمل في الخلفية"""
    print(f"🚀 Starting HTML scraper for: {url}")
    
    # 1. جلب البيانات الوصفية
    metadata = fetch_novel_metadata_html(url)
    if not metadata:
        print("❌ Failed to fetch metadata from HTML")
        return

    print(f"📖 Found Novel: {metadata['title']} ({metadata['total_chapters']} Chapters)")

    # 2. تجهيز أو تحديث الرواية في MongoDB
    if novels_collection is not None:
        existing_novel = novels_collection.find_one({'title': metadata['title'], 'authorEmail': admin_email})
        
        novel_doc = {
            'title': metadata['title'],
            'description': metadata['description'],
            'cover': metadata['cover'],
            'author': author_name,
            'authorEmail': admin_email,
            'category': metadata['category'],
            'tags': metadata['tags'],
            'status': metadata['status'],
            'sourceUrl': url,
            'lastChapterUpdate': datetime.now()
        }

        if existing_novel:
            novel_id = existing_novel['_id']
            novels_collection.update_one({'_id': novel_id}, {'$set': novel_doc})
            print(f"🔄 Updated existing novel ID: {novel_id}")
        else:
            novel_doc['createdAt'] = datetime.now()
            novel_doc['chapters'] = []
            novel_doc['views'] = 0
            result = novels_collection.insert_one(novel_doc)
            novel_id = result.inserted_id
            print(f"🆕 Created new novel ID: {novel_id}")
    else:
        print("❌ MongoDB not connected, cannot save metadata.")
        return

    # 3. حلقة سحب الفصول (من 1 إلى العدد الكلي)
    total = metadata['total_chapters']
    if total == 0:
        print("⚠️ No chapters count found, trying first 100 blind...")
        total = 100

    # جلب الفصول الموجودة مسبقاً لتجنب التكرار
    current_novel = novels_collection.find_one({'_id': novel_id})
    existing_numbers = [c['number'] for c in current_novel.get('chapters', [])] if current_novel else []

    # إرسال إشعار أولي للباك إند (اختياري)
    # requests.post(...) 

    for num in range(1, total + 1):
        if num in existing_numbers:
            print(f"⏩ Skipping Ch {num} (Exists)")
            continue

        # سحب المحتوى
        chap_title, content = scrape_chapter_content_html(url, num)
        
        if content:
            print(f"✅ Scraped Ch {num}: {chap_title[:20]}...")
            
            try:
                # أ) الحفظ في Firebase (المحتوى)
                if firestore_db:
                    doc_ref = firestore_db.collection('novels').document(str(novel_id)).collection('chapters').document(str(num))
                    doc_ref.set({
                        'title': chap_title,
                        'content': content,
                        'lastUpdated': firestore.SERVER_TIMESTAMP
                    })

                # ب) التحديث في MongoDB (الميتا داتا)
                if novels_collection is not None:  # ✅ هذا هو التصحيح المطلوب
                    chapter_meta = {
                        'number': num,
                        'title': chap_title,
                        'createdAt': datetime.now(),
                        'views': 0
                    }
                    novels_collection.update_one(
                        {'_id': novel_id},
                        {'$push': {'chapters': chapter_meta}}
                    )
                
                # تأخير بسيط لتجنب الحظر
                time.sleep(1.5)
                
            except Exception as e:
                print(f"❌ DB Save Error Ch {num}: {e}")
        else:
            print(f"⚠️ Failed to scrape content for Ch {num}")
            # إذا فشل فصلين متتاليين، ربما وصلنا للنهاية الحقيقية
            # يمكن إضافة منطق هنا للتوقف

    print("✨ Scraping Task Completed Successfully!")

# ==========================================
# نقاط النهاية (Endpoints)
# ==========================================

@app.route('/', methods=['GET'])
def health_check():
    return "ZEUS HTML Scraper Service is Running ⚡ v2.0", 200

@app.route('/scrape', methods=['POST'])
def trigger_scrape():
    auth_header = request.headers.get('Authorization')
    if auth_header != API_SECRET:
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.json
    url = data.get('url')
    admin_email = data.get('adminEmail')
    author_name = data.get('authorName', 'ZEUS Bot')

    if not url or 'rewayat.club' not in url:
        return jsonify({'message': 'Invalid URL. Must be from rewayat.club'}), 400

    # تشغيل في الخلفية
    thread = threading.Thread(target=background_worker, args=(url, admin_email, author_name))
    thread.daemon = True 
    thread.start()

    return jsonify({
        'message': 'تم بدء عملية السحب (HTML mode).',
        'status': 'started'
    }), 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

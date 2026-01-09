const axios = require('axios');
const cheerio = require('cheerio');
const http = require('http');

/**
 * دالة جلب البيانات مع محاكاة متصفح كاملة لتجنب 403 و 500
 */
async function scrapeNovelChapter(url) {
    try {
        console.log(`[LOG] محاولة استخراج الفصل من: ${url}`);

        // الرؤوس (Headers) ضرورية جداً لإقناع السيرفر أنك متصفح حقيقي وليس كود برمجي
        const config = {
            timeout: 15000,
            headers: {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Referer': 'https://rewayat.club/',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Upgrade-Insecure-Requests': '1'
            }
        };

        const response = await axios.get(url, config);
        const html = response.data;
        const $ = cheerio.load(html);

        // --- استخراج البيانات ---
        
        // 1. العنوان
        let title = $('title').text().replace('- نادي الروايات', '').trim();
        if (!title || title === "Server error") {
            title = $('h1').first().text().trim() || "عنوان غير معروف";
        }

        // 2. المحتوى (تعديل بناءً على الـ HTML المرسل)
        // نادي الروايات يضع النص غالباً داخل عناصر تنتمي لـ v-application
        let content = '';
        
        // استهداف الحاوية التي تحتوي على النص (جربنا كلاسات متعددة)
        let contentArea = $('.chapter-content, .content, main, article, .v-main__wrap').find('p');
        
        if (contentArea.length > 0) {
            contentArea.each((i, el) => {
                const text = $(el).text().trim();
                if (text) content += text + '\n\n';
            });
        } else {
            // محاولة أخيرة: البحث عن أكبر div يحتوي على نصوص
            content = $('div').filter(function() {
                return $(this).children('p').length > 3;
            }).first().text().trim();
        }

        // 3. رابط الفصل التالي
        let nextChapter = null;
        $('a').each((i, el) => {
            const linkText = $(el).text();
            if (linkText.includes('التالي') || linkText.includes('Next')) {
                const href = $(el).attr('href');
                if (href) {
                    nextChapter = href.startsWith('http') ? href : `https://rewayat.club${href}`;
                }
            }
        });

        console.log(`[SUCCESS] تم جلب: ${title}`);

        return {
            status: 'success',
            data: {
                title,
                content: content || "فشل استخراج النص، قد يكون المحتوى محمي أو بتنسيق مختلف.",
                nextChapter,
                source: url
            }
        };

    } catch (error) {
        console.error(`[ERROR] ${error.message}`);
        return {
            status: 'error',
            message: `فشل الجلب: ${error.message}`,
            hint: "إذا كان الخطأ 403، فالموقع محمي بـ Cloudflare ويتطلب Playwright أو Puppeteer."
        };
    }
}

// إنشاء السيرفر
const server = http.createServer(async (req, res) => {
    res.setHeader('Content-Type', 'application/json; charset=utf-8');

    // التعامل مع الروابط من خلال query parameter أو رابط افتراضي
    if (req.url.startsWith('/fetch')) {
        const target = "https://rewayat.club/novel/open-30000-simulations-every-day/1";
        const result = await scrapeNovelChapter(target);
        res.writeHead(200);
        res.end(JSON.stringify(result, null, 2));
    } else {
        res.writeHead(200);
        res.end(JSON.stringify({ message: "Welcome! Use /fetch to start scraping." }));
    }
});

const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
    console.log(`Scraper is active on port ${PORT}`);
});

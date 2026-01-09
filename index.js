const axios = require('axios');
const cheerio = require('cheerio');

// الرابط المستهدف لفصل معين من نادي الروايات
const targetUrl = 'https://rewayat.club/novel/open-30000-simulations-every-day/1';

async function scrapeRewayatChapter() {
    try {
        console.log(`[LOG] جاري محاولة استخراج الفصل من: ${targetUrl}`);

        // استخدام بروكسي بسيط لتجنب أي حظر IP محتمل
        const bridgeUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(targetUrl)}`;

        const response = await axios.get(bridgeUrl, {
            timeout: 30000,
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        });

        if (!response.data || !response.data.contents) {
            throw new Error("فشل الحصول على محتوى الصفحة.");
        }

        const html = response.data.contents;
        const $ = cheerio.load(html);

        // --- استخراج البيانات بناءً على هيكلية صفحة الفصل ---

        // 1. استخراج العنوان (يكون عادة في الـ title أو h1)
        const rawTitle = $('title').text().split('-')[0].trim();
        
        // 2. استخراج محتوى الفصل
        // الموقع يستخدم كلاسات Nuxt/Vuetify. الحاوية الرئيسية للنص غالباً ما تكون داخل 'v-application'
        // سنستهدف العناصر التي تحتوي على النص الفعلي للرواية
        let chapterBody = $('.chapter-content, .content, main, article').first();

        // إذا لم يجد الكلاسات الشهيرة، نبحث عن الحاوية التي تحتوي على أكبر قدر من الفقرات (p)
        if (chapterBody.length === 0) {
            chapterBody = $('div').filter(function() {
                return $(this).find('p').length > 5;
            }).first();
        }

        // --- تنظيف المحتوى ---
        // إزالة العناصر غير النصية مثل الأزرار، أيقونات SVG، التنبيهات، والقوائم الجانبية
        chapterBody.find('button, script, style, svg, .v-btn, .v-navigation-drawer, header, footer, .toasted-container').remove();

        let cleanText = '';
        
        // استخراج النصوص من الفقرات للحفاظ على التنسيق
        const paragraphs = chapterBody.find('p');
        if (paragraphs.length > 0) {
            paragraphs.each((i, el) => {
                const pText = $(el).text().trim();
                if (pText) cleanText += pText + '\n\n';
            });
        } else {
            // fallback في حال كانت الرواية ليست داخل وسوم p
            cleanText = chapterBody.text().replace(/\s\s+/g, '\n\n').trim();
        }

        // 3. استخراج رابط الفصل التالي
        // نبحث عن أزرار التنقل (عادة تحتوي على كلمة "التالي")
        let nextLink = $('a').filter(function() {
            const txt = $(this).text().toLowerCase();
            return txt.includes('التالي') || txt.includes('next');
        }).attr('href');

        const fullNextUrl = nextLink ? (nextLink.startsWith('http') ? nextLink : `https://rewayat.club${nextLink}`) : null;

        console.log(`[SUCCESS] تم استخراج: ${rawTitle}`);

        return {
            status: 'success',
            data: {
                title: rawTitle,
                content: cleanText,
                nextChapter: fullNextUrl,
                source: targetUrl
            }
        };

    } catch (error) {
        console.error(`[ERROR] ${error.message}`);
        return {
            status: 'error',
            message: error.message
        };
    }
}

// إعداد السيرفر للعرض
const http = require('http');
const server = http.createServer(async (req, res) => {
    res.setHeader('Content-Type', 'application/json; charset=utf-8');

    if (req.url === '/fetch') {
        const result = await scrapeRewayatChapter();
        res.writeHead(200);
        res.end(JSON.stringify(result, null, 2));
    } else {
        res.writeHead(200);
        res.end(JSON.stringify({ message: "استخدم المسار /fetch لجلب الفصل" }));
    }
});

server.listen(8080, () => {
    console.log('Scraper is active on port 8080');
});

const puppeteer = require('puppeteer');
const cheerio = require('cheerio');

const targetUrl = 'https://www.69shuba.com/txt/87906/39867326';

async function scrapeWithBrowser() {
    let browser;
    try {
        console.log(`[LOG] جاري تشغيل متصفح حقيقي لجلب البيانات...`);

        // تشغيل المتصفح مع إعدادات لتجاوز بيئة Docker في Railway
        browser = await puppeteer.launch({
            headless: "new",
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled' // إخفاء حقيقة أنه بوت
            ]
        });

        const page = await browser.newPage();

        // إعداد User-Agent بشري
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

        // الذهاب للرابط والانتظار حتى يستقر الشبكة
        await page.goto(targetUrl, { waitUntil: 'networkidle2', timeout: 60000 });

        // الحصول على محتوى الصفحة بعد تشغيل السكريبتات
        const html = await page.content();
        const $ = cheerio.load(html);

        // التحقق من النجاح
        const title = $('h1').last().text().trim();
        if (!title || html.includes('403 Forbidden')) {
            throw new Error('الموقع لا يزال يحجب الوصول حتى مع المتصفح الحقيقي.');
        }

        // تنظيف المحتوى
        $('.txtnav script, .txtnav .contentadv, .txtnav .txtinfo, .txtnav h1').remove();
        let content = $('.txtnav').text();
        content = content.replace(/\(本章完\)/g, '').replace(/\n\s*\n/g, '\n\n').trim();

        const nextUrl = $('.page1 a').last().attr('href');

        console.log(`[SUCCESS] تم السحب بواسطة المتصفح بنجاح! العنوان: ${title}`);
        
        return {
            status: 'success',
            title,
            content: content.substring(0, 500) + "...", // نرسل جزءاً فقط للتجربة
            nextUrl
        };

    } catch (error) {
        console.error(`[ERROR] فشل المتصفح: ${error.message}`);
        return { status: 'error', message: error.message };
    } finally {
        if (browser) await browser.close();
    }
}

// السيرفر
const http = require('http');
const server = http.createServer(async (req, res) => {
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    if (req.url === '/test') {
        const data = await scrapeWithBrowser();
        res.end(JSON.stringify(data, null, 2));
    } else {
        res.end(JSON.stringify({ message: 'Headless Browser Scraper is ready. Go to /test' }));
    }
});

const PORT = process.env.PORT || 8080;
server.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});

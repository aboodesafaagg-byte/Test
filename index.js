const axios = require('axios');
const cheerio = require('cheerio');
const iconv = require('iconv-lite');

// الرابط الذي أرسلته لي كنموذج للتجربة
const targetUrl = 'https://www.69shuba.com/txt/87906/39867326';

async function scrapeChapter() {
    try {
        console.log(`جاري جلب الفصل من: ${targetUrl}...`);

        // جلب الصفحة كمصفوفة بايتات (Buffer) لكي نتمكن من تحويل الترميز لاحقاً
        const response = await axios.get(targetUrl, {
            responseType: 'arraybuffer',
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
            }
        });

        // تحويل المحتوى من ترميز GBK إلى UTF-8 لكي يظهر النص الصيني صحيحاً
        const html = iconv.decode(response.data, 'gbk');
        const $ = cheerio.load(html);

        // 1. استخراج العنوان
        const title = $('h1').text().trim();

        // 2. استخراج المحتوى (تنظيف النص من الإعلانات والسكريبتات)
        // الموقع يضع النص داخل .txtnav، سنقوم بحذف العناصر غير المرغوبة
        $('.txtnav .contentadv').remove();
        $('.txtnav script').remove();
        $('.txtnav h1').remove();
        $('.txtnav .txtinfo').remove();

        // الحصول على النص المتبقي وتنظيف الفراغات الزائدة
        let content = $('.txtnav').text();
        
        // تنظيف بسيط للنص (إزالة الفراغات المكررة وكلمات النهاية)
        content = content.replace(/\(本章完\)/g, '')
                        .replace(/\n\s*\n/g, '\n\n')
                        .trim();

        // 3. استخراج رابط الفصل التالي (للسحب المستمر مستقبلاً)
        const nextChapterUrl = $('.page1 a').last().attr('href');

        console.log('--- نتيجة السحب التجريبي ---');
        console.log('العنوان:', title);
        console.log('رابط الفصل التالي:', nextChapterUrl);
        console.log('مقتطف من المحتوى:', content.substring(0, 200) + '...');
        console.log('-----------------------------');

        return { title, content, nextChapterUrl };

    } catch (error) {
        console.error('حدث خطأ أثناء السحب:', error.message);
    }
}

// تشغيل التجربة
scrapeChapter();

// إعداد خادم بسيط لكي يعمل على Railway ولا يتوقف
const http = require('http');
const server = http.createServer(async (req, res) => {
    if (req.url === '/test') {
        const data = await scrapeChapter();
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify(data, null, 2));
    } else {
        res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
        res.end('خادم سحب الروايات يعمل. اذهب إلى /test لرؤية التجربة.');
    }
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});

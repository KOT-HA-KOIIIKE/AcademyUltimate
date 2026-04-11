import os
import uuid
from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def analyze_page(source, is_url=True):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--remote-debugging-pipe")

    driver = webdriver.Chrome(options=options)
    report = []

    try:
        if is_url:
            driver.get(source)
        else:
            driver.get(f"file://{os.path.abspath(source)}")

        wait = WebDriverWait(driver, 10)

        # 1. Мета-описание
        meta_description = None
        try:
            meta = driver.find_element(By.CSS_SELECTOR, "meta[name='description']")
            meta_description = meta.get_attribute("content")
        except:
            meta_description = None

        # 2. Основной контейнер
        content = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.article-content_content"))
        )

        # 3. Курсив
        italic_elements = content.find_elements(By.TAG_NAME, "em")
        italic_texts = []
        for el in italic_elements:
            try:
                el.find_element(By.XPATH, "./ancestor::figcaption")
                continue
            except:
                pass
            text = el.text.strip()
            if text:
                italic_texts.append(text)

        # 4. Проверка текста на "Привет, Хабр"
        page_text = content.text
        has_habr_greeting = "Привет, Хабр" in page_text

        # 5. Проверка ссылок на Хабр
        links = content.find_elements(By.TAG_NAME, "a")
        habr_links = []
        for link in links:
            href = link.get_attribute("href") or ""
            text = link.text.strip()
            if "habr.com" in href:
                if not text: text = "[без текста]"
                habr_links.append(f"{text} | {href}")

        # 6. Проверка баннера
        promo_elements = content.find_elements(By.CSS_SELECTOR, "h2.promo-link_title")
        banner_exists = len(promo_elements) > 0

        # 7. Проверка блока "Читайте также"
        read_also_elements = content.find_elements(By.CSS_SELECTOR, "h5.read-also__articles-title")
        read_also_exists = len(read_also_elements) > 0

        # 8. Проверка ссылки "на полях"
        side_link_elements = content.find_elements(By.CSS_SELECTOR,
                                                   "a.columns-flex_right-link, a.columns-flex_big-link")
        side_link_exists = len(side_link_elements) > 0

        # 9. Сбор меток
        tag_elements = content.find_elements(By.CSS_SELECTOR, "a.tag.f-12")
        tags = [tag.text.strip() for tag in tag_elements if tag.text.strip()]

        # 10. Проверка изображений
        images = content.find_elements(By.TAG_NAME, "img")
        image_results = []
        for i, img in enumerate(images, start=1):
            alt = img.get_attribute("alt")
            src = img.get_attribute("src") or img.get_attribute("data-src")
            try:
                figure = img.find_element(By.XPATH, "./ancestor::figure[1]")
                figure_class = figure.get_attribute("class") or ""
                rounded = "✅ Есть скругление" if "is-style-rounded" in figure_class else "❌ Нет скругления"
            except:
                rounded = "❌ Нет скругления"
            alt_text = alt if alt and alt.strip() else "❌ alt отсутствует"
            image_results.append(f"{i}. {alt_text} | {src} | {rounded}")

        # 11. Проверка ссылок (target="_blank")
        bad_links = []
        tag_block = content.find_elements(By.CSS_SELECTOR, "div.article-content-tag-block")
        tag_block_element = tag_block[0] if tag_block else None
        for link in links:
            if tag_block_element:
                try:
                    link.find_element(By.XPATH, "./ancestor::div[contains(@class, 'article-content-tag-block')]")
                    continue
                except:
                    pass
            target = link.get_attribute("target")
            href = link.get_attribute("href")
            text = link.text.strip()
            if target != "_blank":
                if not text: text = "[без текста]"
                bad_links.append(f"{text} | {href} | ❌ открывается в той же вкладке")

        # Сборка отчета
        report.append("МЕТА-ОПИСАНИЕ:")
        report.append(f"✅ {meta_description}" if meta_description else "❌ Нет мета-описания")

        report.append("\nКУРСИВ:")
        if italic_texts:
            report.append("❌ Есть курсив:")
            for i, t in enumerate(italic_texts, 1): report.append(f"{i}. {t}")
        else:
            report.append("✅ Нет курсива")

        report.append("\nХАБР:")
        report.append("❌ Приветствие для Хабра" if has_habr_greeting else "✅ Нет приветствия для Хабра")
        if habr_links:
            report.append("⚠️ Ссылки на Хабр:")
            for hl in habr_links: report.append(hl)
        else:
            report.append("✅ Нет ссылок на Хабр")

        report.append(f"\nБАННЕР: \n{'✅ Есть' if banner_exists else '❌ Нет'}")

        report.append(f"\nЧИТАЙТЕ ТАКЖЕ: \n{'✅ Есть' if read_also_exists else '❌ Нет'}")

        report.append(f"\nССЫЛКИ НА ПОЛЯХ: \n{'✅ Есть' if side_link_exists else '❌ Нет'}")

        report.append("\nМЕТКИ:")
        if tags:
            for i, tag in enumerate(tags, 1): report.append(f"{i}. {tag}")
        else:
            report.append("❌ Нет меток")

        report.append("\nИЗОБРАЖЕНИЯ:")
        for line in image_results: report.append(line)

        report.append("\nССЫЛКИ:")
        if not bad_links:
            report.append("✅ Все ссылки открываются в новой вкладке")
        else:
            for line in bad_links: report.append(line)

        return "\n".join(report)

    except Exception as e:
        return f"Ошибка анализа: {str(e)}"
    finally:
        driver.quit()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/check-url', methods=['POST'])
def check_url():
    data = request.json
    url = data.get('url')
    if not url: return jsonify({'success': False, 'error': 'Нет ссылки'})
    return jsonify({'success': True, 'result': analyze_page(url, is_url=True)})


@app.route('/check-html', methods=['POST'])
def check_html():
    if 'file' not in request.files: return jsonify({'success': False, 'error': 'Нет файла'})
    file = request.files['file']
    filepath = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.html")
    file.save(filepath)
    result = analyze_page(filepath, is_url=False)
    os.remove(filepath)
    return jsonify({'success': True, 'result': result})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)

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

    driver = webdriver.Chrome(options=options)
    report = []

    try:
        if is_url:
            driver.get(source)
        else:
            driver.get(f"file://{os.path.abspath(source)}")

        wait = WebDriverWait(driver, 10)

        # Поиск контента
        content = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.article-content_content")))

        # --- ЛОГИКА ПРОВЕРКИ ---

        # 1. Meta Description
        try:
            meta = driver.find_element(By.CSS_SELECTOR, "meta[name='description']")
            desc = meta.get_attribute("content")
            report.append(f"МЕТА-ОПИСАНИЕ:\n✅ {desc}\n")
        except:
            report.append("МЕТА-ОПИСАНИЕ:\n❌ Нет мета-описания\n")

        # 2. Курсив
        italic_elements = content.find_elements(By.TAG_NAME, "em")
        filtered_italics = []
        for el in italic_elements:
            try:
                el.find_element(By.XPATH, "./ancestor::figcaption")
            except:
                if el.text.strip(): filtered_italics.append(el.text.strip())

        report.append("КУРСИВ:")
        if filtered_italics:
            report.append("❌ Есть курсив:")
            for i, text in enumerate(filtered_italics, 1): report.append(f"{i}. {text}")
        else:
            report.append("✅ Нет курсива")

        # 3. Хабр
        has_habr = "Привет, Хабр" in content.text
        report.append(f"\nХАБР:\n{'❌ Приветствие для Хабра' if has_habr else '✅ Нет приветствия для Хабра'}")

        # 4. Баннер и Читайте также
        promo = len(content.find_elements(By.CSS_SELECTOR, "h2.promo-link_title")) > 0
        read_also = len(content.find_elements(By.CSS_SELECTOR, "h5.read-also__articles-title")) > 0
        report.append(f"\nБАННЕР: {'✅ Есть' if promo else '❌ Нет'}")
        report.append(f"ЧИТАЙТЕ ТАКЖЕ: {'✅ Есть' if read_also else '❌ Нет'}")

        # 5. Изображения (скругления)
        report.append("\nИЗОБРАЖЕНИЯ:")
        images = content.find_elements(By.TAG_NAME, "img")
        for i, img in enumerate(images, 1):
            alt = img.get_attribute("alt") or "❌ alt отсутствует"
            try:
                fig = img.find_element(By.XPATH, "./ancestor::figure[1]")
                rounded = "✅ Есть скругление" if "is-style-rounded" in (
                            fig.get_attribute("class") or "") else "❌ Нет скругления"
            except:
                rounded = "❌ Нет скругления"
            report.append(f"{i}. {alt} | {rounded}")

        # 6. Ссылки (_blank)
        report.append("\nССЫЛКИ:")
        links = content.find_elements(By.TAG_NAME, "a")
        bad_links = []
        for link in links:
            try:
                link.find_element(By.XPATH, "./ancestor::div[contains(@class, 'article-content-tag-block')]")
                continue
            except:
                if link.get_attribute("target") != "_blank":
                    bad_links.append(f"{link.text or '[без текста]'} | {link.get_attribute('href')}")

        if not bad_links:
            report.append("✅ Все ссылки открываются в новой вкладке")
        else:
            for bl in bad_links: report.append(f"❌ В той же вкладке: {bl}")

        return "\n".join(report)

    except Exception as e:
        return f"Ошибка при анализе: {str(e)}"
    finally:
        driver.quit()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/check-url', methods=['POST'])
def check_url():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'Нет ссылки'})

    result = analyze_page(url, is_url=True)
    return jsonify({'success': True, 'result': result})


@app.route('/check-html', methods=['POST'])
def check_html():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Нет файла'})

    file = request.files['file']
    filename = f"{uuid.uuid4()}.html"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    result = analyze_page(filepath, is_url=False)
    os.remove(filepath)  # Чистим за собой

    return jsonify({'success': True, 'result': result})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
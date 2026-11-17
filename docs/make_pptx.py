from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLUE = RGBColor(0x2F, 0x7C, 0xF6)
LAYOUT = prs.slide_layouts[6]


def slide(title, bullets=None, table=None, note=None, size=22):
    s = prs.slides.add_slide(LAYOUT)
    tb = s.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12), Inches(1))
    p = tb.text_frame.paragraphs[0]
    p.text = title
    p.font.size, p.font.bold, p.font.color.rgb = Pt(36), True, BLUE
    top = 1.5
    if table:
        rows, cols = len(table), len(table[0])
        t = s.shapes.add_table(rows, cols, Inches(0.6), Inches(top), Inches(12.1), Inches(0.5 * rows)).table
        for i, row in enumerate(table):
            for j, v in enumerate(row):
                c = t.cell(i, j)
                c.text = v
                for para in c.text_frame.paragraphs:
                    para.font.size = Pt(16)
        top += 0.55 * rows + 0.3
    if bullets:
        tf = s.shapes.add_textbox(Inches(0.6), Inches(top), Inches(12.1), Inches(7.2 - top)).text_frame
        tf.word_wrap = True
        for i, b in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = "• " + b
            p.font.size = Pt(size)
            p.space_after = Pt(8)
    if note:
        s.notes_slide.notes_text_frame.text = note
    return s


s = slide("ЩоВдягнути", [
    "Вебсервіс прогнозу погоди та порад щодо одягу (Open-Meteo + Google Gemini)",
    "Лабораторна робота 2 · Хмарні обчислення",
    "[ПІБ, група]"], size=28)
slide("Ідея", [
    "Проблема: прогноз показує цифри, але не каже, що вдягнути",
    "1. Ввести місто (або геолокацію)",
    "2. Сервіс бере прогноз з Open-Meteo",
    "3. Gemini видає поради; історія й статистика — в базі"])
slide("Хмара як набір сервісів", table=[
    ["Модель", "Що надає", "У проєкті"],
    ["IaaS", "віртуальні машини, мережі", "не використовується"],
    ["PaaS", "платформа для коду", "Render — FastAPI"],
    ["DBaaS", "керована БД", "Supabase — PostgreSQL"],
    ["AIaaS", "AI-модель через API", "Google Gemini"],
    ["Data API", "відкриті дані", "Open-Meteo"],
    ["SaaS", "готовий застосунок", "сам сервіс"]])
slide("Порівняння хмарних API", [
    "Погода: Open-Meteo — без ключа, безкоштовно для некомерційного використання; альтернатива OpenWeatherMap — потрібен ключ",
    "AI: Gemini — безкоштовний рівень, structured JSON за схемою; альтернативи — інші LLM-API",
    "[Звірити цифри й ліміти з сайтами провайдерів перед здачею]"])
slide("Gemini у проєкті", [
    "Вхід: JSON погоди + профіль (активність, чутливість до холоду) + інструкція",
    "Вихід: JSON за схемою — summary, outfit, umbrella, sunscreen, warnings, tips",
    "Надійність: основна модель → запасна (429/5xx) → правила за порогами"])
slide("Як це працює", [
    "Браузер → FastAPI на Render → Open-Meteo (геокодинг, прогноз)",
    "                                          → Gemini API (поради)",
    "                                          → Supabase PostgreSQL (історія)",
    "Кеш прогнозу в пам'яті ~10 хв"], size=24)
slide("Веб-інтерфейс", [
    "1. Пошук міста з підказками / геолокація",
    "2. Картка погоди та прогноз на 5 днів",
    "3. Поради: одяг, парасоля, крем, попередження",
    "[Вставити скріншоти]"])
slide("Аналітика", [
    "SQL GROUP BY: топ міст, середня «відчувається як», частка днів з дощем, запити по днях",
    "Графіки Chart.js, історія запитів, улюблені міста",
    "[Вставити скріншот дашборду]"])
slide("Що вміє сервіс", [
    "Пошук міста й погода на 5 днів",
    "Поради за профілем користувача",
    "Історія, статистика, улюблені міста",
    "REST API зі Swagger (/docs), тести pytest"])
slide("Чого сервіс не вміє", [
    "Немає акаунтів — дані спільні для всіх",
    "Залежність від зовнішніх API та їхніх лімітів",
    "Холодний старт Render після простою"])
slide("Приклад", [
    "[Реальний запит: місто, поради, час відповіді, використана модель, вартість 0 ₴]"])
slide("Скільки це коштує", [
    "Прототип: 0 ₴ — безкоштовні плани Render, Supabase, Gemini, Open-Meteo",
    "Далі — pay-as-you-go; умови безкоштовних рівнів змінюються",
    "[Звірити умови з сайтами]"])
slide("Сфери застосування", [
    "Щоденне планування, подорожі, туризм, доставка, спорт на відкритому повітрі"])
slide("Як розвинути в хмарі", [
    "Supabase Auth — акаунти",
    "Cloud Run — без холодного старту",
    "Cloud Scheduler / Pub/Sub — щоденні сповіщення",
    "Storage, експорт даних"])
slide("Висновки", [
    "AIaaS дозволяє додати «розумну» функцію без власних моделей",
    "Structured JSON робить відповідь AI передбачуваною",
    "Три хмарні сервіси зібрано в працюючий продукт за 0 ₴"])
slide("Дякую за увагу!", ["GitHub: [посилання]", "Демо: [посилання на Render]"], size=28)
prs.save("docs/presentation.pptx")

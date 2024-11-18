import os
import requests
from bs4 import BeautifulSoup
import zipfile
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from aiohttp import ClientSession
import time

# Конфигурация
BASE_URL = "https://mrroot.pro/books/page/{page}/"
TELEGRAM_BOT_TOKEN = "7707551823:AAFDGOcgbmXOGuumEBlUFxJulyYc9yTTnCc"
TELEGRAM_CHANNEL_ID = "@dwhnxhwhcw"
DOWNLOAD_DIR = "downloads"
EXTRACT_DIR = "extracted"
TIMEOUT = 3600  # Тайм-аут между отправками (в секундах)

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Функция для парсинга страницы
def parse_page(page_number):
    url = BASE_URL.format(page=page_number)
    print(f"Парсинг страницы: {url}")
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Ошибка доступа к странице {page_number}")
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    books = soup.find_all("article", class_="post")
    book_data = []

    for book in books:
        title = book.find("h2", class_="entry-title").text.strip()
        description = "Описание не найдено."
        
        # Ищем блок с описанием (entry-content)
        description_block = book.find("div", class_="entry-content")
        if description_block:
            paragraphs = description_block.find_all("p")
            description = "\n".join([p.text.strip() for p in paragraphs])  # Собираем все параграфы в описание
        
        details_url = book.find("a", class_="btn text-uppercase")["href"]
        book_data.append({"title": title, "description": description, "details_url": details_url})
    
    return book_data

# Функция для получения ссылки на ZIP файл
def get_download_link(details_url):
    print(f"Получение ссылки на скачивание с {details_url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    response = requests.get(details_url, headers=headers)
    if response.status_code != 200:
        print(f"Не удалось получить страницу: {details_url}")
        return None
    
    soup = BeautifulSoup(response.text, "html.parser")
    download_link_element = soup.find("a", text="Скачать бесплатно можно здесь")
    if download_link_element and "href" in download_link_element.attrs:
        return download_link_element["href"]
    else:
        print(f"Ссылка для скачивания не найдена на странице: {details_url}")
        return None

# Функция для загрузки и извлечения книги
async def download_and_extract(title, download_url):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(EXTRACT_DIR, exist_ok=True)

    zip_filename = os.path.join(DOWNLOAD_DIR, os.path.basename(download_url))
    print(f"Загрузка файла {download_url}...")
    response = requests.get(download_url)
    if response.status_code != 200:
        print(f"Не удалось скачать файл: {download_url}")
        return None

    with open(zip_filename, "wb") as file:
        file.write(response.content)

    # Извлекаем PDF из архива
    try:
        with zipfile.ZipFile(zip_filename, "r") as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)
        pdf_files = [f for f in os.listdir(EXTRACT_DIR) if f.endswith(".pdf")]
        if pdf_files:
            return os.path.join(EXTRACT_DIR, pdf_files[0])
        else:
            print(f"PDF файл не найден в архиве: {title}")
            return None
    except zipfile.BadZipFile:
        print(f"Архив повреждён: {zip_filename}")
        return None

# Функция для отправки книги в Telegram
async def send_to_telegram(book, pdf_path):
    try:
        with open(pdf_path, "rb") as pdf_file:
            print(f"Отправка книги '{book['title']}' в Telegram...")
            await bot.send_document(
                chat_id=TELEGRAM_CHANNEL_ID,
                document=pdf_file,
                caption=f"**{book['title']}**\n\n{book['description']}",
                parse_mode="Markdown"
            )
        print(f"Книга '{book['title']}' успешно отправлена.")
    except TelegramError as e:
        print(f"Ошибка отправки книги {book['title']}: {e}")

# Функция для удаления скачанных и извлеченных файлов
def cleanup_files(zip_filename, extracted_pdf):
    try:
        os.remove(zip_filename)
        os.remove(extracted_pdf)
        print(f"Удалены файлы: {zip_filename}, {extracted_pdf}")
    except Exception as e:
        print(f"Ошибка при удалении файлов: {e}")

# Основной процесс
async def main():
    async with ClientSession() as session:
        for page in range(1, 10):  # Задайте нужное количество страниц
            print(f"Обработка страницы {page}...")
            books = parse_page(page)
            for book in books:
                download_url = get_download_link(book["details_url"])
                if download_url:
                    pdf_path = await download_and_extract(book["title"], download_url)
                    if pdf_path:
                        await send_to_telegram(book, pdf_path)
                        cleanup_files(pdf_path, pdf_path.replace(EXTRACT_DIR, DOWNLOAD_DIR))  # Удаляем скачанный архив и извлечённый PDF
                        print(f"Таймоут {TIMEOUT} секунд...")
                        time.sleep(TIMEOUT)  # Задержка перед следующим скачиванием и отправкой

if __name__ == "__main__":
    asyncio.run(main())

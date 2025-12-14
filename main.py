import argparse
import os
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config_parser import load_survey_config


CONFIG_FILE = "survey_answers.md"


def weighted_choice(items: Sequence[Tuple[str, float]]) -> str:
    """Выбирает значение с учетом весов."""
    total = sum(w for _, w in items)
    if total <= 0:
        return items[0][0]
    r = random.random() * total
    upto = 0.0
    for val, w in items:
        upto += w
        if upto >= r:
            return val
    return items[-1][0]


def select_radio_by_value(driver: webdriver.Chrome, value: str) -> bool:
    """Выбирает radio button по значению."""
    print(f"    Selecting radio: '{value}'")

    # Небольшой скролл к следующему вопросу
    driver.execute_script("window.scrollBy(0, 150);")
    time.sleep(0.2)

    # Альтернативные XPath селекторы (от самого простого к сложному)
    selectors = [
        f'//*[@data-value="{value}"]',  # Самый простой и надежный!
        f'//div[@jsname][@data-value="{value}"]',
        f'//*[@aria-label="{value}"]',
        f'//span[contains(text(), "{value}")]/ancestor::*[@role="radio" or @data-value="{value}" or contains(@class, "option")][1]',
    ]

    for i, xpath in enumerate(selectors, 1):
        try:
            print(f"      Trying selector {i}: {xpath}")
            element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath)))
            # Скроллим к элементу
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.3)
            # Кликаем через JavaScript для надежности
            driver.execute_script("arguments[0].click();", element)
            print(f"      ✓ Selected with selector {i}")
            return True
        except (TimeoutException, NoSuchElementException) as e:
            print(f"      ✗ Selector {i} failed")
            continue

    print(f"    ✗ Failed to select radio: '{value}'")
    return False


def select_checkbox_by_value(driver: webdriver.Chrome, value: str) -> bool:
    """Выбирает checkbox по значению."""
    print(f"    Selecting checkbox: '{value}'")

    # Небольшой скролл к следующему вопросу
    driver.execute_script("window.scrollBy(0, 150);")
    time.sleep(0.2)

    selectors = [
        f'//*[@data-value="{value}"]',  # Самый простой и надежный!
        f'//div[@jsname][@data-value="{value}"]',
        f'//*[@aria-label="{value}"]',
        f'//span[contains(text(), "{value}")]/ancestor::*[@role="checkbox" or @data-value="{value}" or contains(@class, "option")][1]',
    ]

    for i, xpath in enumerate(selectors, 1):
        try:
            print(f"      Trying selector {i}: {xpath}")
            element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath)))
            # Скроллим к элементу
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.3)
            # Кликаем через JavaScript для надежности
            driver.execute_script("arguments[0].click();", element)
            print(f"      ✓ Selected with selector {i}")
            return True
        except (TimeoutException, NoSuchElementException) as e:
            print(f"      ✗ Selector {i} failed")
            continue

    print(f"    ✗ Failed to select checkbox: '{value}'")
    return False


def fill_form(driver: webdriver.Chrome, survey_config) -> bool:
    """Заполняет форму данными из конфигурации."""
    try:
        print("  Waiting for form to load...")
        # Ждем загрузки формы
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "form"))
        )
        time.sleep(1)
        print("  ✓ Form loaded")

        total_questions = len(survey_config.questions)
        
        # Заполняем все вопросы из конфигурации
        for idx, question in enumerate(survey_config.questions, 1):
            print(f"  [{idx}/{total_questions}] Filling: {question.question_text}")
            
            # Выбираем ответ с учетом весов
            value = weighted_choice([(ans.text, ans.weight) for ans in question.answers])
            print(f"    Choosing: {value}")
            
            # Выбираем элемент в зависимости от типа вопроса
            if question.question_type == "checkbox":
                select_checkbox_by_value(driver, value)
            else:  # radio
                select_radio_by_value(driver, value)
            
            time.sleep(0.5)

        print("  ✓ Form filled successfully")
        return True
    except Exception as e:
        print(f"Error filling form: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def submit_form(driver: webdriver.Chrome) -> bool:
    """Отправляет форму."""
    print("  Looking for submit button...")

    submit_selectors = [
        # Поиск кнопки "Отправить" (теперь всегда русский через метаданные)
        "//span[contains(text(), 'Отправить')]/ancestor::div[@role='button']",
        "//div[@role='button']//span[contains(text(), 'Отправить')]",
        "//div[contains(@class, 'freebirdFormviewerViewNavigationSubmitButton')]",
        "//div[@jsname='M2UYVd']",  # Универсальный селектор кнопки Submit
        "//div[contains(@jsaction, 'submit')]",  # По jsaction
    ]

    for i, selector in enumerate(submit_selectors, 1):
        try:
            print(f"    Trying submit selector {i}: {selector}")
            button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, selector))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            time.sleep(0.1)
            print("    Clicking submit button...")
            button.click()
            time.sleep(0.8)  # Ждем подтверждения отправки
            print("    ✓ Submit button clicked")
            return True
        except TimeoutException:
            print(f"    ✗ Submit selector {i} not found")
            continue

    # Если не нашли кнопку, пробуем через JavaScript
    print("  Trying JavaScript submit...")
    try:
        driver.execute_script("document.querySelector('form').submit();")
        time.sleep(0.8)
        print("  ✓ Submitted via JavaScript")
        return True
    except Exception as e:
        print(f"  ✗ JavaScript submit failed: {e}")

    # Попробуем найти кнопку через JavaScript
    try:
        print("  Trying JavaScript submit...")
        js_submit = """
        // Ищем кнопку по тексту "Отправить" (теперь всегда русский)
        var buttons = document.querySelectorAll('div[role="button"]');
        for (var button of buttons) {
            var spans = button.querySelectorAll('span');
            for (var span of spans) {
                var text = span.textContent;
                if (text.includes('Отправить')) {
                    button.scrollIntoView({block: 'center'});
                    button.click();
                    return true;
                }
            }
        }
        // Альтернативный поиск (русский, английский)
        var submitTexts = ['Отправить', 'Submit', 'Send'];
        for (var text of submitTexts) {
            var elements = document.evaluate('//*[contains(text(), "' + text + '")]', document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
            for (var i = 0; i < elements.snapshotLength; i++) {
                var element = elements.snapshotItem(i);
                var buttonElement = element.closest('div[role="button"], button, input[type="submit"]');
                if (buttonElement && buttonElement.offsetParent !== null) {
                    buttonElement.scrollIntoView({block: 'center'});
                    buttonElement.click();
                    return true;
                }
            }
        }
        return false;
        """
        result = driver.execute_script(js_submit)
        if result:
            print("  ✓ Submitted successfully with JavaScript")
            return True
    except Exception as e:
        print(f"  ✗ JavaScript submit failed: {e}")

    print("  ✗ Could not submit form")
    return False


def click_another_response(driver: webdriver.Chrome) -> bool:
    """Нажимает кнопку 'Отправить ещё один ответ' для повторного заполнения."""
    print("  Looking for 'Submit another response' button...")
    
    another_response_selectors = [
        "//a[contains(text(), 'Отправить ещё один ответ')]",
        "//a[contains(text(), 'ещё один ответ')]",
        "//a[contains(text(), 'Заполнить ещё раз')]",
        "//a[contains(@href, 'viewform')]",  # Обычно это ссылка на форму
    ]
    
    for i, selector in enumerate(another_response_selectors, 1):
        try:
            print(f"    Trying selector {i}: {selector}")
            button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, selector))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            time.sleep(0.1)
            button.click()
            print("    ✓ Clicked 'Submit another response'")
            time.sleep(0.5)  # Ждем загрузки формы
            return True
        except TimeoutException:
            print(f"    ✗ Selector {i} not found")
            continue
    
    print("  ✗ Could not find 'Submit another response' button")
    return False


def create_driver(headless: bool = True) -> webdriver.Chrome:
    """Создает Chrome driver с нужными опциями для macOS."""
    print(f"Creating Chrome driver (headless={headless})...")

    options = Options()

    # Для macOS используем системный Chrome
    # Selenium 4.11+ сам управляет ChromeDriver через selenium-manager
    # Или можно указать путь к chromedriver из brew: /opt/homebrew/bin/chromedriver

    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    options.add_argument("--lang=ru-RU")
    options.add_argument("--accept-lang=ru-RU,ru")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Настройки языка через preferences
    prefs = {
        "intl.accept_languages": "ru-RU,ru",
        "profile.default_content_setting_values.notifications": 2,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Пробуем разные пути к chromedriver
    chromedriver_paths = [
        None,  # selenium-manager сам найдет
        "/opt/homebrew/bin/chromedriver",  # brew для Apple Silicon
        "/usr/local/bin/chromedriver",     # brew для Intel
        "./chromedriver",                  # локальный файл
    ]

    for path in chromedriver_paths:
        try:
            print(f"  Trying ChromeDriver path: {path}")
            if path:
                service = Service(executable_path=path)
                driver = webdriver.Chrome(service=service, options=options)
            else:
                driver = webdriver.Chrome(options=options)
            driver.implicitly_wait(5)
            print("  ✓ Chrome driver created successfully")
            return driver
        except Exception as e:
            print(f"  ✗ Failed with path {path}: {e}", file=sys.stderr)
            continue

    raise Exception("Could not create Chrome driver. Please install ChromeDriver: brew install chromedriver")


def main() -> int:
    # Парсим аргументы командной строки
    parser = argparse.ArgumentParser(description="Google Forms автоматическое заполнение")
    parser.add_argument("-n", "--count", type=int, default=150, help="Количество отправок (по умолчанию: 150)")
    parser.add_argument("--headless", action="store_true", help="Запустить в headless режиме")
    parser.add_argument("--sleep", type=float, default=1.0, help="Задержка между отправками в секундах (по умолчанию: 1)")
    parser.add_argument("--url", type=str, required=True, help="URL формы")
    parser.add_argument("--config", type=str, default=CONFIG_FILE, help="Путь к файлу конфигурации (.md)")
    args = parser.parse_args()
    
    form_url = args.url.strip()
    send_count = args.count
    sleep_s = args.sleep
    headless = args.headless
    config_file = args.config

    # Загружаем конфигурацию опроса
    try:
        print(f"Loading survey config from: {config_file}")
        survey_config = load_survey_config(config_file)
        print(f"✓ Loaded {len(survey_config.questions)} questions")
    except FileNotFoundError:
        print(f"✗ Config file not found: {config_file}", file=sys.stderr)
        print(f"Please create {config_file} with survey answers (see survey_answers.md example)", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"✗ Error loading config: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    print(f"Starting: {send_count} submissions to {form_url} (headless={headless})", file=sys.stderr)

    driver = None
    try:
        driver = create_driver(headless=headless)

        for i in range(1, send_count + 1):
            try:
                # Первый раз открываем форму, потом используем "Отправить ещё один ответ"
                if i == 1:
                    print(f"[{i}/{send_count}] Opening form...")
                    driver.get(form_url)
                    time.sleep(2)  # Даем время на загрузку
                else:
                    print(f"[{i}/{send_count}] Clicking 'Submit another response'...")
                    if not click_another_response(driver):
                        print(f"[{i}/{send_count}] Failed to click 'Submit another response', reopening form...", file=sys.stderr)
                        driver.get(form_url)
                        time.sleep(1)

                print(f"[{i}/{send_count}] Filling form...")
                # Заполняем форму
                if not fill_form(driver, survey_config):
                    print(f"[{i}/{send_count}] Failed to fill form", file=sys.stderr)
                    continue

                print(f"[{i}/{send_count}] Submitting...")
                # Отправляем
                if not submit_form(driver):
                    print(f"[{i}/{send_count}] Failed to submit", file=sys.stderr)
                    continue

                # Быстрая проверка успешной отправки (сокращенный таймаут)
                try:
                    WebDriverWait(driver, 2).until(
                        EC.any_of(
                            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Ваш ответ записан')]")),
                            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'ответ отправлен')]")),
                            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'freebirdFormviewerViewResponseConfirmationMessage')]")),
                        )
                    )
                    print(f"[{i}/{send_count}] ✓ Response submitted successfully!")
                except TimeoutException:
                    # Если не нашли подтверждение, но форма отправилась - все равно OK
                    print(f"[{i}/{send_count}] ✓ Submitted (no confirmation found)")

                if sleep_s > 0 and i < send_count:
                    print(f"Waiting {sleep_s}s before next submission...")
                    time.sleep(sleep_s)

            except Exception as e:
                print(f"[{i}/{send_count}] ✗ Error: {e}", file=sys.stderr)
                # Попробуем перезагрузить форму при ошибке
                try:
                    driver.get(form_url)
                    time.sleep(2)
                except:
                    pass
                continue

    finally:
        if driver:
            print("\n" + "="*50)
            print(f"Completed: {send_count} submissions")
            print("="*50)
            if not headless:
                print("Closing browser in 3 seconds...")
                time.sleep(3)  # Дать время увидеть результат перед закрытием
            driver.quit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

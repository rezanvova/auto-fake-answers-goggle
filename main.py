import argparse
import random
import time
from typing import Sequence, Tuple

from loguru import logger
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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
    driver.execute_script("window.scrollBy(0, 150);")
    time.sleep(0.2)

    selectors = [
        f'//*[@data-value="{value}"]',
        f'//div[@jsname][@data-value="{value}"]',
        f'//*[@aria-label="{value}"]',
        f'//span[contains(text(), "{value}")]/ancestor::*[@role="radio" or @data-value="{value}" or contains(@class, "option")][1]',
    ]

    for xpath in selectors:
        try:
            element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", element)
            return True
        except (TimeoutException, NoSuchElementException):
            continue

    logger.error(f"Failed to select radio: '{value}'")
    return False


def select_checkbox_by_value(driver: webdriver.Chrome, value: str) -> bool:
    """Выбирает checkbox по значению."""
    driver.execute_script("window.scrollBy(0, 150);")
    time.sleep(0.2)

    selectors = [
        f'//*[@data-value="{value}"]',
        f'//div[@jsname][@data-value="{value}"]',
        f'//*[@aria-label="{value}"]',
        f'//span[contains(text(), "{value}")]/ancestor::*[@role="checkbox" or @data-value="{value}" or contains(@class, "option")][1]',
    ]

    for xpath in selectors:
        try:
            element = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", element)
            return True
        except (TimeoutException, NoSuchElementException):
            continue

    logger.error(f"Failed to select checkbox: '{value}'")
    return False


def fill_form(driver: webdriver.Chrome, survey_config) -> bool:
    """Заполняет форму данными из конфигурации."""
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "form"))
        )
        time.sleep(1)

        total_questions = len(survey_config.questions)

        for idx, question in enumerate(survey_config.questions, 1):
            value = weighted_choice([(ans.text, ans.weight) for ans in question.answers])

            if question.question_type == "checkbox":
                if not select_checkbox_by_value(driver, value):
                    return False
            else:
                if not select_radio_by_value(driver, value):
                    return False

            time.sleep(0.5)

        return True
    except Exception as e:
        logger.exception(f"Error filling form: {e}")
        return False


def submit_form(driver: webdriver.Chrome) -> bool:
    """Отправляет форму."""
    submit_selectors = [
        "//span[contains(text(), 'Отправить')]/ancestor::div[@role='button']",
        "//div[@role='button']//span[contains(text(), 'Отправить')]",
        "//div[contains(@class, 'freebirdFormviewerViewNavigationSubmitButton')]",
        "//div[@jsname='M2UYVd']",
        "//div[contains(@jsaction, 'submit')]",
    ]

    for selector in submit_selectors:
        try:
            button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, selector))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            time.sleep(0.1)
            button.click()
            time.sleep(0.8)
            return True
        except TimeoutException:
            continue

    # Пробуем через JavaScript
    try:
        driver.execute_script("document.querySelector('form').submit();")
        time.sleep(0.8)
        return True
    except Exception:
        pass

    try:
        js_submit = """
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
            return True
    except Exception:
        pass

    logger.error("Could not submit form")
    return False


def click_another_response(driver: webdriver.Chrome) -> bool:
    """Нажимает кнопку 'Отправить ещё один ответ' для повторного заполнения."""
    another_response_selectors = [
        "//a[contains(text(), 'Отправить ещё один ответ')]",
        "//a[contains(text(), 'ещё один ответ')]",
        "//a[contains(text(), 'Заполнить ещё раз')]",
        "//a[contains(@href, 'viewform')]",
    ]

    for selector in another_response_selectors:
        try:
            button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, selector))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
            time.sleep(0.1)
            button.click()
            time.sleep(0.5)
            return True
        except TimeoutException:
            continue

    return False


def create_driver(headless: bool = True) -> webdriver.Chrome:
    """Создает Chrome driver с нужными опциями для macOS."""
    options = Options()

    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    options.add_argument("--lang=ru-RU")
    options.add_argument("--accept-lang=ru-RU,ru")
    options.add_argument("--disable-blink-features=AutomationControlled")

    prefs = {
        "intl.accept_languages": "ru-RU,ru",
        "profile.default_content_setting_values.notifications": 2,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    chromedriver_paths = [
        None,
        "/opt/homebrew/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "./chromedriver",
    ]

    for path in chromedriver_paths:
        try:
            if path:
                service = Service(executable_path=path)
                driver = webdriver.Chrome(service=service, options=options)
            else:
                driver = webdriver.Chrome(options=options)
            driver.implicitly_wait(5)
            return driver
        except Exception as e:
            logger.debug(f"Failed ChromeDriver path {path}: {e}")
            continue

    raise Exception("Could not create Chrome driver. Please install ChromeDriver: brew install chromedriver")


def main() -> int:
    parser = argparse.ArgumentParser(description="Google Forms автоматическое заполнение")
    parser.add_argument("-n", "--count", type=int, default=150, help="Количество отправок (по умолчанию: 150)")
    parser.add_argument("--headless", action="store_true", help="Запустить в headless режиме")
    parser.add_argument("--sleep", type=float, default=1.0,
                        help="Задержка между отправками в секундах (по умолчанию: 1)")
    parser.add_argument("--url", type=str, required=True, help="URL формы")
    parser.add_argument("--config", type=str, default=CONFIG_FILE, help="Путь к файлу конфигурации (.md)")
    args = parser.parse_args()

    form_url = args.url.strip()
    send_count = args.count
    sleep_s = args.sleep
    headless = args.headless
    config_file = args.config

    try:
        survey_config = load_survey_config(config_file)
        logger.info(f"Loaded {len(survey_config.questions)} questions from {config_file}")
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_file}")
        logger.error(f"Please create {config_file} with survey answers (see survey_answers.md example)")
        return 1
    except Exception as e:
        logger.exception(f"Error loading config: {e}")
        return 1

    logger.info(f"Starting: {send_count} submissions to {form_url} (headless={headless})")

    driver = None
    try:
        driver = create_driver(headless=headless)

        for i in range(1, send_count + 1):
            try:
                if i == 1:
                    logger.info(f"[{i}/{send_count}] Opening form...")
                    driver.get(form_url)
                    time.sleep(2)
                else:
                    if not click_another_response(driver):
                        logger.warning(f"[{i}/{send_count}] Failed to click 'Submit another response', reopening form...")
                        driver.get(form_url)
                        time.sleep(1)

                logger.info(f"[{i}/{send_count}] Filling form...")
                if not fill_form(driver, survey_config):
                    logger.error(f"[{i}/{send_count}] Failed to fill form")
                    continue

                logger.info(f"[{i}/{send_count}] Submitting...")
                if not submit_form(driver):
                    logger.error(f"[{i}/{send_count}] Failed to submit")
                    continue

                try:
                    WebDriverWait(driver, 2).until(
                        EC.any_of(
                            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Ваш ответ записан')]")),
                            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'ответ отправлен')]")),
                            EC.presence_of_element_located((By.XPATH,
                                                            "//div[contains(@class, 'freebirdFormviewerViewResponseConfirmationMessage')]")),
                        )
                    )
                    logger.success(f"[{i}/{send_count}] Response submitted successfully!")
                except TimeoutException:
                    logger.info(f"[{i}/{send_count}] Submitted (no confirmation found)")

                if sleep_s > 0 and i < send_count:
                    time.sleep(sleep_s)

            except Exception as e:
                logger.exception(f"[{i}/{send_count}] Error: {e}")
                try:
                    driver.get(form_url)
                    time.sleep(2)
                except:
                    pass
                continue

    finally:
        if driver:
            logger.info("=" * 50)
            logger.info(f"Completed: {send_count} submissions")
            logger.info("=" * 50)
            if not headless:
                logger.info("Closing browser in 3 seconds...")
                time.sleep(3)
            driver.quit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

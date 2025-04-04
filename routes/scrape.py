import re
import time
import random
import os
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.firefox import GeckoDriverManager
from bs4 import BeautifulSoup


def scrape_web(url, cookies=None, headers=None, timeout=30, rotate_user_agents=True, random_delay=True):
    """
    Scrape a website using Selenium and return only the main content text.
    """
    driver = None
    try:
        if random_delay:
            time.sleep(random.uniform(1, 3))

        common_user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]

        firefox_options = Options()
        # firefox_options.add_argument("--headless")

        if rotate_user_agents:
            user_agent = random.choice(common_user_agents)
            firefox_options.set_preference(
                "general.useragent.override", user_agent)

        service = Service(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=firefox_options)
        driver.set_page_load_timeout(timeout)
        driver.get(url)

        if cookies:
            for cookie_name, cookie_value in cookies.items():
                driver.add_cookie({'name': cookie_name, 'value': cookie_value})
            driver.refresh()

        time.sleep(3)

        try:
            cookie_button_patterns = [
                "//button[contains(., 'Accept') or contains(., 'accept') or contains(., 'Allow')]",
                "//div[contains(@class, 'cookie') and (contains(., 'Accept') or contains(., 'accept'))]"
            ]
            for xpath in cookie_button_patterns:
                try:
                    cookie_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    cookie_button.click()
                    time.sleep(1)
                    break
                except (TimeoutException, NoSuchElementException):
                    continue
        except Exception:
            pass

        page_source = driver.page_source
        current_url = driver.current_url
        soup = BeautifulSoup(page_source, 'html.parser')

        non_content_elements = ["header", "footer", "nav",
                                "sidebar", "aside", "menu", "comments", "comment"]
        for element_name in non_content_elements:
            for element in soup.find_all(['div', 'section', 'nav', 'header', 'footer'],
                                         class_=lambda x: x and element_name in x.lower()):
                element.decompose()
            for element in soup.find_all(['div', 'section', 'nav', 'header', 'footer'],
                                         id=lambda x: x and element_name in x.lower()):
                element.decompose()
            for element in soup.find_all(element_name):
                element.decompose()

        main_content = None
        for tag in ['main', 'article', 'section']:
            if soup.find(tag):
                main_content = soup.find(tag)
                break

        if not main_content:
            content_patterns = ['content', 'main',
                                'post', 'article', 'entry', 'body']
            for pattern in content_patterns:
                for element in soup.find_all(['div', 'section'],
                                             class_=lambda x: x and pattern in x.lower()):
                    if element.text.strip():
                        main_content = element
                        break
                if not main_content:
                    for element in soup.find_all(['div', 'section'],
                                                 id=lambda x: x and pattern in x.lower()):
                        if element.text.strip():
                            main_content = element
                            break
                if main_content:
                    break

        clean_text = main_content.get_text(
            separator=' ', strip=True) if main_content else soup.get_text(separator=' ', strip=True)
        import re
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        driver.quit()
        return {'status': 200, 'soup': soup, 'rtext': page_source, 'text': clean_text, 'url': current_url}

    except Exception as e:
        if driver:
            driver.quit()
        raise Exception(f"Failed to scrape {url}: {str(e)}")


if __name__ == '__main__':
    result = scrape_web("https://www.go-globe.com/erp-software.php",
                        rotate_user_agents=True, random_delay=True)
    lines = re.sub(r"\s+", " ", str(result['text'])).strip()
    print(lines)

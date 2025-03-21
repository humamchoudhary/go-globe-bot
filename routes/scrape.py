import requests
from bs4 import BeautifulSoup
import logging
import random
import time
from urllib.parse import urlparse


def scrape_with_session(url, cookies=None, headers=None, timeout=30, rotate_user_agents=True, random_delay=True):
    """
    Scrape a website using provided session information with anti-detection measures.

    Args:
        url (str): The URL to scrape
        cookies (dict, optional): Dictionary of cookies to use for authentication
        headers (dict, optional): Dictionary of headers to send with the request
        timeout (int, optional): Request timeout in seconds
        rotate_user_agents (bool, optional): Whether to use a randomized user agent
        random_delay (bool, optional): Whether to add a random delay before request

    Returns:
        dict: A dictionary containing:
            - 'status': HTTP status code
            - 'soup': BeautifulSoup object for HTML parsing
            - 'text': Raw response text
            - 'url': Final URL after any redirects

    Raises:
        Exception: If the request fails
    """
    try:
        # Add random delay to mimic human behavior
        if random_delay:
            time.sleep(random.uniform(1, 3))

        # Common user agents to rotate through
        common_user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]

        # Set up headers with human-like attributes
        if headers is None:
            headers = {}

        # Apply user agent rotation if enabled
        if rotate_user_agents and 'User-Agent' not in headers:
            headers['User-Agent'] = random.choice(common_user_agents)

        # Add common headers that browsers send
        if 'Accept' not in headers:
            headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
        if 'Accept-Language' not in headers:
            headers['Accept-Language'] = 'en-US,en;q=0.9'
        # if 'Accept-Encoding' not in headers:
        #     headers['Accept-Encoding'] = 'gzip, deflate, br'
        if 'Connection' not in headers:
            headers['Connection'] = 'keep-alive'

        # Set referer to the same domain to look more natural
        if 'Referer' not in headers:
            parsed_url = urlparse(url)
            headers['Referer'] = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # Add browser-specific headers to further avoid detection
        if 'sec-ch-ua' not in headers:
            headers['sec-ch-ua'] = '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"'
        if 'sec-ch-ua-mobile' not in headers:
            headers['sec-ch-ua-mobile'] = '?0'
        if 'sec-ch-ua-platform' not in headers:
            headers['sec-ch-ua-platform'] = '"Windows"'
        if 'Sec-Fetch-Dest' not in headers:
            headers['Sec-Fetch-Dest'] = 'document'
        if 'Sec-Fetch-Mode' not in headers:
            headers['Sec-Fetch-Mode'] = 'navigate'
        if 'Sec-Fetch-Site' not in headers:
            headers['Sec-Fetch-Site'] = 'same-origin'

        # Make request with session information
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True
        )

        # Raise exception for bad status codes
        response.raise_for_status()
        # print(response.apparent_encoding)
        soup = BeautifulSoup(response.text, 'html.parser')

        return {
            'status': response.status_code,
            'soup': soup,
            'rtext': response.text,
            'text': soup.get_text(),
            'url': response.url,
        }
        # return soup

    except requests.exceptions.RequestException as e:
        # logging.error(f"Error scraping {url}: {str(e)}")
        raise Exception(f"Failed to scrape {url}: {str(e)}")


if __name__ == '__main__':
    # Load existing cookies from authenticated session
    # user_cookies = {
    #     'session_id': 'abc123xyz789',
    #     'auth_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    # }

    # hti = Html2Image(output_path="temp")
    result = scrape_with_session(
        "https://ubuntu.com/download/desktop",
        # cookies=user_cookies,
        rotate_user_agents=True,
        random_delay=True
    )

    # updated_cookies = result['cookies']
    # print("\n".join(line.strip() for line in result['text'].splitlines() if line.strip()))
    lines = str(result['text'])
    import re
    lines = re.sub(r"\s+", " ", lines).strip()
    # with open('output.txt', 'w') as file:
    #     file.writelines(lines)
    # hti.screenshot(html_str=result[''], save_as="output.png")

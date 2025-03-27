import os
import re
import time
from urllib.parse import urlparse
import random
from routes.scrape import process_and_scrape_url


def process_multiple_urls(urls,
                          max_urls_per_sitemap=50,  # Limit number of URLs from a single sitemap
                          delay_between_requests=1,  # Minimum delay between requests
                          max_delay_between_requests=3):
    """
    Process and scrape multiple URLs, including automatic sitemap URL processing.

    Args:
        urls (list): List of URLs to process and scrape
        max_urls_per_sitemap (int): Maximum number of URLs to scrape from a single sitemap
        delay_between_requests (float): Minimum delay between requests
        max_delay_between_requests (float): Maximum delay between requests

    Returns:
        dict: Comprehensive results of URL processing
    """
    saved_files = []
    processed_urls = set()
    total_results = {
        'successful_scrapes': [],
        'failed_scrapes': [],
        'sitemap_urls': []
    }

    def safe_delay():
        """Add a random delay to prevent overwhelming the server"""
        time.sleep(random.uniform(
            delay_between_requests, max_delay_between_requests))

    for url in urls:
        # Skip already processed URLs
        if url in processed_urls:
            continue

        try:
            # Process the URL
            result = process_and_scrape_url(
                url,
                rotate_user_agents=True,
                random_delay=True,
                process_sitemaps=True
            )

            # Handle sitemap processing
            if result.get('scraped_urls'):
                total_results['sitemap_urls'].extend(result['scraped_urls'])

                # Limit number of URLs from sitemap
                sitemap_urls = result['scraped_urls'][:max_urls_per_sitemap]

                print(f"Sitemap detected: Processing {len(sitemap_urls)} URLs")

                # Process each URL from sitemap
                for sitemap_url in sitemap_urls:
                    if sitemap_url in processed_urls:
                        continue

                    safe_delay()  # Add delay between requests

                    try:
                        # Scrape individual URL from sitemap
                        url_result = process_and_scrape_url(
                            sitemap_url,
                            rotate_user_agents=True,
                            random_delay=True
                        )

                        # Check if scraping was successful
                        if url_result.get('scrape_result') and 'text' in url_result['scrape_result']:
                            # Process and save content
                            lines = str(url_result['scrape_result']['text'])
                            lines = re.sub(r"\s+", " ", lines).strip()

                            # Create filename
                            try:
                                filename = '-'.join(
                                    url_result['scrape_result']['url'].split('/')[2:])
                                if not filename:
                                    filename = urlparse(
                                        url_result['scrape_result']['url']).netloc
                            except Exception:
                                filename = re.sub(
                                    r'[^a-zA-Z0-9-]', '_', sitemap_url)

                            # Ensure files directory exists
                            os.makedirs('files', exist_ok=True)

                            filepath = os.path.join(
                                os.getcwd(), 'files', f"{filename}.txt")

                            with open(filepath, 'w', encoding='utf-8') as f:
                                print(f"Saving content to {f.name}")
                                f.write(lines)

                            saved_files.append(filepath)
                            total_results['successful_scrapes'].append(
                                sitemap_url)
                            processed_urls.add(sitemap_url)

                    except Exception as url_error:
                        print(f"Error processing sitemap URL {
                              sitemap_url}: {str(url_error)}")
                        total_results['failed_scrapes'].append({
                            'url': sitemap_url,
                            'error': str(url_error)
                        })

            # Handle regular URL scraping
            elif result.get('scrape_result') and 'text' in result['scrape_result']:
                # Similar processing for non-sitemap URLs
                lines = str(result['scrape_result']['text'])
                lines = re.sub(r"\s+", " ", lines).strip()

                try:
                    filename = '-'.join(result['scrape_result']
                                        ['url'].split('/')[2:])
                    if not filename:
                        filename = urlparse(
                            result['scrape_result']['url']).netloc
                except Exception:
                    filename = re.sub(r'[^a-zA-Z0-9-]', '_', url)

                os.makedirs('files', exist_ok=True)
                filepath = os.path.join(
                    os.getcwd(), 'files', f"{filename}.txt")

                with open(filepath, 'w', encoding='utf-8') as f:
                    print(f"Saving content to {f.name}")
                    f.write(lines)

                saved_files.append(filepath)
                total_results['successful_scrapes'].append(url)
                processed_urls.add(url)

        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
            total_results['failed_scrapes'].append({
                'url': url,
                'error': str(e)
            })

    # Print summary
    print("\n--- Scraping Summary ---")
    print(f"Total Successful Scrapes: {
          len(total_results['successful_scrapes'])}")
    print(f"Total Failed Scrapes: {len(total_results['failed_scrapes'])}")
    print(f"Total Sitemap URLs Found: {len(total_results['sitemap_urls'])}")

    return {
        'saved_files': saved_files,
        'results': total_results
    }


# If this script is run directly
if __name__ == '__main__':
    # Example usage
    urls_to_process = [
        "https://www.python.org/sitemap.xml",  # Sitemap example
        "https://ubuntu.com/download/desktop",  # Regular URL example
    ]

    scraping_results = process_multiple_urls(
        urls_to_process,
        max_urls_per_sitemap=10,  # Limit to 10 URLs per sitemap for demonstration
        delay_between_requests=1,
        max_delay_between_requests=3
    )

import json
import requests
from bs4 import BeautifulSoup
import os
import time

def search_web(query):
    print(f"Searching the web for: {query}")
    api_key = "cc4dfeb3a13f1948e6de074aa18114fe88061b7700609b96d8f32e3bfff0cef2"
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key
    }
    response = requests.get("https://serpapi.com/search", params=params)
    results = response.json()
    
    urls = [result["link"] for result in results.get("organic_results", [])[:3]]
    print(f"Found URLs: {urls}")
    return urls

def scrape_content(urls):
    print(f"Scraping content from URLs: {urls}")
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_content = ""
    seen_content = set()

    for url in urls:
        print(f"Scraping URL: {url}")
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        read_more_links = soup.find_all('a', text='Read More')
        for link in read_more_links:
            full_url = link.get('href')
            if full_url and full_url not in urls:
                print(f"Found 'Read More' link, adding to URLs: {full_url}")
                urls.append(full_url)

        paragraphs = soup.find_all('p')
        for paragraph in paragraphs:
            text = paragraph.text.strip()
            if text not in seen_content:
                all_content += text + "\n\n"
                seen_content.add(text)
                print(f"Added paragraph to content: {text[:30]}...")

    print("Finished scraping content.")
    return all_content

def is_file_recent(filename):
    """Check if the file exists and is less than 12 hours old."""
    print(f"Checking if {filename} is recent...")
    if not os.path.exists(filename):
        print(f"{filename} does not exist.")
        return False
    file_mod_time = os.path.getmtime(filename)
    current_time = time.time()
    # Check if the file is less than 12 hours old
    if (current_time - file_mod_time) < 12 * 3600:
        print(f"{filename} is less than 12 hours old.")
        return True
    else:
        print(f"{filename} is older than 12 hours.")
        return False

def save_content_to_file(content, filename="the_latest_in_ai_healthcare.txt"):
    print(f"Attempting to save content to {filename}...")
    if is_file_recent(filename):
        print(f"{filename} is already up-to-date and less than 12 hours old. No need to overwrite.")
        return
    else:
        with open(filename, "w", encoding="utf-8") as file:
            file.write(content)
        print(f"Content saved to {filename}.")

# Main logic adjustment
filename = "the_latest_in_ai_healthcare.txt"
print(f"Checking if {filename} needs updating...")
if not is_file_recent(filename):
    print(f"{filename} is not recent. Proceeding with update...")
    urls = search_web("latest developments in healthcare and ai")
    content = scrape_content(urls)
    save_content_to_file(content, filename)
else:
    print(f"{filename} is recent and will be used as is.")
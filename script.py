"""
This file demonstrates the code that was used to convert the CSV files about NASA publications to a strcutured SQLite DB.
The CSV file concerned could be found at https://github.com/jgalazka/SB_publications/blob/main/SB_publication_PMC.csv
"""

import csv
import re
import asyncio
from datetime import datetime
from peewee import chunked
from bs4 import BeautifulSoup
from database.db import Pubs, Authors, PubAuthors, db
from models.models import Publications, ScrapedPubs, CsvPubs
from scraping.scraping import scrape_sites

db.create_tables([Pubs, Authors, PubAuthors])

async def scrape_pmc_articles(urls: list[str]) -> list[ScrapedPubs]:
    """
    Extracts date, authors and content from a single PMC articles.
    """
    articles = await scrape_sites(urls)
    pubs = []
    
    for article in articles:
        
        if article.content is None:
            continue
        
        soup = BeautifulSoup(article.content, 'html.parser')
                
        section_element = soup.select_one("section.pmc-layout__citation")
                
        if not section_element:
            raise Exception("Citation section not found")
                
        section_text = section_element.get_text(" ", strip=True)
        
        match = re.search(r"\d{4}\s+[A-Za-z]{3}\s+\d{1,2}", section_text)

        if match:
            date_str = match.group()
            parsed_date = datetime.strptime(date_str, "%Y %b %d")
        else:
            match = re.search(r"\d{4}\s+[A-Za-z]{3}", section_text)
            
            if not match:
                raise Exception("Date not found")
            
            date_str = match.group()
            parsed_date = datetime.strptime(date_str, "%Y %b")
                    
        
        main_section = soup.find("section", {"aria-label": "Article content"})
            
        if not main_section:
            raise Exception("Main section not found")
                
        pubs.append(ScrapedPubs(
            date=parsed_date,
            authors=[span.get_text(strip=True) for span in soup.select("span.name.western")],
            content=main_section.get_text(separator="\n", strip=True)
        ))
        
    return pubs

def insert_publications_to_db(publications: list[Publications]):
    """
    Upserts publications and their authors in the database.
    """
    nasa_pubs_dict = [{
        "link": pub.link,
        "title": pub.title,
        "date": pub.date,
        "content": pub.content
        } for pub in publications
    ]
   
    authors_set = set([
        author for pub in publications for author in pub.authors
    ])
   
    pubs_and_authors_dict = [{
        "publication": pub.link,
        "author": author
        } for pub in publications for author in pub.authors
    ]
   
    with db.atomic():
        for batch in chunked(nasa_pubs_dict, 100):
            Pubs.insert_many(batch).on_conflict(
                conflict_target=[Pubs.link],
                preserve=[Pubs.title, Pubs.date, Pubs.content]
            ).execute()
           
    print(f"Upserted {len(nasa_pubs_dict)} publications to DB")
    
    with db.atomic():
        for batch in chunked(authors_set, 100):
            author_dicts = [{"name": author} for author in batch]
            Authors.insert_many(author_dicts).on_conflict(
                conflict_target=[Authors.name],
                action='NOTHING'
            ).execute()
           
    print(f"Upserted {len(authors_set)} authors to DB")
           
    with db.atomic():
        for batch in chunked(pubs_and_authors_dict, 100):
            PubAuthors.insert_many(batch).on_conflict(
                conflict_target=[PubAuthors.publication, PubAuthors.author],
                action='NOTHING' 
            ).execute()
           
    print(f"Upserted {len(pubs_and_authors_dict)} publication - author pairs to DB")

def extract_from_csv_file() -> list[CsvPubs]:
    with open("resources/SB_publication_PMC.csv", "r", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        
        pubs = {row['Title']: row['Link'] for row in reader}
        
    print(f"Extracted {len(pubs)} publications from CSV file")
    
    return [CsvPubs(title=title, link=link) for title, link in pubs.items()]

async def scrape_and_store_publications():
    """
    Manages, augments publication info and then commits them to DB
    """
    pubs = extract_from_csv_file() 
    
    urls = [pub.link for pub in pubs]
    
    scraped_pubs_data = await scrape_pmc_articles(urls)
    
    publications = []
    
    scraped_dict = {urls[i]: scraped for i, scraped in enumerate(scraped_pubs_data) if scraped}
    
    for pub in pubs:
        scraped = scraped_dict.get(pub.link)
        if scraped:
            publication = Publications(
                link=pub.link,
                title=pub.title,
                date=scraped.date,
                authors=scraped.authors,
                content=scraped.content
            )
            publications.append(publication)
            
    insert_publications_to_db(publications)
    
    print(f"Successfully stored {len(publications)} publications")
    return publications

    
if __name__ == "__main__":
    asyncio.run(scrape_and_store_publications())
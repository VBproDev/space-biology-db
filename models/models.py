from pydantic import BaseModel
from datetime import datetime

class CsvPubs(BaseModel):
    link: str
    title: str
    
class ScrapedPubs(BaseModel):
    date: datetime
    authors: list[str]
    content: str
    
class Publications(CsvPubs, ScrapedPubs):
    pass

class ScrapedSites(BaseModel):
    url: str
    content: str | None
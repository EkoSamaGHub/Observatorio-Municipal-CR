# =========================
# COSTA RICA MUNICIPAL INTELLIGENCE PLATFORM
# BOOTSTRAP SCRIPT
# =========================

$BASE = "D:\Git\scrapling"

Write-Host ""
Write-Host "====================================="
Write-Host "INITIALIZING MUNICIPAL PLATFORM"
Write-Host "====================================="
Write-Host ""

# =========================
# CREATE FOLDER STRUCTURE
# =========================

$folders = @(
    "$BASE\crawlers",
    "$BASE\modules",
    "$BASE\analyzers",
    "$BASE\configs",
    "$BASE\exports",
    "$BASE\dashboards",
    "$BASE\logs",

    "$BASE\data",
    "$BASE\data\raw_html",
    "$BASE\data\cleaned",
    "$BASE\data\pdfs",
    "$BASE\data\screenshots",
    "$BASE\data\structured",
    "$BASE\data\diffs",

    "$BASE\municipality_lists"
)

foreach ($folder in $folders) {
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
}

Write-Host "[OK] Folder structure created"

# =========================
# CREATE .gitignore
# =========================

$gitignore = @"
venv/
__pycache__/
*.pyc

.env

data/raw_html/
data/pdfs/
data/screenshots/
data/cleaned/
data/diffs/

logs/

*.sqlite
*.db
"@

Set-Content "$BASE\.gitignore" $gitignore

Write-Host "[OK] .gitignore created"

# =========================
# CREATE REQUIREMENTS
# =========================

$requirements = @"
scrapling
playwright
beautifulsoup4
pandas
lxml
aiofiles
tqdm
pydantic
requests
PyMuPDF
pdfplumber
tldextract
aiohttp
"@

Set-Content "$BASE\requirements.txt" $requirements

Write-Host "[OK] requirements.txt created"

# =========================
# CREATE MODELS
# =========================

$models = @'
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Municipality:
    id: str
    name: str
    province: str
    root_url: str


@dataclass
class Page:
    url: str
    municipality_id: str
    depth: int
    status_code: int
    content_type: str
    content_hash: str
    last_crawled: datetime


@dataclass
class Document:
    url: str
    municipality_id: str
    file_type: str
    content_hash: str
'@

Set-Content "$BASE\modules\models.py" $models

Write-Host "[OK] models.py created"

# =========================
# CREATE URL MANAGER
# =========================

$urlManager = @'
from urllib.parse import urlparse, urlunparse


IGNORED_SCHEMES = [
    "mailto",
    "tel",
    "javascript"
]


IGNORED_DOMAINS = [
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "youtube.com"
]


def normalize_url(url):
    parsed = urlparse(url)

    clean = parsed._replace(
        fragment=""
    )

    normalized = urlunparse(clean)

    if normalized.endswith("/"):
        normalized = normalized[:-1]

    return normalized


def should_ignore(url):
    parsed = urlparse(url)

    if parsed.scheme in IGNORED_SCHEMES:
        return True

    for domain in IGNORED_DOMAINS:
        if domain in parsed.netloc:
            return True

    return False
'@

Set-Content "$BASE\modules\url_manager.py" $urlManager

Write-Host "[OK] url_manager.py created"

# =========================
# CREATE HASHING MODULE
# =========================

$hashing = @'
import hashlib


def sha256_hash(content):
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()
'@

Set-Content "$BASE\modules\hashing.py" $hashing

Write-Host "[OK] hashing.py created"

# =========================
# CREATE CLASSIFIERS
# =========================

$classifiers = @'
def classify_url(url):

    url = url.lower()

    if ".pdf" in url:
        return "pdf"

    if ".docx" in url:
        return "docx"

    if ".xlsx" in url:
        return "xlsx"

    if ".zip" in url:
        return "zip"

    if "arcgis" in url or "gis" in url:
        return "gis"

    return "html"
'@

Set-Content "$BASE\modules\classifiers.py" $classifiers

Write-Host "[OK] classifiers.py created"

# =========================
# CREATE LOGGER
# =========================

$logger = @'
import logging
from pathlib import Path


LOG_DIR = Path(r"D:\Git\scrapling\logs")
LOG_DIR.mkdir(exist_ok=True)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "crawl.log"),
        logging.StreamHandler()
    ]
)


logger = logging.getLogger("municipal_crawler")
'@

Set-Content "$BASE\modules\logger.py" $logger

Write-Host "[OK] logger.py created"

# =========================
# CREATE RETRY MANAGER
# =========================

$retryManager = @'
import time


def retry(operation, retries=3, delay=2):

    for attempt in range(retries):

        try:
            return operation()

        except Exception as e:

            if attempt == retries - 1:
                raise

            time.sleep(delay * (attempt + 1))
'@

Set-Content "$BASE\modules\retry_manager.py" $retryManager

Write-Host "[OK] retry_manager.py created"

# =========================
# CREATE SQLITE DATABASE
# =========================

$dbPython = @'
import sqlite3
from pathlib import Path


DB_PATH = Path(r"D:\Git\scrapling\data\municipal.db")

conn = sqlite3.connect(DB_PATH)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    municipality TEXT,
    url TEXT UNIQUE,
    normalized_url TEXT,
    content_type TEXT,
    content_hash TEXT,
    status_code INTEGER,
    depth INTEGER,
    last_crawled TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    municipality TEXT,
    url TEXT UNIQUE,
    file_type TEXT,
    content_hash TEXT,
    downloaded INTEGER DEFAULT 0
)
""")

conn.commit()
conn.close()

print("Database initialized")
'@

Set-Content "$BASE\configs\init_db.py" $dbPython

Write-Host "[OK] init_db.py created"

# =========================
# CREATE STARTER CRAWLER
# =========================

$crawler = @'
import re
import json
from pathlib import Path

from scrapling.fetchers import Fetcher
from bs4 import BeautifulSoup

from modules.url_manager import normalize_url
from modules.hashing import sha256_hash
from modules.classifiers import classify_url
from modules.logger import logger


BASE_DIR = Path(r"D:\Git\scrapling")

MUNI_FILE = BASE_DIR / "municipality_lists" / "Muni84.md"

OUTPUT_DIR = BASE_DIR / "data" / "structured"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

fetcher = Fetcher(
    auto_match=False,
    stealthy_headers=True
)

markdown_pattern = r'\[([^\]]+)\]\((https?://[^\)]+)\)'


def extract_links(markdown_text):
    return re.findall(markdown_pattern, markdown_text)


def crawl(name, url):

    logger.info(f"Crawling {name}")

    response = fetcher.get(url)

    html = response.html

    soup = BeautifulSoup(html, "lxml")

    metadata = {
        "links": [],
        "pdfs": [],
        "emails": []
    }

    for a in soup.find_all("a", href=True):

        href = normalize_url(a["href"])

        metadata["links"].append(href)

        if classify_url(href) == "pdf":
            metadata["pdfs"].append(href)

    output = {
        "municipality": name,
        "url": url,
        "content_hash": sha256_hash(html),
        "metadata": metadata
    }

    safe_name = re.sub(r"[^a-z0-9]+", "_", name.lower())

    output_file = OUTPUT_DIR / f"{safe_name}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {output_file}")


def main():

    with open(MUNI_FILE, "r", encoding="utf-8") as f:
        markdown = f.read()

    municipalities = extract_links(markdown)

    logger.info(f"Detected {len(municipalities)} municipalities")

    for name, url in municipalities:
        try:
            crawl(name, url)

        except Exception as e:
            logger.error(f"{name} failed: {e}")


if __name__ == "__main__":
    main()
'@

Set-Content "$BASE\crawlers\crawl_all.py" $crawler

Write-Host "[OK] crawl_all.py created"

# =========================
# CREATE README
# =========================

$readme = @"
# Costa Rica Municipal Intelligence Platform

National municipal crawling and intelligence platform for:

- transparency monitoring
- procurement monitoring
- GIS discovery
- legal/document intelligence
- change tracking
- municipal AI knowledge systems
"@

Set-Content "$BASE\README.md" $readme

Write-Host "[OK] README.md created"

# =========================
# CREATE VENV
# =========================

Write-Host ""
Write-Host "Creating virtual environment..."

Set-Location $BASE

python -m venv venv

Write-Host "[OK] venv created"

# =========================
# INSTALL PACKAGES
# =========================

Write-Host ""
Write-Host "Installing packages..."

& "$BASE\venv\Scripts\pip.exe" install -r "$BASE\requirements.txt"

Write-Host "[OK] packages installed"

# =========================
# INSTALL PLAYWRIGHT
# =========================

Write-Host ""
Write-Host "Installing Playwright browsers..."

& "$BASE\venv\Scripts\playwright.exe" install

Write-Host "[OK] Playwright installed"

# =========================
# INITIALIZE DATABASE
# =========================

Write-Host ""
Write-Host "Initializing database..."

& "$BASE\venv\Scripts\python.exe" "$BASE\configs\init_db.py"

Write-Host "[OK] Database initialized"

# =========================
# COMPLETE
# =========================

Write-Host ""
Write-Host "====================================="
Write-Host "BOOTSTRAP COMPLETE"
Write-Host "====================================="
Write-Host ""

Write-Host "NEXT STEP:"
Write-Host ""
Write-Host "Place Muni84.md into:"
Write-Host "$BASE\municipality_lists\"
Write-Host ""
Write-Host "Then run:"
Write-Host ""
Write-Host ".\venv\Scripts\activate"
Write-Host "python crawlers\crawl_all.py"
Write-Host ""
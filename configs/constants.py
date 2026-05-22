MAX_DEPTH = 5
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

USER_AGENT = "CostaRicaMunicipalResearchBot/1.0"

IGNORED_EXTENSIONS = [
    # images
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".bmp",
    # binary documents (catalogued separately, not fetched as HTML)
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    # media
    ".mp4", ".mp3", ".avi", ".mov", ".wmv",
    # fonts / styles
    ".woff", ".woff2", ".ttf", ".eot",
]
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

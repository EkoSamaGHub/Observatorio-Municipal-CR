"""
Fix bad root_url entries in municipalities.json based on URL validation research.
"""
import json

FIXES = {
    # DNS errors - domain doesn't exist, replaced with correct URL
    "SJ008": "https://munigoicoechea.go.cr",
    "SJ010": "https://munialajuelita.go.cr",
    "SJ013": "https://www.munitibas.go.cr",        # was redirecting to 404.html
    "SJ015": "https://montesdeoca.go.cr",           # was returning 403 with www
    "SJ017": "https://dota.go.cr",
    "AL002": "https://sanramon.go.cr",
    "AL005": "https://www.atenasmuni.go.cr",
    "AL010": "https://www.munisc.go.cr",
    "AL013": "https://muniupala.go.cr",
    "AL014": "https://muniloschiles.go.cr",
    "AL015": "https://muniguatuso.go.cr",
    "CA003": "https://launion.go.cr",
    "CA008": "https://muniguarco.go.cr",
    "HE002": "https://munibarva.go.cr",
    "HE003": "http://www.munisantodomingo.go.cr",   # TLS error on https
    "HE006": "https://munisanisidro.go.cr",
    "HE008": "https://flores.go.cr",                # www.flores.go.cr blocked by Cloudflare corp
    "HE009": "https://sanpablo.go.cr",
    "GU006": "https://www.municanas.go.cr",
    "GU011": "http://munihojancha.go.cr",
    "PU001": "https://www.puntarenas.go.cr",
    "PU002": "https://muniesparza.go.cr",           # TLS error on old URL
    "PU003": "https://munibuenosaires.go.cr",
    "PU005": "https://www.gobiernolocalosa.go.cr",  # was redirecting from osa.go.cr
    "PU006": "https://muniquepos.go.cr",
    "PU007": "https://munidegolfito.go.cr",
    "PU008": "https://www.municotobrus.go.cr",
    "PU009": "https://www.muniparrita.go.cr",
    "PU011": "https://www.munigarabito.go.cr",
    "LI001": "https://municlimon.go.cr",
    "LI002": "https://munipococi.go.cr",
    "LI004": "https://www.municipalidadtalamanca.go.cr",
    "LI005": "https://www.munimatina.go.cr",
}

with open("municipalities.json", "r", encoding="utf-8") as f:
    data = json.load(f)

changed = 0
for muni in data:
    muni_id = muni["id"]
    if muni_id in FIXES:
        old = muni["root_url"]
        new = FIXES[muni_id]
        print(f"{muni_id:8s} {muni['name']}")
        print(f"  OLD: {old}")
        print(f"  NEW: {new}")
        muni["root_url"] = new
        changed += 1

with open("municipalities.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\nDone. Updated {changed} municipalities.")

# Crawl Policy

## Purpose

This document defines the ethical and operational rules governing how MUNI84CR crawls Costa Rican municipal websites.

## Identity

The crawler identifies itself honestly:

```
User-Agent: CostaRicaMunicipalResearchBot/1.0
```

It does not spoof browser user agents or attempt to disguise itself as a regular user.

## robots.txt

The crawler reads and respects `robots.txt` for every domain before fetching any URL. The check is cached per domain to avoid repeated requests. If `robots.txt` cannot be fetched, the crawler proceeds permissively (assumes allowed).

## Rate Limiting

- Minimum 2-second delay between requests to the same site
- Only one concurrent request per municipality at any time
- No parallel crawling across municipalities (sequential)

This keeps the load on each municipal server minimal — roughly equivalent to a single slow human browser.

## Scope Restriction

The crawler only follows links within the municipality's own domain. It does not:
- Follow links to external government systems (SICOP, CGR, IFAM)
- Follow links to social media or third-party platforms
- Crawl subdomains not explicitly listed in the registry

## Data Use

All data collected is from publicly accessible pages (no authentication). The purpose is:
- Public transparency monitoring
- Document discovery and indexing
- Change detection on public content

No personal data is targeted. Email addresses discovered in page text are collected as contact information for public offices only.

## No Interaction

The crawler is read-only. It does not:
- Submit forms
- Click buttons
- Create accounts
- Trigger any write operations on crawled sites

## Stopping Conditions

The crawler will stop and log an error (not retry indefinitely) if:
- A site returns consistent 5xx errors
- A site's robots.txt explicitly disallows the bot
- The per-municipality page limit is reached

## Contact

Research contact: rs@sotoprojdev.com

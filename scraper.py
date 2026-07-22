import re
import feedparser
import httpx
from datetime import datetime, timedelta, timezone

import db

OPENALEX_URL = "https://api.openalex.org/works"
BASE_URL     = "https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi"
MAILTO       = "lara.poppy@proton.me"


def _date_from(days_back):
    return (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip() or None


def _reconstruct_abstract(inverted_index):
    if not inverted_index:
        return None
    positions = []
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions.append((pos, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def fetch_openalex(days_back=7):
    count     = 0
    date_from = _date_from(days_back)
    query_en  = db.get_setting("query_openalex_en", "surrealism OR surrealist")
    query_de  = db.get_setting("query_openalex_de", "Surrealismus OR surrealistisch")

    for query, lang in [(query_en, "en"), (query_de, "de")]:
        cursor = "*"
        while cursor:
            try:
                resp = httpx.get(
                    OPENALEX_URL,
                    params={
                        "search":  query,
                        "filter":  f"from_publication_date:{date_from}",
                        "per-page": 100,
                        "cursor":  cursor,
                        "sort":    "publication_date:desc",
                        "mailto":  MAILTO,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data  = resp.json()
                works = data.get("results", [])
                if not works:
                    break

                for w in works:
                    doi     = w.get("doi") or w.get("id")
                    title   = w.get("display_name", "")
                    authors = ", ".join(
                        a.get("author", {}).get("display_name", "")
                        for a in w.get("authorships", [])[:5]
                    )
                    loc      = w.get("primary_location") or {}
                    src      = loc.get("source") or {}
                    journal  = src.get("display_name", "")
                    pub_date = w.get("publication_date", "")
                    year     = w.get("publication_year")
                    abstract = _reconstruct_abstract(w.get("abstract_inverted_index"))
                    url      = loc.get("landing_page_url") or w.get("id", "")
                    det_lang = w.get("language") or lang

                    if db.insert_article(doi, title, authors, journal, year,
                                         pub_date, abstract, url, det_lang, "openalex"):
                        count += 1

                meta        = data.get("meta", {})
                next_cursor = meta.get("next_cursor")
                cursor      = next_cursor if (next_cursor and len(works) == 100) else None

            except Exception as e:
                print(f"[OpenAlex] error ({lang}): {e}")
                break

    return count


def fetch_base(days_back=7):
    count     = 0
    date_from = _date_from(days_back)
    q_en      = db.get_setting("query_base_en", "surrealis*")
    q_de      = db.get_setting("query_base_de", "Surrealismus OR surrealistisch OR Surrealisten")

    queries = [
        (f"{q_en} AND dcdate:[{date_from} TO *]",                              "en"),
        (f"({q_de}) AND dclanguage:ger AND dcdate:[{date_from} TO *]",         "de"),
    ]

    for query, lang in queries:
        try:
            resp = httpx.get(
                BASE_URL,
                params={"func": "PerformSearch", "query": query,
                        "hits": 100, "offset": 0, "format": "json"},
                timeout=30,
            )
            resp.raise_for_status()
            docs = resp.json().get("response", {}).get("docs", [])

            for doc in docs:
                identifiers = doc.get("dcidentifier") or []
                doi = (next((i for i in identifiers if "doi" in i.lower()), None)
                       or (identifiers[0] if identifiers else None))

                title_list = doc.get("dctitle") or []
                title = title_list[0] if title_list else ""
                if not title:
                    continue

                authors  = ", ".join((doc.get("dccreator") or [])[:5])
                pubs     = doc.get("dcpublisher") or []
                journal  = pubs[0] if pubs else ""
                dates    = doc.get("dcdate") or []
                pub_date = dates[0] if dates else ""
                year     = int(pub_date[:4]) if pub_date and pub_date[:4].isdigit() else None
                descs    = doc.get("dcdescription") or []
                abstract = _strip_html(descs[0]) if descs else None
                links    = doc.get("dclink") or []
                url      = links[0] if links else ""
                raw_lang = (doc.get("dclanguage") or [lang])[0]
                det_lang = {"ger": "de", "eng": "en", "deu": "de"}.get(raw_lang, raw_lang[:2])

                if db.insert_article(doi or url or title, title, authors, journal,
                                     year, pub_date, abstract, url, det_lang, "base"):
                    count += 1

        except Exception as e:
            print(f"[BASE] error ({lang}): {e}")

    return count


def fetch_rss(days_back=7):
    count  = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    for feed_info in db.get_feeds():
        try:
            feed = feedparser.parse(feed_info["url"])
            if feed.bozo and not feed.entries:
                print(f"[RSS] failed: {feed_info['name']}")
                continue

            for entry in feed.entries:
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub:
                    pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue
                    pub_date = pub_dt.strftime("%Y-%m-%d")
                    year     = pub_dt.year
                else:
                    pub_date = ""
                    year     = None

                doi     = entry.get("prism_doi") or entry.get("dc_identifier") or entry.get("id")
                title   = _strip_html(entry.get("title", ""))
                if not title:
                    continue

                authors  = (", ".join(a.get("name", "") for a in entry.get("authors", []))
                            or entry.get("author", ""))
                content  = (entry.get("content") or [{}])[0].get("value", "")
                abstract = _strip_html(entry.get("summary", "") or content) or None
                url      = entry.get("link", "")
                journal  = feed_info["name"]
                lang     = feed_info.get("lang", "en")

                if db.insert_article(doi or url, title, authors, journal, year,
                                     pub_date, abstract, url, lang, f"rss_{journal}"):
                    count += 1

        except Exception as e:
            print(f"[RSS] error ({feed_info['name']}): {e}")

    return count


def run_fetch(days_back=7):
    print(f"[Fetch] starting — last {days_back} days")
    total = 0
    try:
        n = fetch_openalex(days_back)
        print(f"[Fetch] OpenAlex: {n} new")
        total += n

        n = fetch_base(days_back)
        print(f"[Fetch] BASE: {n} new")
        total += n

        n = fetch_rss(days_back)
        print(f"[Fetch] RSS: {n} new")
        total += n

        db.log_fetch(total, "ok")
        print(f"[Fetch] done — {total} total new articles")
    except Exception as e:
        db.log_fetch(0, f"error: {e}")
        print(f"[Fetch] failed: {e}")

    return total

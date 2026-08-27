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


def _parse_entry_date(entry):
    pub = entry.get("published_parsed") or entry.get("updated_parsed")
    if pub:
        pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
        return pub_dt.strftime("%Y-%m-%d"), pub_dt.year
    return "", None


def _entry_thumbnail(entry):
    """Extract thumbnail URL from feedparser entry (YouTube, Mastodon, generic enclosures)."""
    # YouTube / media:thumbnail
    thumbs = entry.get("media_thumbnail") or []
    if thumbs:
        return thumbs[0].get("url")
    # media:content with medium=image
    for mc in (entry.get("media_content") or []):
        if mc.get("medium") == "image" and mc.get("url"):
            return mc["url"]
    # Standard RSS enclosure (image/*)
    for enc in (entry.get("enclosures") or []):
        if enc.get("type", "").startswith("image/") and enc.get("href"):
            return enc["href"]
    # Look for og:image in summary HTML
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.get("summary", ""))
    if match:
        return match.group(1)
    return None


def _entry_media_url(entry):
    """Extract primary media URL (video/audio) from entry."""
    for mc in (entry.get("media_content") or []):
        if mc.get("medium") in ("video", "audio") and mc.get("url"):
            return mc["url"]
    for enc in (entry.get("enclosures") or []):
        t = enc.get("type", "")
        if (t.startswith("video/") or t.startswith("audio/")) and enc.get("href"):
            return enc["href"]
    return None


# ── Academic source fetchers ──────────────────────────────────────────────────

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
                        "search":   query,
                        "filter":   f"from_publication_date:{date_from}",
                        "per-page": 100,
                        "cursor":   cursor,
                        "sort":     "publication_date:desc",
                        "mailto":   MAILTO,
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
                                         pub_date, abstract, url, det_lang, "openalex",
                                         content_type="paper"):
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
        (f"{q_en} AND dcdate:[{date_from} TO *]",                       "en"),
        (f"({q_de}) AND dclanguage:ger AND dcdate:[{date_from} TO *]",  "de"),
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
                                     year, pub_date, abstract, url, det_lang, "base",
                                     content_type="paper"):
                    count += 1

        except Exception as e:
            print(f"[BASE] error ({lang}): {e}")

    return count


# ── Feed fetchers (RSS, YouTube, Mastodon, image feeds) ───────────────────────

def _fetch_rss_feed(feed_info, cutoff):
    """Standard RSS/Atom — articles, newsletters, blogs."""
    count = 0
    feed  = feedparser.parse(feed_info["url"])
    if feed.bozo and not feed.entries:
        print(f"[RSS] failed: {feed_info['name']}")
        return 0

    for entry in feed.entries:
        pub_date, year = _parse_entry_date(entry)
        if pub_date:
            pub_dt = datetime.strptime(pub_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if pub_dt < cutoff:
                continue

        doi      = entry.get("prism_doi") or entry.get("dc_identifier") or entry.get("id")
        title    = _strip_html(entry.get("title", ""))
        if not title:
            continue

        authors  = (", ".join(a.get("name", "") for a in entry.get("authors", []))
                    or entry.get("author", ""))
        content  = (entry.get("content") or [{}])[0].get("value", "")
        abstract = _strip_html(entry.get("summary", "") or content) or None
        url      = entry.get("link", "")
        thumb    = _entry_thumbnail(entry)

        if db.insert_article(doi or url, title, authors, feed_info["name"], year,
                             pub_date, abstract, url, feed_info.get("lang", "en"),
                             f"rss_{feed_info['name']}",
                             content_type="article",
                             thumbnail_url=thumb,
                             collection_id=feed_info.get("collection_id")):
            count += 1
    return count


def _fetch_youtube_feed(feed_info, cutoff):
    """YouTube channel RSS — sets content_type='video' and extracts thumbnails."""
    count = 0
    feed  = feedparser.parse(feed_info["url"])
    if feed.bozo and not feed.entries:
        print(f"[YouTube] failed: {feed_info['name']}")
        return 0

    for entry in feed.entries:
        pub_date, year = _parse_entry_date(entry)
        if pub_date:
            pub_dt = datetime.strptime(pub_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if pub_dt < cutoff:
                continue

        video_id = entry.get("yt_videoid") or ""
        url      = entry.get("link", "")
        title    = _strip_html(entry.get("title", ""))
        if not title:
            continue

        # feedparser puts description in media_description or summary
        desc     = None
        for mc in (entry.get("media_content") or []):
            if mc.get("medium") == "video":
                desc = mc.get("media_description") or mc.get("description")
                break
        abstract = _strip_html(desc or entry.get("summary", "")) or None

        thumb = _entry_thumbnail(entry)
        if not thumb and video_id:
            thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        channel = feed_info["name"]
        if db.insert_article(url, title, channel, channel, year,
                             pub_date, abstract, url, feed_info.get("lang", "en"),
                             f"youtube_{channel}",
                             content_type="video",
                             media_url=url,
                             thumbnail_url=thumb,
                             collection_id=feed_info.get("collection_id")):
            count += 1
    return count


def _fetch_mastodon_feed(feed_info, cutoff):
    """Mastodon account RSS — sets content_type='post'."""
    count = 0
    feed  = feedparser.parse(feed_info["url"])
    if feed.bozo and not feed.entries:
        print(f"[Mastodon] failed: {feed_info['name']}")
        return 0

    for entry in feed.entries:
        pub_date, year = _parse_entry_date(entry)
        if pub_date:
            pub_dt = datetime.strptime(pub_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if pub_dt < cutoff:
                continue

        url   = entry.get("link", "")
        title = _strip_html(entry.get("title", "")) or _strip_html(entry.get("summary", ""))[:80]
        if not title:
            continue

        abstract = _strip_html(entry.get("summary", "")) or None
        thumb    = _entry_thumbnail(entry)

        if db.insert_article(url, title, feed_info["name"], feed_info["name"], year,
                             pub_date, abstract, url, feed_info.get("lang", "en"),
                             f"mastodon_{feed_info['name']}",
                             content_type="post",
                             thumbnail_url=thumb,
                             collection_id=feed_info.get("collection_id")):
            count += 1
    return count


_FEED_FETCHERS = {
    "youtube":  _fetch_youtube_feed,
    "mastodon": _fetch_mastodon_feed,
    "rss":      _fetch_rss_feed,
}


def fetch_feeds(days_back=7):
    count  = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    for feed_info in db.get_feeds():
        feed_type = feed_info.get("feed_type") or "rss"
        fetcher   = _FEED_FETCHERS.get(feed_type, _fetch_rss_feed)
        try:
            n = fetcher(feed_info, cutoff)
            count += n
        except Exception as e:
            print(f"[Feed] error ({feed_info['name']}): {e}")

    return count


# ── Orchestrator ──────────────────────────────────────────────────────────────

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

        n = fetch_feeds(days_back)
        print(f"[Fetch] Feeds: {n} new")
        total += n

        db.log_fetch(total, "ok")
        print(f"[Fetch] done — {total} total new items")
    except Exception as e:
        db.log_fetch(0, f"error: {e}")
        print(f"[Fetch] failed: {e}")

    return total

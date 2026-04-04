import feedparser
import time

class NewsProvider:
    """
    Raccoglie sentiment in tempo reale (RSS, WebScraping base).
    Nell'architettura finale del 2026 questo modulo passa il testo ai LLM
    per valutare fear & greed.
    """
    def __init__(self):
        self.feeds = [
            "https://finance.yahoo.com/news/rssindex",
            "https://cointelegraph.com/rss"
        ]
        
    def get_latest_headlines(self, limit=5):
        headlines = []
        for url in self.feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:limit]:
                    headlines.append({
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.published if hasattr(entry, 'published') else time.time()
                    })
            except Exception as e:
                print(f"[NewsProvider] Errore su {url}: {e}")
        return headlines

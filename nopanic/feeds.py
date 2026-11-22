"""News sources (RSS). `kind` is a hint for the model: france / world / mixed.
Broken feeds are skipped and reported by /sources and in the deploy log."""

FEEDS: list[tuple[str, str, str]] = [
    # name, kind, url
    ("franceinfo", "france", "https://www.francetvinfo.fr/france.rss"),
    ("franceinfo", "mixed", "https://www.francetvinfo.fr/titres.rss"),
    ("Le Monde", "france", "https://www.lemonde.fr/societe/rss_full.xml"),
    ("Le Figaro", "france", "https://www.lefigaro.fr/rss/figaro_actualites.xml"),
    ("20 Minutes", "france", "https://www.20minutes.fr/feeds/rss-actu-france.xml"),
    ("20 Minutes", "mixed", "https://www.20minutes.fr/feeds/rss-une.xml"),
    ("Ouest-France", "france", "https://www.ouest-france.fr/rss/une"),
    ("Le Dauphiné", "france", "https://www.ledauphine.com/rss"),
    ("Le Monde", "world", "https://www.lemonde.fr/international/rss_full.xml"),
    ("franceinfo", "world", "https://www.francetvinfo.fr/monde.rss"),
    ("France 24", "world", "https://www.france24.com/fr/europe/rss"),
    ("France 24", "world", "https://www.france24.com/fr/rss"),
    ("RFI", "world", "https://www.rfi.fr/fr/europe/rss"),
    ("BBC", "world", "https://feeds.bbci.co.uk/news/world/europe/rss.xml"),
    ("Euronews", "world", "https://fr.euronews.com/rss"),
    ("20 Minutes", "mixed", "https://www.20minutes.fr/feeds/rss-insolite.xml"),
    ("franceinfo", "mixed", "https://www.francetvinfo.fr/insolite.rss"),
]

"""News sources (RSS). `kind` is a hint for the model:
official — French administration; ua — Ukrainian sources about Ukrainians abroad;
france — general French news (strict filter applies); world — for rare major events; light — curious/kind.
Broken feeds are skipped and reported by /sources and in the deploy log."""

FEEDS: list[tuple[str, str, str]] = [
    # official / practical
    ("Service-Public", "official", "https://www.service-public.fr/abonnements/rss/actu-actualites-particuliers.rss"),
    ("Service-Public", "official", "https://www.service-public.gouv.fr/abonnements/rss/actu-actualites-particuliers.rss"),
    ("Google News", "official", "https://news.google.com/rss/search?q=CAF+OR+%22Assurance+maladie%22+OR+Ameli+OR+%22France+Travail%22+OR+imp%C3%B4ts+nouvelles+r%C3%A8gles+when%3A2d&hl=fr&gl=FR&ceid=FR:fr"),
    ("Google News", "official", "https://news.google.com/rss/search?q=pr%C3%A9fecture+OR+%22titre+de+s%C3%A9jour%22+OR+ANEF+OR+%22protection+temporaire%22+when%3A2d&hl=fr&gl=FR&ceid=FR:fr"),
    ("Google News", "official", "https://news.google.com/rss/search?q=%22ce+qui+change%22+OR+%22%C3%A0+partir+du+1er%22+OR+tarif+OR+prix+hausse+when%3A2d&hl=fr&gl=FR&ceid=FR:fr"),
    ("Google News", "official", "https://news.google.com/rss/search?q=gr%C3%A8ve+SNCF+OR+RATP+OR+%22vigilance+orange%22+OR+%22vigilance+rouge%22+when%3A2d&hl=fr&gl=FR&ceid=FR:fr"),
    ("franceinfo éco", "france", "https://www.francetvinfo.fr/economie.rss"),
    ("franceinfo transports", "france", "https://www.francetvinfo.fr/economie/transports.rss"),
    # Ukrainian
    ("Google News", "ua", "https://news.google.com/rss/search?q=%D1%83%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D1%86%D1%96+%D0%A4%D1%80%D0%B0%D0%BD%D1%86%D1%96%D1%8F+when%3A2d&hl=uk&gl=UA&ceid=UA:uk"),
    ("Google News", "ua", "https://news.google.com/rss/search?q=%22%D1%82%D0%B8%D0%BC%D1%87%D0%B0%D1%81%D0%BE%D0%B2%D0%B8%D0%B9+%D0%B7%D0%B0%D1%85%D0%B8%D1%81%D1%82%22+OR+%22%D1%82%D0%B8%D0%BC%D1%87%D0%B0%D1%81%D0%BE%D0%B2%D0%BE%D0%B3%D0%BE+%D0%B7%D0%B0%D1%85%D0%B8%D1%81%D1%82%D1%83%22+when%3A2d&hl=uk&gl=UA&ceid=UA:uk"),
    ("Google News", "ua", "https://news.google.com/rss/search?q=%D0%BF%D0%BE%D1%81%D0%BE%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D0%BE+%D0%A3%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D0%B8+%D1%83+%D0%A4%D1%80%D0%B0%D0%BD%D1%86%D1%96%D1%97+OR+%D0%BA%D0%BE%D0%BD%D1%81%D1%83%D0%BB%D1%8C%D1%81%D1%82%D0%B2%D0%BE+%D0%BF%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82+%D0%B7%D0%B0+%D0%BA%D0%BE%D1%80%D0%B4%D0%BE%D0%BD%D0%BE%D0%BC+when%3A2d&hl=uk&gl=UA&ceid=UA:uk"),
    ("Google News", "ua", "https://news.google.com/rss/search?q=%D0%B2%D1%96%D0%B9%D1%81%D1%8C%D0%BA%D0%BE%D0%B2%D0%B8%D0%B9+%D0%BE%D0%B1%D0%BB%D1%96%D0%BA+%D0%B7%D0%B0+%D0%BA%D0%BE%D1%80%D0%B4%D0%BE%D0%BD%D0%BE%D0%BC+OR+%D0%BC%D0%BE%D0%B1%D1%96%D0%BB%D1%96%D0%B7%D0%B0%D1%86%D1%96%D1%8F+%D1%83%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D1%86%D1%96+%D0%84%D0%A1+when%3A2d&hl=uk&gl=UA&ceid=UA:uk"),
    ("Google News", "ua", "https://news.google.com/rss/search?q=Ukrainiens+France+when%3A2d&hl=fr&gl=FR&ceid=FR:fr"),
    ("Європейська правда", "ua", "https://www.eurointegration.com.ua/rss/"),
    ("Укрінформ", "ua", "https://www.ukrinform.ua/rss/block-lastnews"),
    # general French (strict filter)
    ("franceinfo", "france", "https://www.francetvinfo.fr/france.rss"),
    ("franceinfo", "france", "https://www.francetvinfo.fr/titres.rss"),
    ("Le Monde", "france", "https://www.lemonde.fr/societe/rss_full.xml"),
    ("20 Minutes", "france", "https://www.20minutes.fr/feeds/rss-une.xml"),
    ("Ouest-France", "france", "https://www.ouest-france.fr/rss/une"),
    # world — only major events pass
    ("France 24", "world", "https://www.france24.com/fr/rss"),
    ("BBC", "world", "https://feeds.bbci.co.uk/news/world/europe/rss.xml"),
    # light
    ("20 Minutes insolite", "light", "https://www.20minutes.fr/feeds/rss-insolite.xml"),
]

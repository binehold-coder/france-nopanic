"""News sources (RSS). `kind` is a hint for the model:
official — French administration; ua — Ukrainian sources about Ukrainians abroad;
france — general French news (strict filter applies); world — for rare major events; light — curious/kind.
Broken feeds are skipped and reported by /sources and in the deploy log."""

FEEDS: list[tuple[str, str, str]] = [
    # official / practical
    ("Service-Public", "official", "https://www.service-public.fr/abonnements/rss/actu-actu-part.rss"),
    ("Service-Public", "official", "https://www.service-public.fr/abonnements/rss/actu-actu.rss"),
    ("Service-Public", "official", "https://www.service-public.fr/particuliers/actualites/rss"),
    ("Ameli", "official", "https://www.ameli.fr/assure/actualites/rss.xml"),
    ("impots.gouv", "official", "https://www.impots.gouv.fr/rss.xml"),
    ("Intérieur", "official", "https://www.interieur.gouv.fr/rss.xml"),
    ("InfoMigrants", "official", "https://www.infomigrants.net/fr/rss"),
    ("franceinfo conso", "france", "https://www.francetvinfo.fr/economie/consommation.rss"),
    ("franceinfo éco", "france", "https://www.francetvinfo.fr/economie.rss"),
    ("franceinfo transports", "france", "https://www.francetvinfo.fr/economie/transports.rss"),
    # Ukrainian
    ("Європейська правда", "ua", "https://www.eurointegration.com.ua/rss/"),
    ("Укрінформ", "ua", "https://www.ukrinform.ua/rss/block-lastnews"),
    ("Українська правда", "ua", "https://www.pravda.com.ua/rss/"),
    ("Посольство України у Франції", "ua", "https://france.mfa.gov.ua/rss"),
    ("Суспільне", "ua", "https://suspilne.media/rss/all.rss"),
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
    ("Ouest-France insolite", "light", "https://www.ouest-france.fr/rss/insolite"),
]

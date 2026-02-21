"""
team_extractor.py — Base de données des équipes + extraction depuis titres Yupoo

Usage :
    from team_extractor import extract_product_info
    info = extract_product_info("24-25 巴黎圣日耳曼 主场", "fan")
    # → {"team": "Paris Saint-Germain", "season": "2024-25", "type": "Home", ...}
"""
import re
import logging
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz, process

log = logging.getLogger("team_extractor")

# ══════════════════════════════════════════════════════════════════════════════
# BASE DE DONNÉES DES ÉQUIPES
# Format : clé = nom canonique en minuscules, valeur = métadonnées complètes
# ══════════════════════════════════════════════════════════════════════════════
TEAM_DATABASE = {

    # ─────────────────────────── PREMIER LEAGUE ───────────────────────────────
    "arsenal": {
        "canonical_name": "Arsenal FC",
        "short_name":     "Arsenal",
        "aliases":        ["arsenal", "gunners", "afc", "阿森纳", "arsenal fc"],
        "league":         "Premier League",
        "country":        "England",
    },
    "aston villa": {
        "canonical_name": "Aston Villa FC",
        "short_name":     "Aston Villa",
        "aliases":        ["aston villa", "villa", "avfc", "阿斯顿维拉"],
        "league":         "Premier League",
        "country":        "England",
    },
    "bournemouth": {
        "canonical_name": "AFC Bournemouth",
        "short_name":     "Bournemouth",
        "aliases":        ["bournemouth", "afcb", "cherries", "伯恩茅斯"],
        "league":         "Premier League",
        "country":        "England",
    },
    "brentford": {
        "canonical_name": "Brentford FC",
        "short_name":     "Brentford",
        "aliases":        ["brentford", "bees"],
        "league":         "Premier League",
        "country":        "England",
    },
    "brighton": {
        "canonical_name": "Brighton & Hove Albion FC",
        "short_name":     "Brighton",
        "aliases":        ["brighton", "bhafc", "seagulls", "brighton hove"],
        "league":         "Premier League",
        "country":        "England",
    },
    "burnley": {
        "canonical_name": "Burnley FC",
        "short_name":     "Burnley",
        "aliases":        ["burnley", "clarets"],
        "league":         "Premier League",
        "country":        "England",
    },
    "chelsea": {
        "canonical_name": "Chelsea FC",
        "short_name":     "Chelsea",
        "aliases":        ["chelsea", "cfc", "blues", "切尔西"],
        "league":         "Premier League",
        "country":        "England",
    },
    "crystal palace": {
        "canonical_name": "Crystal Palace FC",
        "short_name":     "Crystal Palace",
        "aliases":        ["crystal palace", "cpfc", "eagles", "水晶宫"],
        "league":         "Premier League",
        "country":        "England",
    },
    "everton": {
        "canonical_name": "Everton FC",
        "short_name":     "Everton",
        "aliases":        ["everton", "efc", "toffees", "埃弗顿"],
        "league":         "Premier League",
        "country":        "England",
    },
    "fulham": {
        "canonical_name": "Fulham FC",
        "short_name":     "Fulham",
        "aliases":        ["fulham", "ffc", "cottagers"],
        "league":         "Premier League",
        "country":        "England",
    },
    "ipswich town": {
        "canonical_name": "Ipswich Town FC",
        "short_name":     "Ipswich",
        "aliases":        ["ipswich", "ipswich town", "tractor boys"],
        "league":         "Premier League",
        "country":        "England",
    },
    "leeds united": {
        "canonical_name": "Leeds United FC",
        "short_name":     "Leeds",
        "aliases":        ["leeds", "leeds united", "lufc", "whites"],
        "league":         "Championship",
        "country":        "England",
    },
    "leicester city": {
        "canonical_name": "Leicester City FC",
        "short_name":     "Leicester",
        "aliases":        ["leicester", "leicester city", "lcfc", "foxes", "莱斯特城"],
        "league":         "Championship",
        "country":        "England",
    },
    "liverpool": {
        "canonical_name": "Liverpool FC",
        "short_name":     "Liverpool",
        "aliases":        ["liverpool", "lfc", "reds", "利物浦"],
        "league":         "Premier League",
        "country":        "England",
    },
    "luton town": {
        "canonical_name": "Luton Town FC",
        "short_name":     "Luton",
        "aliases":        ["luton", "luton town", "hatters"],
        "league":         "Championship",
        "country":        "England",
    },
    "manchester city": {
        "canonical_name": "Manchester City FC",
        "short_name":     "Man City",
        "aliases":        ["manchester city", "man city", "mcfc", "城", "曼城", "曼彻斯特城", "sky blues"],
        "league":         "Premier League",
        "country":        "England",
    },
    "manchester united": {
        "canonical_name": "Manchester United FC",
        "short_name":     "Man United",
        "aliases":        ["manchester united", "man united", "man utd", "mufc", "曼联", "曼彻斯特联", "red devils"],
        "league":         "Premier League",
        "country":        "England",
    },
    "newcastle united": {
        "canonical_name": "Newcastle United FC",
        "short_name":     "Newcastle",
        "aliases":        ["newcastle", "newcastle united", "nufc", "magpies", "纽卡斯尔"],
        "league":         "Premier League",
        "country":        "England",
    },
    "nottingham forest": {
        "canonical_name": "Nottingham Forest FC",
        "short_name":     "Nottingham Forest",
        "aliases":        ["nottingham forest", "nffc", "forest", "诺丁汉森林"],
        "league":         "Premier League",
        "country":        "England",
    },
    "sheffield united": {
        "canonical_name": "Sheffield United FC",
        "short_name":     "Sheffield Utd",
        "aliases":        ["sheffield united", "sufc", "blades"],
        "league":         "Championship",
        "country":        "England",
    },
    "tottenham hotspur": {
        "canonical_name": "Tottenham Hotspur FC",
        "short_name":     "Tottenham",
        "aliases":        ["tottenham", "spurs", "thfc", "热刺", "托特纳姆", "tottenham hotspur"],
        "league":         "Premier League",
        "country":        "England",
    },
    "west ham united": {
        "canonical_name": "West Ham United FC",
        "short_name":     "West Ham",
        "aliases":        ["west ham", "whufc", "hammers", "west ham united", "西汉姆"],
        "league":         "Premier League",
        "country":        "England",
    },
    "wolverhampton": {
        "canonical_name": "Wolverhampton Wanderers FC",
        "short_name":     "Wolves",
        "aliases":        ["wolves", "wolverhampton", "wwfc", "wolfs", "狼队", "wolverhampton wanderers"],
        "league":         "Premier League",
        "country":        "England",
    },

    # ────────────────────────────── LA LIGA ───────────────────────────────────
    "real madrid": {
        "canonical_name": "Real Madrid CF",
        "short_name":     "Real Madrid",
        "aliases":        ["real madrid", "real", "rmcf", "皇家马德里", "皇马", "los blancos"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "barcelona": {
        "canonical_name": "FC Barcelona",
        "short_name":     "Barcelona",
        "aliases":        ["barcelona", "barca", "barça", "fcb", "巴塞罗那", "巴萨", "blaugrana"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "atletico madrid": {
        "canonical_name": "Atlético de Madrid",
        "short_name":     "Atlético Madrid",
        "aliases":        ["atletico madrid", "atletico", "atlético", "atm", "马德里竞技", "马竞", "colchoneros"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "sevilla": {
        "canonical_name": "Sevilla FC",
        "short_name":     "Sevilla",
        "aliases":        ["sevilla", "sfc", "塞维利亚"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "real betis": {
        "canonical_name": "Real Betis Balompié",
        "short_name":     "Real Betis",
        "aliases":        ["real betis", "betis", "rbfc", "皇家贝蒂斯"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "real sociedad": {
        "canonical_name": "Real Sociedad de Fútbol",
        "short_name":     "Real Sociedad",
        "aliases":        ["real sociedad", "sociedad", "rsssb"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "villarreal": {
        "canonical_name": "Villarreal CF",
        "short_name":     "Villarreal",
        "aliases":        ["villarreal", "yellow submarine", "维拉利尔"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "athletic bilbao": {
        "canonical_name": "Athletic Club",
        "short_name":     "Athletic Bilbao",
        "aliases":        ["athletic bilbao", "athletic club", "athletic", "lions"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "valencia": {
        "canonical_name": "Valencia CF",
        "short_name":     "Valencia",
        "aliases":        ["valencia", "vcf", "bats", "瓦伦西亚"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "celta vigo": {
        "canonical_name": "RC Celta de Vigo",
        "short_name":     "Celta Vigo",
        "aliases":        ["celta vigo", "celta", "sky blues vigo"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "osasuna": {
        "canonical_name": "Club Atlético Osasuna",
        "short_name":     "Osasuna",
        "aliases":        ["osasuna", "ca osasuna"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "girona": {
        "canonical_name": "Girona FC",
        "short_name":     "Girona",
        "aliases":        ["girona", "gfc"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "getafe": {
        "canonical_name": "Getafe CF",
        "short_name":     "Getafe",
        "aliases":        ["getafe", "gcf"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "rayo vallecano": {
        "canonical_name": "Rayo Vallecano",
        "short_name":     "Rayo",
        "aliases":        ["rayo vallecano", "rayo"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "alaves": {
        "canonical_name": "Deportivo Alavés",
        "short_name":     "Alavés",
        "aliases":        ["alaves", "alavés", "deportivo alaves"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "mallorca": {
        "canonical_name": "RCD Mallorca",
        "short_name":     "Mallorca",
        "aliases":        ["mallorca", "rcd mallorca"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "espanyol": {
        "canonical_name": "RCD Espanyol",
        "short_name":     "Espanyol",
        "aliases":        ["espanyol", "rcd espanyol", "西班牙人"],
        "league":         "La Liga",
        "country":        "Spain",
    },
    "las palmas": {
        "canonical_name": "UD Las Palmas",
        "short_name":     "Las Palmas",
        "aliases":        ["las palmas", "ud las palmas"],
        "league":         "La Liga",
        "country":        "Spain",
    },

    # ─────────────────────────────── SERIE A ──────────────────────────────────
    "juventus": {
        "canonical_name": "Juventus FC",
        "short_name":     "Juventus",
        "aliases":        ["juventus", "juve", "old lady", "尤文图斯", "尤文", "bianconeri"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "inter milan": {
        "canonical_name": "Inter Milan",
        "short_name":     "Inter",
        "aliases":        ["inter milan", "inter", "internazionale", "nerazzurri", "国际米兰", "国米"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "ac milan": {
        "canonical_name": "AC Milan",
        "short_name":     "AC Milan",
        "aliases":        ["ac milan", "milan", "rossoneri", "AC米兰", "米兰"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "napoli": {
        "canonical_name": "SSC Napoli",
        "short_name":     "Napoli",
        "aliases":        ["napoli", "ssc napoli", "partenopei", "那不勒斯"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "roma": {
        "canonical_name": "AS Roma",
        "short_name":     "Roma",
        "aliases":        ["roma", "as roma", "giallorossi", "罗马"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "lazio": {
        "canonical_name": "SS Lazio",
        "short_name":     "Lazio",
        "aliases":        ["lazio", "ss lazio", "biancocelesti", "拉齐奥"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "atalanta": {
        "canonical_name": "Atalanta BC",
        "short_name":     "Atalanta",
        "aliases":        ["atalanta", "atalanta bc", "la dea", "阿特兰大"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "fiorentina": {
        "canonical_name": "ACF Fiorentina",
        "short_name":     "Fiorentina",
        "aliases":        ["fiorentina", "viola", "la viola", "佛罗伦萨"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "torino": {
        "canonical_name": "Torino FC",
        "short_name":     "Torino",
        "aliases":        ["torino", "toro", "granata"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "bologna": {
        "canonical_name": "Bologna FC 1909",
        "short_name":     "Bologna",
        "aliases":        ["bologna", "bologna fc", "rossoblù"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "udinese": {
        "canonical_name": "Udinese Calcio",
        "short_name":     "Udinese",
        "aliases":        ["udinese", "zebrette"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "monza": {
        "canonical_name": "AC Monza",
        "short_name":     "Monza",
        "aliases":        ["monza", "ac monza"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "lecce": {
        "canonical_name": "US Lecce",
        "short_name":     "Lecce",
        "aliases":        ["lecce", "us lecce"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "genoa": {
        "canonical_name": "Genoa CFC",
        "short_name":     "Genoa",
        "aliases":        ["genoa", "cfc genoa", "grifone"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "cagliari": {
        "canonical_name": "Cagliari Calcio",
        "short_name":     "Cagliari",
        "aliases":        ["cagliari", "rossoblù sardi"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "hellas verona": {
        "canonical_name": "Hellas Verona FC",
        "short_name":     "Verona",
        "aliases":        ["verona", "hellas verona", "hellase"],
        "league":         "Serie A",
        "country":        "Italy",
    },
    "empoli": {
        "canonical_name": "Empoli FC",
        "short_name":     "Empoli",
        "aliases":        ["empoli", "empoli fc"],
        "league":         "Serie A",
        "country":        "Italy",
    },

    # ─────────────────────────────── BUNDESLIGA ───────────────────────────────
    "bayern munich": {
        "canonical_name": "FC Bayern München",
        "short_name":     "Bayern Munich",
        "aliases":        ["bayern munich", "bayern", "fcb", "bayer munich", "拜仁慕尼黑", "拜仁", "拜仁慕尼", "bavarians"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "borussia dortmund": {
        "canonical_name": "Borussia Dortmund",
        "short_name":     "Dortmund",
        "aliases":        ["borussia dortmund", "dortmund", "bvb", "多特蒙德", "多特", "黄蜂", "black yellows"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "rb leipzig": {
        "canonical_name": "RB Leipzig",
        "short_name":     "RB Leipzig",
        "aliases":        ["rb leipzig", "leipzig", "rbl", "莱比锡", "红牛莱比锡"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "bayer leverkusen": {
        "canonical_name": "Bayer 04 Leverkusen",
        "short_name":     "Leverkusen",
        "aliases":        ["bayer leverkusen", "leverkusen", "b04", "勒沃库森"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "eintracht frankfurt": {
        "canonical_name": "Eintracht Frankfurt",
        "short_name":     "Frankfurt",
        "aliases":        ["eintracht frankfurt", "frankfurt", "sge", "法兰克福"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "vfb stuttgart": {
        "canonical_name": "VfB Stuttgart",
        "short_name":     "Stuttgart",
        "aliases":        ["vfb stuttgart", "stuttgart", "斯图加特"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "wolfsburg": {
        "canonical_name": "VfL Wolfsburg",
        "short_name":     "Wolfsburg",
        "aliases":        ["wolfsburg", "vfl wolfsburg", "狼堡", "wolves wolfsburg"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "borussia monchengladbach": {
        "canonical_name": "Borussia Mönchengladbach",
        "short_name":     "Mönchengladbach",
        "aliases":        ["borussia monchengladbach", "monchengladbach", "gladbach", "bmg", "门兴格拉德巴赫"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "union berlin": {
        "canonical_name": "1. FC Union Berlin",
        "short_name":     "Union Berlin",
        "aliases":        ["union berlin", "fc union berlin", "union", "柏林联合"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "sc freiburg": {
        "canonical_name": "SC Freiburg",
        "short_name":     "Freiburg",
        "aliases":        ["sc freiburg", "freiburg", "breisgauer"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "hoffenheim": {
        "canonical_name": "TSG Hoffenheim",
        "short_name":     "Hoffenheim",
        "aliases":        ["hoffenheim", "tsg hoffenheim", "1899 hoffenheim"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "hertha bsc": {
        "canonical_name": "Hertha BSC",
        "short_name":     "Hertha",
        "aliases":        ["hertha", "hertha bsc", "hertha berlin"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "hamburg": {
        "canonical_name": "Hamburger SV",
        "short_name":     "Hamburg",
        "aliases":        ["hamburger sv", "hamburg", "hsv", "汉堡"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "schalke": {
        "canonical_name": "FC Schalke 04",
        "short_name":     "Schalke",
        "aliases":        ["schalke", "schalke 04", "fc schalke", "沙尔克"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "werder bremen": {
        "canonical_name": "SV Werder Bremen",
        "short_name":     "Werder Bremen",
        "aliases":        ["werder bremen", "werder", "sv werder", "不来梅"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "koln": {
        "canonical_name": "1. FC Köln",
        "short_name":     "Köln",
        "aliases":        ["köln", "koln", "fc koln", "fc köln", "cologne"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "mainz": {
        "canonical_name": "1. FSV Mainz 05",
        "short_name":     "Mainz",
        "aliases":        ["mainz", "mainz 05", "fsv mainz", "美因茨"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },
    "augsburg": {
        "canonical_name": "FC Augsburg",
        "short_name":     "Augsburg",
        "aliases":        ["augsburg", "fc augsburg"],
        "league":         "Bundesliga",
        "country":        "Germany",
    },

    # ──────────────────────────────── LIGUE 1 ─────────────────────────────────
    "paris saint-germain": {
        "canonical_name": "Paris Saint-Germain FC",
        "short_name":     "PSG",
        "aliases":        ["paris saint-germain", "psg", "paris sg", "paris fc", "巴黎圣日耳曼", "巴黎", "parisiens"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "marseille": {
        "canonical_name": "Olympique de Marseille",
        "short_name":     "Marseille",
        "aliases":        ["marseille", "om", "olympique marseille", "马赛", "phocéens"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "lyon": {
        "canonical_name": "Olympique Lyonnais",
        "short_name":     "Lyon",
        "aliases":        ["lyon", "ol", "olympique lyonnais", "里昂", "gones"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "monaco": {
        "canonical_name": "AS Monaco FC",
        "short_name":     "Monaco",
        "aliases":        ["monaco", "as monaco", "asmonaco", "摩纳哥", "monegasques"],
        "league":         "Ligue 1",
        "country":        "Monaco",
    },
    "lille": {
        "canonical_name": "LOSC Lille",
        "short_name":     "Lille",
        "aliases":        ["lille", "losc", "losc lille", "里尔", "dogues"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "lens": {
        "canonical_name": "RC Lens",
        "short_name":     "Lens",
        "aliases":        ["lens", "rc lens", "血腥佬"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "rennes": {
        "canonical_name": "Stade Rennais FC",
        "short_name":     "Rennes",
        "aliases":        ["rennes", "stade rennais", "srfc", "雷恩"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "nice": {
        "canonical_name": "OGC Nice",
        "short_name":     "Nice",
        "aliases":        ["nice", "ogc nice", "aiglons", "尼斯"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "nantes": {
        "canonical_name": "FC Nantes",
        "short_name":     "Nantes",
        "aliases":        ["nantes", "fc nantes", "canaris", "南特"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "strasbourg": {
        "canonical_name": "RC Strasbourg Alsace",
        "short_name":     "Strasbourg",
        "aliases":        ["strasbourg", "rc strasbourg", "racing strasbourg", "斯特拉斯堡"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "montpellier": {
        "canonical_name": "Montpellier HSC",
        "short_name":     "Montpellier",
        "aliases":        ["montpellier", "mhsc", "la paillade"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "toulouse": {
        "canonical_name": "Toulouse FC",
        "short_name":     "Toulouse",
        "aliases":        ["toulouse", "tfc", "téfécé"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "reims": {
        "canonical_name": "Stade de Reims",
        "short_name":     "Reims",
        "aliases":        ["reims", "stade de reims", "sdr"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "brest": {
        "canonical_name": "Stade Brestois 29",
        "short_name":     "Brest",
        "aliases":        ["brest", "stade brestois"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "le havre": {
        "canonical_name": "Le Havre AC",
        "short_name":     "Le Havre",
        "aliases":        ["le havre", "hac", "havre ac"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "lorient": {
        "canonical_name": "FC Lorient",
        "short_name":     "Lorient",
        "aliases":        ["lorient", "fc lorient", "les merlus"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "metz": {
        "canonical_name": "FC Metz",
        "short_name":     "Metz",
        "aliases":        ["metz", "fc metz", "grenat"],
        "league":         "Ligue 1",
        "country":        "France",
    },
    "auxerre": {
        "canonical_name": "AJ Auxerre",
        "short_name":     "Auxerre",
        "aliases":        ["auxerre", "aj auxerre", "aja"],
        "league":         "Ligue 2",
        "country":        "France",
    },
    "bordeaux": {
        "canonical_name": "FC Girondins de Bordeaux",
        "short_name":     "Bordeaux",
        "aliases":        ["bordeaux", "girondins", "girondins de bordeaux", "fcgb"],
        "league":         "Ligue 2",
        "country":        "France",
    },

    # ────────────────────────── AUTRES CLUBS EUROPÉENS ────────────────────────
    "ajax": {
        "canonical_name": "AFC Ajax",
        "short_name":     "Ajax",
        "aliases":        ["ajax", "afc ajax", "阿贾克斯", "amsterdammers"],
        "league":         "Eredivisie",
        "country":        "Netherlands",
    },
    "psv eindhoven": {
        "canonical_name": "PSV Eindhoven",
        "short_name":     "PSV",
        "aliases":        ["psv", "psv eindhoven", "eindhoven", "埃因霍温"],
        "league":         "Eredivisie",
        "country":        "Netherlands",
    },
    "feyenoord": {
        "canonical_name": "Feyenoord Rotterdam",
        "short_name":     "Feyenoord",
        "aliases":        ["feyenoord", "feyenoord rotterdam", "de club"],
        "league":         "Eredivisie",
        "country":        "Netherlands",
    },
    "porto": {
        "canonical_name": "FC Porto",
        "short_name":     "Porto",
        "aliases":        ["porto", "fc porto", "dragões", "波尔图"],
        "league":         "Primeira Liga",
        "country":        "Portugal",
    },
    "benfica": {
        "canonical_name": "SL Benfica",
        "short_name":     "Benfica",
        "aliases":        ["benfica", "sl benfica", "águias", "本菲卡"],
        "league":         "Primeira Liga",
        "country":        "Portugal",
    },
    "sporting cp": {
        "canonical_name": "Sporting CP",
        "short_name":     "Sporting",
        "aliases":        ["sporting cp", "sporting", "sporting portugal", "leões", "葡萄牙竞技"],
        "league":         "Primeira Liga",
        "country":        "Portugal",
    },
    "celtic": {
        "canonical_name": "Celtic FC",
        "short_name":     "Celtic",
        "aliases":        ["celtic", "celtic fc", "bhoys", "凯尔特人"],
        "league":         "Scottish Premiership",
        "country":        "Scotland",
    },
    "rangers": {
        "canonical_name": "Rangers FC",
        "short_name":     "Rangers",
        "aliases":        ["rangers", "rangers fc", "gers", "流浪者"],
        "league":         "Scottish Premiership",
        "country":        "Scotland",
    },
    "galatasaray": {
        "canonical_name": "Galatasaray SK",
        "short_name":     "Galatasaray",
        "aliases":        ["galatasaray", "gala", "cimbom", "加拉塔萨雷"],
        "league":         "Süper Lig",
        "country":        "Turkey",
    },
    "fenerbahce": {
        "canonical_name": "Fenerbahçe SK",
        "short_name":     "Fenerbahçe",
        "aliases":        ["fenerbahce", "fenerbahçe", "fener", "fb", "费内巴切"],
        "league":         "Süper Lig",
        "country":        "Turkey",
    },
    "besiktas": {
        "canonical_name": "Beşiktaş JK",
        "short_name":     "Beşiktaş",
        "aliases":        ["besiktas", "beşiktaş", "bjk", "kartal"],
        "league":         "Süper Lig",
        "country":        "Turkey",
    },
    "anderlecht": {
        "canonical_name": "RSC Anderlecht",
        "short_name":     "Anderlecht",
        "aliases":        ["anderlecht", "rsc anderlecht", "sporting anderlecht"],
        "league":         "Pro League",
        "country":        "Belgium",
    },
    "club brugge": {
        "canonical_name": "Club Brugge KV",
        "short_name":     "Club Brugge",
        "aliases":        ["club brugge", "brugge", "blauw zwart"],
        "league":         "Pro League",
        "country":        "Belgium",
    },
    "red bull salzburg": {
        "canonical_name": "FC Red Bull Salzburg",
        "short_name":     "Salzburg",
        "aliases":        ["salzburg", "red bull salzburg", "fc salzburg", "rbs"],
        "league":         "Austrian Bundesliga",
        "country":        "Austria",
    },
    "red star belgrade": {
        "canonical_name": "FK Red Star Belgrade",
        "short_name":     "Red Star",
        "aliases":        ["red star belgrade", "red star", "crvena zvezda", "estrela vermelha"],
        "league":         "Serbian SuperLiga",
        "country":        "Serbia",
    },
    "dinamo zagreb": {
        "canonical_name": "GNK Dinamo Zagreb",
        "short_name":     "Dinamo Zagreb",
        "aliases":        ["dinamo zagreb", "zagreb", "gnk dinamo"],
        "league":         "HNL",
        "country":        "Croatia",
    },
    "shakhtar donetsk": {
        "canonical_name": "Shakhtar Donetsk",
        "short_name":     "Shakhtar",
        "aliases":        ["shakhtar", "shakhtar donetsk", "miners"],
        "league":         "Ukrainian Premier League",
        "country":        "Ukraine",
    },

    # ─────────────────────────── ÉQUIPES NATIONALES ───────────────────────────
    "france": {
        "canonical_name": "France",
        "short_name":     "France",
        "aliases":        ["france", "french team", "les bleus", "équipe de france", "法国", "法兰西"],
        "league":         "National Teams",
        "country":        "France",
    },
    "germany": {
        "canonical_name": "Germany",
        "short_name":     "Germany",
        "aliases":        ["germany", "deutschland", "allemagne", "deutsche mannschaft", "德国", "德意志"],
        "league":         "National Teams",
        "country":        "Germany",
    },
    "italy": {
        "canonical_name": "Italy",
        "short_name":     "Italy",
        "aliases":        ["italy", "italia", "italie", "azzurri", "意大利"],
        "league":         "National Teams",
        "country":        "Italy",
    },
    "spain": {
        "canonical_name": "Spain",
        "short_name":     "Spain",
        "aliases":        ["spain", "españa", "espagne", "espana", "la roja", "西班牙"],
        "league":         "National Teams",
        "country":        "Spain",
    },
    "england": {
        "canonical_name": "England",
        "short_name":     "England",
        "aliases":        ["england", "angleterre", "three lions", "英格兰", "英国"],
        "league":         "National Teams",
        "country":        "England",
    },
    "portugal": {
        "canonical_name": "Portugal",
        "short_name":     "Portugal",
        "aliases":        ["portugal", "selecção", "seleção", "quinas", "葡萄牙"],
        "league":         "National Teams",
        "country":        "Portugal",
    },
    "netherlands": {
        "canonical_name": "Netherlands",
        "short_name":     "Netherlands",
        "aliases":        ["netherlands", "holland", "pays-bas", "oranje", "荷兰"],
        "league":         "National Teams",
        "country":        "Netherlands",
    },
    "belgium": {
        "canonical_name": "Belgium",
        "short_name":     "Belgium",
        "aliases":        ["belgium", "belgique", "belgie", "red devils national", "比利时"],
        "league":         "National Teams",
        "country":        "Belgium",
    },
    "brazil": {
        "canonical_name": "Brazil",
        "short_name":     "Brazil",
        "aliases":        ["brazil", "brasil", "brésil", "canarinha", "seleção brasileira", "巴西"],
        "league":         "National Teams",
        "country":        "Brazil",
    },
    "argentina": {
        "canonical_name": "Argentina",
        "short_name":     "Argentina",
        "aliases":        ["argentina", "argentine", "albiceleste", "la albiceleste", "阿根廷"],
        "league":         "National Teams",
        "country":        "Argentina",
    },
    "croatia": {
        "canonical_name": "Croatia",
        "short_name":     "Croatia",
        "aliases":        ["croatia", "croatie", "hrvatska", "vatreni", "克罗地亚"],
        "league":         "National Teams",
        "country":        "Croatia",
    },
    "morocco": {
        "canonical_name": "Morocco",
        "short_name":     "Morocco",
        "aliases":        ["morocco", "maroc", "atlas lions", "المغرب", "摩洛哥"],
        "league":         "National Teams",
        "country":        "Morocco",
    },
    "senegal": {
        "canonical_name": "Senegal",
        "short_name":     "Senegal",
        "aliases":        ["senegal", "sénégal", "lions of teranga", "塞内加尔"],
        "league":         "National Teams",
        "country":        "Senegal",
    },
    "nigeria": {
        "canonical_name": "Nigeria",
        "short_name":     "Nigeria",
        "aliases":        ["nigeria", "super eagles", "尼日利亚"],
        "league":         "National Teams",
        "country":        "Nigeria",
    },
    "ivory coast": {
        "canonical_name": "Ivory Coast",
        "short_name":     "Ivory Coast",
        "aliases":        ["ivory coast", "côte d'ivoire", "cote d'ivoire", "elephants", "科特迪瓦"],
        "league":         "National Teams",
        "country":        "Ivory Coast",
    },
    "cape verde": {
        "canonical_name": "Cape Verde",
        "short_name":     "Cape Verde",
        "aliases":        ["cape verde", "cabo verde", "佛得角"],
        "league":         "National Teams",
        "country":        "Cape Verde",
    },
    "ghana": {
        "canonical_name": "Ghana",
        "short_name":     "Ghana",
        "aliases":        ["ghana", "black stars", "加纳"],
        "league":         "National Teams",
        "country":        "Ghana",
    },
    "egypt": {
        "canonical_name": "Egypt",
        "short_name":     "Egypt",
        "aliases":        ["egypt", "égypte", "egypte", "pharaohs", "مصر", "埃及"],
        "league":         "National Teams",
        "country":        "Egypt",
    },
    "cameroon": {
        "canonical_name": "Cameroon",
        "short_name":     "Cameroon",
        "aliases":        ["cameroon", "cameroun", "indomitable lions", "喀麦隆"],
        "league":         "National Teams",
        "country":        "Cameroon",
    },
    "algeria": {
        "canonical_name": "Algeria",
        "short_name":     "Algeria",
        "aliases":        ["algeria", "algérie", "algerie", "fennecs", "الجزائر", "阿尔及利亚"],
        "league":         "National Teams",
        "country":        "Algeria",
    },
    "tunisia": {
        "canonical_name": "Tunisia",
        "short_name":     "Tunisia",
        "aliases":        ["tunisia", "tunisie", "eagles of carthage", "تونس", "突尼斯"],
        "league":         "National Teams",
        "country":        "Tunisia",
    },
    "colombia": {
        "canonical_name": "Colombia",
        "short_name":     "Colombia",
        "aliases":        ["colombia", "colombie", "los cafeteros", "哥伦比亚"],
        "league":         "National Teams",
        "country":        "Colombia",
    },
    "uruguay": {
        "canonical_name": "Uruguay",
        "short_name":     "Uruguay",
        "aliases":        ["uruguay", "celeste", "la celeste", "乌拉圭"],
        "league":         "National Teams",
        "country":        "Uruguay",
    },
    "mexico": {
        "canonical_name": "Mexico",
        "short_name":     "Mexico",
        "aliases":        ["mexico", "mexique", "tri", "el tri", "墨西哥"],
        "league":         "National Teams",
        "country":        "Mexico",
    },
    "usa": {
        "canonical_name": "United States",
        "short_name":     "USA",
        "aliases":        ["usa", "united states", "états-unis", "etats-unis", "usmnt", "美国"],
        "league":         "National Teams",
        "country":        "United States",
    },
    "japan": {
        "canonical_name": "Japan",
        "short_name":     "Japan",
        "aliases":        ["japan", "japon", "samurai blue", "日本", "日本代表"],
        "league":         "National Teams",
        "country":        "Japan",
    },
    "south korea": {
        "canonical_name": "South Korea",
        "short_name":     "South Korea",
        "aliases":        ["south korea", "korea", "corée du sud", "coree du sud", "taeguk warriors", "韩国", "朝鲜"],
        "league":         "National Teams",
        "country":        "South Korea",
    },
    "saudi arabia": {
        "canonical_name": "Saudi Arabia",
        "short_name":     "Saudi Arabia",
        "aliases":        ["saudi arabia", "arabie saoudite", "green falcons", "السعودية", "沙特阿拉伯"],
        "league":         "National Teams",
        "country":        "Saudi Arabia",
    },
    "australia": {
        "canonical_name": "Australia",
        "short_name":     "Australia",
        "aliases":        ["australia", "australie", "socceroos", "澳大利亚"],
        "league":         "National Teams",
        "country":        "Australia",
    },
    "switzerland": {
        "canonical_name": "Switzerland",
        "short_name":     "Switzerland",
        "aliases":        ["switzerland", "suisse", "schweiz", "nati", "瑞士"],
        "league":         "National Teams",
        "country":        "Switzerland",
    },
    "poland": {
        "canonical_name": "Poland",
        "short_name":     "Poland",
        "aliases":        ["poland", "pologne", "polska", "biało-czerwoni", "波兰"],
        "league":         "National Teams",
        "country":        "Poland",
    },
    "denmark": {
        "canonical_name": "Denmark",
        "short_name":     "Denmark",
        "aliases":        ["denmark", "danemark", "danish dynamite", "丹麦"],
        "league":         "National Teams",
        "country":        "Denmark",
    },
    "norway": {
        "canonical_name": "Norway",
        "short_name":     "Norway",
        "aliases":        ["norway", "norvège", "norvege", "norge", "挪威"],
        "league":         "National Teams",
        "country":        "Norway",
    },
    "sweden": {
        "canonical_name": "Sweden",
        "short_name":     "Sweden",
        "aliases":        ["sweden", "suède", "suede", "sverige", "blågult", "瑞典"],
        "league":         "National Teams",
        "country":        "Sweden",
    },
    "turkey": {
        "canonical_name": "Turkey",
        "short_name":     "Turkey",
        "aliases":        ["turkey", "turquie", "türkiye", "turkiye", "turks", "土耳其"],
        "league":         "National Teams",
        "country":        "Turkey",
    },
    "iran": {
        "canonical_name": "Iran",
        "short_name":     "Iran",
        "aliases":        ["iran", "team melli", "ایران", "伊朗"],
        "league":         "National Teams",
        "country":        "Iran",
    },

    # ───────────────────────── CLUBS SAOUDIENS / MLS ──────────────────────────
    "al hilal": {
        "canonical_name": "Al Hilal SFC",
        "short_name":     "Al Hilal",
        "aliases":        ["al hilal", "hilal", "النصر", "الهلال", "蓝月亮"],
        "league":         "Saudi Pro League",
        "country":        "Saudi Arabia",
    },
    "al nassr": {
        "canonical_name": "Al Nassr FC",
        "short_name":     "Al Nassr",
        "aliases":        ["al nassr", "nassr", "النصر", "阿尔纳斯尔"],
        "league":         "Saudi Pro League",
        "country":        "Saudi Arabia",
    },
    "al ittihad": {
        "canonical_name": "Al Ittihad Club",
        "short_name":     "Al Ittihad",
        "aliases":        ["al ittihad", "ittihad", "الاتحاد"],
        "league":         "Saudi Pro League",
        "country":        "Saudi Arabia",
    },
    "inter miami": {
        "canonical_name": "Inter Miami CF",
        "short_name":     "Inter Miami",
        "aliases":        ["inter miami", "miami", "imcf", "herons"],
        "league":         "MLS",
        "country":        "United States",
    },
    "la galaxy": {
        "canonical_name": "LA Galaxy",
        "short_name":     "LA Galaxy",
        "aliases":        ["la galaxy", "galaxy", "los angeles galaxy"],
        "league":         "MLS",
        "country":        "United States",
    },

    # ──────────────────────────── CLUBS SUDAMÉRICAINS ─────────────────────────
    "boca juniors": {
        "canonical_name": "Club Atlético Boca Juniors",
        "short_name":     "Boca Juniors",
        "aliases":        ["boca juniors", "boca", "xeneize", "博卡青年"],
        "league":         "Liga Profesional",
        "country":        "Argentina",
    },
    "river plate": {
        "canonical_name": "Club Atlético River Plate",
        "short_name":     "River Plate",
        "aliases":        ["river plate", "river", "millonarios", "河床"],
        "league":         "Liga Profesional",
        "country":        "Argentina",
    },
    "flamengo": {
        "canonical_name": "Clube de Regatas do Flamengo",
        "short_name":     "Flamengo",
        "aliases":        ["flamengo", "fla", "mengão", "flamengo rj", "弗拉门戈"],
        "league":         "Brasileirão",
        "country":        "Brazil",
    },
    "palmeiras": {
        "canonical_name": "Sociedade Esportiva Palmeiras",
        "short_name":     "Palmeiras",
        "aliases":        ["palmeiras", "porco", "verdão"],
        "league":         "Brasileirão",
        "country":        "Brazil",
    },
    "corinthians": {
        "canonical_name": "Sport Club Corinthians Paulista",
        "short_name":     "Corinthians",
        "aliases":        ["corinthians", "timão", "corinthians paulista"],
        "league":         "Brasileirão",
        "country":        "Brazil",
    },
    "santos": {
        "canonical_name": "Santos FC",
        "short_name":     "Santos",
        "aliases":        ["santos", "santos fc", "peixe"],
        "league":         "Brasileirão",
        "country":        "Brazil",
    },
    "sao paulo": {
        "canonical_name": "São Paulo FC",
        "short_name":     "São Paulo",
        "aliases":        ["sao paulo", "são paulo", "spfc", "tricolor paulista"],
        "league":         "Brasileirão",
        "country":        "Brazil",
    },
    "fluminense": {
        "canonical_name": "Fluminense FC",
        "short_name":     "Fluminense",
        "aliases":        ["fluminense", "flu", "tricolor carioca"],
        "league":         "Brasileirão",
        "country":        "Brazil",
    },
    "atletico mineiro": {
        "canonical_name": "Clube Atlético Mineiro",
        "short_name":     "Atlético Mineiro",
        "aliases":        ["atletico mineiro", "atlético mineiro", "galo", "galo atletico"],
        "league":         "Brasileirão",
        "country":        "Brazil",
    },
    "botafogo": {
        "canonical_name": "Botafogo de Futebol e Regatas",
        "short_name":     "Botafogo",
        "aliases":        ["botafogo", "bfr", "glorioso"],
        "league":         "Brasileirão",
        "country":        "Brazil",
    },
    "vasco da gama": {
        "canonical_name": "Club de Regatas Vasco da Gama",
        "short_name":     "Vasco",
        "aliases":        ["vasco da gama", "vasco", "crvg"],
        "league":         "Brasileirão",
        "country":        "Brazil",
    },
    "gremio": {
        "canonical_name": "Grêmio FBPA",
        "short_name":     "Grêmio",
        "aliases":        ["gremio", "grêmio", "tricolor gaucho"],
        "league":         "Brasileirão",
        "country":        "Brazil",
    },
    "colo-colo": {
        "canonical_name": "Club Social y Deportivo Colo-Colo",
        "short_name":     "Colo-Colo",
        "aliases":        ["colo-colo", "colo colo", "cacique"],
        "league":         "Primera División Chile",
        "country":        "Chile",
    },
    "nacional": {
        "canonical_name": "Club Nacional de Football",
        "short_name":     "Nacional",
        "aliases":        ["nacional", "club nacional", "bolso"],
        "league":         "Primera División Uruguay",
        "country":        "Uruguay",
    },
    "peñarol": {
        "canonical_name": "Club Atlético Peñarol",
        "short_name":     "Peñarol",
        "aliases":        ["peñarol", "peñarol montevideo", "carboneros"],
        "league":         "Primera División Uruguay",
        "country":        "Uruguay",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# INDEX DE RECHERCHE (construit au chargement du module)
# ══════════════════════════════════════════════════════════════════════════════

# Construire un index plat : alias_lower → clé du TEAM_DATABASE
_ALIAS_INDEX: dict[str, str] = {}

for _key, _data in TEAM_DATABASE.items():
    for _alias in _data.get("aliases", []):
        _ALIAS_INDEX[_alias.lower()] = _key
    _ALIAS_INDEX[_key.lower()] = _key
    _ALIAS_INDEX[_data["canonical_name"].lower()] = _key
    _ALIAS_INDEX[_data["short_name"].lower()] = _key

# Liste de tous les alias pour le fuzzy matching
_ALL_ALIASES = list(_ALIAS_INDEX.keys())


# ══════════════════════════════════════════════════════════════════════════════
# DICTIONNAIRE TYPE DE MAILLOT
# ══════════════════════════════════════════════════════════════════════════════
TYPE_MAPPING = {
    # Anglais
    "home":      "Home",
    "away":      "Away",
    "third":     "Third",
    "fourth":    "Fourth",
    "alternate": "Third",
    "gk":        "Goalkeeper",
    "goalkeeper":"Goalkeeper",
    "keeper":    "Goalkeeper",
    "training":  "Training",
    "pre-match": "Training",
    "special":   "Special",
    "anniversary":"Special",
    "commemorative":"Special",

    # Français
    "domicile":  "Home",
    "extérieur": "Away",
    "exterieur": "Away",
    "troisième": "Third",
    "quatrième": "Fourth",
    "gardien":   "Goalkeeper",
    "entrainement": "Training",
    "spécial":   "Special",

    # Chinois
    "主场":       "Home",
    "客场":       "Away",
    "第三":       "Third",
    "第三套":     "Third",
    "门将":       "Goalkeeper",
    "守门员":     "Goalkeeper",
    "训练":       "Training",
    "特别版":     "Special",
    "纪念":       "Special",   # anniversaire/commémoratif
    "周年":       "Special",   # anniversaire
    # Formes abrégées courantes dans les titres Yupoo (doit venir APRÈS les formes longues)
    "主":         "Home",      # abrév. de 主场
    "客":         "Away",      # abrév. de 客场

    # Espagnol/Portugais
    "local":     "Home",
    "visitante": "Away",
    "alternativo": "Third",
    "portero":   "Goalkeeper",
    "casa":      "Home",
    "fora":      "Away",
}

# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION D'INFORMATIONS DEPUIS UN TITRE YUPOO
# ══════════════════════════════════════════════════════════════════════════════

# Patterns de saisons
_SEASON_PATTERNS = [
    # 24/25, 24-25, 2024/25, 2024-25, 2024/2025, 24/2025
    r"\b(20)?(\d{2})[/-](20)?(\d{2})\b",
    # 2024, 2025
    r"\b(202[0-9])\b",
    # Retro : 98-99, 1998-99, etc.
    r"\b(19\d{2})[/-](\d{2,4})\b",
    r"\b(\d{2})[/-](\d{2})\b",
    # Format compact chinois : 2425 → 24/25, 2627 → 26/27 (années consécutives)
    # \b ne fonctionne pas après un chiffre suivi d'un caractère chinois (\w)
    # → utiliser lookahead/lookbehind sur les chiffres uniquement
    r"(?<![0-9])(2[0-9])([0-9]{2})(?![0-9])",
]

# Patterns de manches longues
_LONG_SLEEVE_PATTERNS = [
    r"\blong\s*sleeve\b",
    r"\bml\b",
    r"\bmanches?\s*longues?\b",
    r"\blong\b.*\bsleeve\b",
    r"长袖",
]


def normalize_text(s: str) -> str:
    """Normalise le texte : minuscules, retrait des accents courants."""
    if not s:
        return ""
    s = s.lower().strip()
    # Remplacements de caractères accentués fréquents
    replacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "ä": "a",
        "ô": "o", "ö": "o", "ò": "o",
        "ü": "u", "ù": "u", "û": "u",
        "î": "i", "ï": "i",
        "ç": "c",
        "ñ": "n",
        "ã": "a", "õ": "o",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s


def extract_season(title: str) -> Optional[str]:
    """Extrait la saison depuis un titre. Ex: '24-25 PSG' → '2024-25'"""
    for pattern in _SEASON_PATTERNS:
        m = re.search(pattern, title)
        if not m:
            continue
        groups = m.groups()
        if len(groups) == 4:
            # Pattern XX/YY ou 20XX/YY
            y1 = groups[1]  # 2 derniers chiffres de l'année 1
            y2 = groups[3]  # 2 derniers chiffres de l'année 2
            year1 = int("20" + y1) if len(y1) == 2 else int(y1)
            year2 = int("20" + y2) if len(y2) == 2 else int(y2)
            if abs(year2 - year1) <= 1:
                return f"{year1}-{str(year2)[-2:]}"
        elif len(groups) == 1:
            # Année seule
            y = int(groups[0])
            return str(y)
        elif len(groups) == 2:
            g0, g1 = groups[0], groups[1]
            # Format compact 2 chiffres chacun : "2627" → 26/27 → 2026-27
            if len(g0) == 2 and len(g1) == 2:
                y1 = int("20" + g0)
                y2 = int("20" + g1)
                if y2 == y1 + 1:
                    return f"{y1}-{g1}"
                # Pas consécutif → ignorer ce pattern
                continue
            # Rétro XX-YY ou XXXX-YY
            y1 = int(g0) if len(g0) == 4 else int("19" + g0)
            y2 = int(g1) if len(g1) == 4 else (
                int("20" + g1) if int(g1) < 50 else int("19" + g1)
            )
            return f"{y1}-{str(y2)[-2:]}"
    return None


def extract_jersey_type(title: str) -> str:
    """Extrait le type de maillot (Home/Away/Third/etc.) depuis un titre."""
    title_lower = title.lower()
    for keyword, jersey_type in TYPE_MAPPING.items():
        if keyword in title_lower:
            return jersey_type
    return "Unknown"


def extract_sleeve_type(title: str) -> str:
    """Détecte si le maillot est à manches longues."""
    title_lower = title.lower()
    for pattern in _LONG_SLEEVE_PATTERNS:
        if re.search(pattern, title_lower):
            return "long"
    return "short"


def find_team_exact(text: str) -> Optional[tuple[str, float]]:
    """
    Cherche une équipe par match exact sur les alias.
    Retourne (clé_team, score=1.0) ou None.
    """
    t = text.lower().strip()
    # Match exact
    if t in _ALIAS_INDEX:
        return (_ALIAS_INDEX[t], 1.0)

    # Chercher si un alias est contenu dans le texte
    # (du plus long au plus court pour éviter les faux positifs)
    text_norm = normalize_text(t)
    candidates = sorted(_ALIAS_INDEX.keys(), key=len, reverse=True)
    for alias in candidates:
        # Autoriser les alias de 2 chars CJK (ex: 皇马, 巴西) ; filtrer seulement les alias Latin < 3 chars
        if len(alias) < 2:
            continue
        if len(alias) == 2 and all(ord(c) < 0x4E00 for c in alias):
            continue  # alias Latin de 2 chars → trop court, risque de faux positifs
        alias_norm = normalize_text(alias)
        if alias_norm in text_norm:
            return (_ALIAS_INDEX[alias], 0.95)

    return None


def find_team_fuzzy(text: str, threshold: int = 75) -> Optional[tuple[str, float]]:
    """
    Fuzzy match sur tous les alias connus.
    Retourne (clé_team, score/100) ou None si sous le seuil.
    """
    text_norm = normalize_text(text)
    if not text_norm or len(text_norm) < 3:
        return None

    # Utiliser rapidfuzz pour trouver le meilleur match
    result = process.extractOne(
        text_norm,
        _ALL_ALIASES,
        scorer=fuzz.token_set_ratio,
        score_cutoff=threshold,
    )

    if result:
        matched_alias, score, _ = result
        team_key = _ALIAS_INDEX[matched_alias]
        return (team_key, score / 100.0)

    return None


def extract_team_from_title(title: str) -> Optional[tuple[str, float]]:
    """
    Méthode principale : tente d'extraire le nom d'équipe depuis un titre Yupoo.
    Essaie d'abord exact, puis fuzzy sur des sous-parties du titre.
    Retourne (clé_team, confidence) ou None.
    """
    if not title:
        return None

    # 1. Match exact sur tout le titre
    result = find_team_exact(title)
    if result:
        return result

    # 2. Nettoyer le titre et tenter un fuzzy match sur des portions
    # Retirer les infos de saison et type pour isoler le nom d'équipe
    cleaned = title
    # Retirer les saisons
    cleaned = re.sub(r"\b(20)?\d{2}[/-](20)?\d{2}\b", "", cleaned)
    cleaned = re.sub(r"\b(202[0-9])\b", "", cleaned)
    cleaned = re.sub(r"\b(19\d{2})[/-]\d{2,4}\b", "", cleaned)
    # Retirer les mots de type
    type_words = list(TYPE_MAPPING.keys())
    for w in sorted(type_words, key=len, reverse=True):
        cleaned = re.sub(r"\b" + re.escape(w) + r"\b", "", cleaned, flags=re.IGNORECASE)
    # Retirer mots génériques
    for w in ["jersey", "shirt", "kit", "maillot", "version", "fan", "player", "retro", "long", "sleeve", "ml"]:
        cleaned = re.sub(r"\b" + re.escape(w) + r"\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()

    if cleaned:
        result = find_team_exact(cleaned)
        if result:
            return result

        result = find_team_fuzzy(cleaned)
        if result:
            return result

    # 3. Fuzzy sur le titre entier nettoyé
    result = find_team_fuzzy(title)
    return result


def get_team_info(team_key: str) -> dict:
    """Retourne les infos complètes d'une équipe depuis sa clé."""
    return TEAM_DATABASE.get(team_key, {})


def extract_product_info(title: str, version: str = "fan") -> dict:
    """
    Analyse complète d'un titre d'album Yupoo.
    Retourne un dict avec toutes les informations extraites.

    Args:
        title:   Titre de l'album Yupoo (ex: "24-25 巴黎圣日耳曼 主场")
        version: Version du catalogue ("fan", "player", "retro", "kit")

    Returns:
        {
            "team":             "Paris Saint-Germain FC",
            "team_short":       "PSG",
            "team_key":         "paris saint-germain",
            "team_aliases":     [...],
            "league":           "Ligue 1",
            "country":          "France",
            "season":           "2024-25",
            "type":             "Home",
            "version":          "fan",
            "sleeve":           "short",
            "confidence":       0.98,
            "matched":          True,
        }
    """
    result = {
        "team":         "Unknown",
        "team_short":   "Unknown",
        "team_key":     None,
        "team_aliases": [],
        "league":       "",
        "country":      "",
        "season":       extract_season(title) or "",
        "type":         extract_jersey_type(title),
        "version":      version,
        "sleeve":       extract_sleeve_type(title),
        "confidence":   0.0,
        "matched":      False,
        "raw_title":    title,
    }

    # Extraire l'équipe
    team_result = extract_team_from_title(title)
    if team_result:
        team_key, confidence = team_result
        team_data = get_team_info(team_key)
        result.update({
            "team":         team_data.get("canonical_name", team_key),
            "team_short":   team_data.get("short_name", team_key),
            "team_key":     team_key,
            "team_aliases": team_data.get("aliases", []),
            "league":       team_data.get("league", ""),
            "country":      team_data.get("country", ""),
            "confidence":   confidence,
            "matched":      confidence >= 0.75,
        })

    return result


# ── Tests rapides ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_titles = [
        "24-25 巴黎圣日耳曼 主场",
        "2024/25 PSG Home Jersey",
        "Retro 06-07 AC Milan Home",
        "24/25 Real Madrid Away",
        "2024 Manchester City Third Kit",
        "Barcleona Home 24-25",           # faute de frappe
        "23-24 皇马 客场",                # Real Madrid Away (chinois)
        "24-25 Bayern Munich Home Long Sleeve",
        "France Home 2024 Euro",
        "24-25 Maillot Extérieur Arsenal",
        "Egypt Home Kit 2024",
    ]

    print("=" * 60)
    for title in test_titles:
        info   = extract_product_info(title, "fan")
        status = "OK" if info["matched"] else "!!"
        safe   = title.encode("ascii", "replace").decode("ascii")[:40]
        print(f"[{status}][{info['confidence']:.2f}] {safe:<40} -> {info['team_short']:20} | {info['season']:7} | {info['type']}")

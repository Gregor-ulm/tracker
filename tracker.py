import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build

# API-Key sicher aus GitHub Secrets laden
API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    print("Fehler: Kein YOUTUBE_API_KEY gefunden!")
    sys.exit(1)

# Kanäle definieren
KANAL_LISTE = {
    "UCX6OQ3DkcsbYNE6H8uQQuVA": "MrBeast",
    "UCsXVk37bltHxD1rDPwtNM8Q": "Kurzgesagt",
    "UCUHW94eEFW7hkUMVaZz4eDg": "Minutephysics",
    "UCUK0HBIBWgM2c4vsPhkYY4w": "SlowMoGuys",
    "UCY1kMZp36IQSyNx_9h4mpCg": "MarkRober",
    "UCqECaJ8Gagnn7YCbPEzWH6g": "TaylorSwift",
    "UCgmHVWU9vo_Y4fiQSCfGGRw": "Brotatos",
    "UCgZpwegd4AdDlZNrIamIgRw": "BastiGHG",
    "UCDmbhGe7-wC1a55l5ZYAZJw": "Papaplatte",
    "UCfdNM3NAhaBOXCafH7krzrA": "The Infographics Show"
}

MAX_TRACKING_VIDEOS = 10
MAX_ALTER_MINUTEN = 15  # Passend zum stündlichen Cronjob
MAX_TRACKING_STUNDEN = 720  # 30 Tage
STATUS_DATEI = "status.json"

youtube = build('youtube', 'v3', developerKey=API_KEY)


def lade_status():
    """Lädt die Liste der aktiven Videos aus der status.json."""
    if os.path.exists(STATUS_DATEI):
        try:
            with open(STATUS_DATEI, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Fehler beim Laden von status.json: {e}")
    return {}


def speichere_status(aktive_videos):
    """Speichert die aktive Video-Liste ab."""
    with open(STATUS_DATEI, "w", encoding="utf-8") as f:
        json.dump(aktive_videos, f, ensure_ascii=False, indent=2)


def hole_video_details(video_id):
    """Holt Titel und Kanalname für die Kopfzeile der TXT-Datei."""
    try:
        request = youtube.videos().list(part="snippet", id=video_id)
        response = request.execute()
        items = response.get('items', [])
        if items:
            snippet = items[0]['snippet']
            titel = snippet['title'].replace("\n", " ")  # Einzeilig halten
            kanal = snippet['channelTitle']
            return titel, kanal
    except Exception as e:
        print(f"Fehler beim Holen der Video-Details für {video_id}: {e}")
    return "Unbekannter Titel", "Unbekannter Kanal"


def scanne_nach_neuem_video(bereits_getrackt_ids):
    """Scannt Kanäle nach neuen Uploads, die noch nicht getrackt werden."""
    print("Scanne Kanäle nach neuen Uploads...")
    for kanal_id, kanal_name in KANAL_LISTE.items():
        try:
            request = youtube.search().list(
                channelId=kanal_id,
                part="snippet",
                type="video",
                order="date",
                maxResults=1
            )
            response = request.execute()
            items = response.get('items', [])
            if not items:
                continue

            erstes_video = items[0]
            video_id = erstes_video['id']['videoId']

            # Überprüfen, ob das Video bereits getrackt wird
            if video_id in bereits_getrackt_ids:
                continue

            pub_zeit_str = erstes_video['snippet']['publishedAt']
            pub_zeit = datetime.fromisoformat(pub_zeit_str.replace("Z", "+00:00"))
            alter = datetime.now(timezone.utc) - pub_zeit

            if alter < timedelta(minutes=MAX_ALTER_MINUTEN):
                print(f"🔥 NEUES VIDEO GEFUNDEN: {video_id} ({kanal_name})")
                return video_id
        except Exception as e:
            print(f"Fehler bei Radar für {kanal_name}: {e}")
    return None


def hole_views_mehrere(video_ids):
    """Holt View-Counts für bis zu 50 Videos in EINEM API-Aufruf."""
    if not video_ids:
        return {}

    ids_string = ",".join(video_ids)
    try:
        request = youtube.videos().list(part="statistics", id=ids_string)
        response = request.execute()
        
        ergebnisse = {}
        for item in response.get('items', []):
            v_id = item['id']
            views = int(item['statistics']['viewCount'])
            ergebnisse[v_id] = views
        return ergebnisse
    except Exception as e:
        print(f"Fehler beim Abrufen der Aufrufe: {e}")
        return {}


# ==========================================
# HAUPTLOGIK
# ==========================================

aktive_videos = lade_status()
jetzt_ts = time.time()

# 1. Abgelaufene Videos (älter als 30 Tage) entfernen
abgelaufen = []
for v_id, info in aktive_videos.items():
    vergangene_stunden = (jetzt_ts - info["start_zeit"]) / 3600.0
    if vergangene_stunden > MAX_TRACKING_STUNDEN:
        abgelaufen.append(v_id)

for v_id in abgelaufen:
    print(f"Tracking beendet für {v_id} (30 Tage abgelaufen).")
    del aktive_videos[v_id]

# 2. RADAR: Scannen, falls noch freie Tracking-Plätze da sind (< 10)
if len(aktive_videos) < MAX_TRACKING_VIDEOS:
    neues_video_id = scanne_nach_neuem_video(bereits_getrackt_ids=list(aktive_videos.keys()))
    
    if neues_video_id:
        titel, kanal = hole_video_details(neues_video_id)
        link = f"https://www.youtube.com/watch?v={neues_video_id}"
        
        # In Status-Liste aufnehmen
        aktive_videos[neues_video_id] = {
            "start_zeit": jetzt_ts,
            "titel": titel,
            "kanal": kanal
        }
        
        # Neue TXT-Datei anlegen (mit Meta-Daten in Zeile 1)
        datei_pfad = f"tracking_{neues_video_id}.txt"
        with open(datei_pfad, "w", encoding="utf-8") as f:
            f.write(f"Titel: {titel} | Kanal: {kanal} | Link: {link}\n")
            f.write("Zeit_in_h, Aufrufe\n")
        print(f"Tracking-Datei erstellt: {datei_pfad}")
else:
    print(f"Radar pausiert: Maximale Anzahl an Videos ({MAX_TRACKING_VIDEOS}) erreicht.")

# 3. TRACKING: Aufrufzahlen für alle aktiven Videos erfassen
if aktive_videos:
    views_dict = hole_views_mehrere(list(aktive_videos.keys()))
    
    for v_id, info in aktive_videos.items():
        views = views_dict.get(v_id)
        if views is not None:
            vergangene_stunden = (jetzt_ts - info["start_zeit"]) / 3600.0
            datei_pfad = f"tracking_{v_id}.txt"
            
            with open(datei_pfad, "a", encoding="utf-8") as f:
                f.write(f"{vergangene_stunden:.4f}, {views}\n")
            print(f"Eintrag [{v_id}]: {vergangene_stunden:.2f}h -> {views} Views.")
else:
    print("Keine aktiven Videos zum Tracken vorhanden.")

# Aktuellen Stand abspeichern
speichere_status(aktive_videos)
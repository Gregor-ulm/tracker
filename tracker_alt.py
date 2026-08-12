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
    "UCDmbhGe7-wC1a55l5ZYAZJw": "Papaplatte"
}

MAX_ALTER_MINUTEN = 65 # Erhöht auf 65, da GitHub stündlich läuft
youtube = build('youtube', 'v3', developerKey=API_KEY)

def hole_status():
    """Liest den aktuellen Modus (Radar oder Tracking) aus."""
    if not os.path.exists("status.txt"):
        return "RADAR", None, None
    with open("status.txt", "r") as f:
        zeilen = f.read().splitlines()
        if len(zeilen) >= 3:
            return zeilen[0], zeilen[1], float(zeilen[2])
    return "RADAR", None, None

def schreibe_status(modus, video_id, start_zeit):
    with open("status.txt", "w") as f:
        f.write(f"{modus}\n{video_id}\n{start_zeit}")

def scanne_nach_neuem_video():
    print("Scanne Kanäle nach neuen Uploads...")
    for kanal_id, kanal_name in KANAL_LISTE.items():
        try:
            request = youtube.search().list(channelId=kanal_id, part="snippet", type="video", order="date", maxResults=1)
            response = request.execute()
            items = response.get('items', [])
            if not items: continue

            erstes_video = items[0]
            video_id = erstes_video['id']['videoId']
            pub_zeit_str = erstes_video['snippet']['publishedAt']

            pub_zeit = datetime.fromisoformat(pub_zeit_str.replace("Z", "+00:00"))
            alter = datetime.now(timezone.utc) - pub_zeit

            if alter < timedelta(minutes=MAX_ALTER_MINUTEN):
                print(f"🔥 NEUES VIDEO GEFUNDEN: {video_id}")
                return video_id
        except Exception as e:
            print(f"Fehler bei {kanal_name}: {e}")
    return None

def hole_views(video_id):
    try:
        request = youtube.videos().list(part="statistics", id=video_id)
        response = request.execute()
        return int(response['items'][0]['statistics']['viewCount'])
    except:
        return None

# Hauptlogik für den stündlichen GitHub-Aufruf
modus, aktives_video, start_zeit = hole_status()

if modus == "RADAR":
    video_id = scanne_nach_neuem_video()
    if video_id:
        schreibe_status("TRACKING", video_id, time.time())
        # Erste Messung direkt anlegen
        views = hole_views(video_id)
        with open(f"tracking_{video_id}.txt", "w") as f:
            f.write(f"Zeit_in_h, Aufrufe\n0.0000, {views}\n")
    else:
        print("Kein neues Video in der letzten Stunde.")

elif modus == "TRACKING":
    vergangene_stunden = (time.time() - start_zeit) / 3600.0
    if vergangene_stunden > 720: # Nach 30 Tagen beenden
        print("Tracking-Zeitraum abgelaufen.")
        schreibe_status("RADAR", "", "")
    else:
        views = hole_views(aktives_video)
        if views:
            with open(f"tracking_{aktives_video}.txt", "a") as f:
                f.write(f"{vergangene_stunden:.4f}, {views}\n")
            print(f"Eintrag hinzugefügt: {vergangene_stunden:.2f}h -> {views} Views.")

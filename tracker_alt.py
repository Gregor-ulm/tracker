import time
import os
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build

# ==========================================
# KONFIGURATION
# ==========================================
API_KEY = "AIzaSyDn6o8WZ7cmtUzzGzdZMSyl5pgY8SPN3QM"  # Ersetzen Sie dies mit Ihrem YouTube API Key

# WICHTIG FÜR PYTHONANYWHERE FREE PLAN: Proxy aktivieren
os.environ["https_proxy"] = "http://proxy.server:3128"

# Liste der großen Kanäle (Kanal-ID: Name)
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
#Möglich: moistcritical, marcant
RADAR_INTERVALL = 7200       # Alle 2 Minuten nach neuen Uploads suchen
MAX_ALTER_MINUTEN = 10      # Ein Video gilt als brandneu, wenn es jünger als X Minuten ist

# API-Client initialisieren
youtube = build('youtube', 'v3', developerKey=API_KEY)

# ==========================================
# FUNKTIONEN
# ==========================================

def scanne_nach_neuem_video():
    """Scannt die Kanäle und gibt die Video-ID zurück, sobald ein neues gefunden wird."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Scanne Kanäle nach neuen Uploads...")

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

            # KORREKTUR: Greife auf das erste Element [0] der Liste zu
            erstes_video = items[0]
            video_id = erstes_video['id']['videoId']
            titel = erstes_video['snippet']['title']
            pub_zeit_str = erstes_video['snippet']['publishedAt']

            pub_zeit = datetime.fromisoformat(pub_zeit_str.replace("Z", "+00:00"))
            jetzt = datetime.now(timezone.utc)
            alter = jetzt - pub_zeit

            if alter < timedelta(minutes=MAX_ALTER_MINUTEN):
                print(f"\n🔥 NEUES VIDEO GEFUNDEN BEI {kanal_name.upper()}!")
                print(f"Video-ID: {video_id} | Titel: {titel}")
                return video_id

        except Exception as e:
            print(f"Fehler beim Scannen von {kanal_name}: {e}")
    print("Noch nichts gefunden")
    return None



def hole_aktuelle_aufrufe(video_id):
    """Fragt die exakte aktuelle Aufrufzahl eines Videos ab."""
    try:
        request = youtube.videos().list(
            part="statistics",
            id=video_id
        )
        response = request.execute()
        items = response.get('items', [])
        if items:
            return int(items['statistics']['viewCount'])
    except Exception as e:
        print(f"Fehler bei der View-Abfrage: {e}")
    return None


def bestimme_wartezeit_sekunden(vergangene_stunden):
    """Berechnet dynamisch das nächste Messintervall basierend auf dem Video-Alter."""
    if vergangene_stunden <= 2:
        return 60         # 1 Minute
    elif vergangene_stunden <= 12:
        return 300        # 5 Minuten
    elif vergangene_stunden <= 24:
        return 900        # 15 Minuten
    elif vergangene_stunden <= 72:
        return 1800       # 30 Minuten
    elif vergangene_stunden <= 720:
        return 3600       # 60 Minuten (bis zu 30 Tage)
    else:
        return -1         # Über 30 Tage -> Tracking beenden


def starte_daten_tracking(video_id):
    """Wechselt in den Tracking-Modus mit dynamischen Intervallen und LaTeX-Format."""
    dateiname = f"tracking_{video_id}.txt"
    start_zeitpunkt = time.time()

    print(f"\n🚀 Starte Tracking-Modus. Daten werden in '{dateiname}' gespeichert.")

    # Datei initialisieren und LaTeX-konforme Spaltenüberschriften schreiben
    if not os.path.exists(dateiname):
        with open(dateiname, "w", encoding="utf-8") as f:
            f.write(f"Daten für Video-ID: {video_id}, Startzeit: {start_zeitpunkt}\n")
            f.write("Zeit_in_h, Aufrufe\n")

    while True:
        try:
            # Berechne vergangene Zeit in Stunden seit Tracking-Start
            aktuelle_zeit = time.time()
            vergangene_sekunden = aktuelle_zeit - start_zeitpunkt
            vergangene_stunden = vergangene_sekunden / 3600.0

            # Dynamisches Intervall bestimmen
            wartezeit = bestimme_wartezeit_sekunden(vergangene_stunden)
            if wartezeit == -1:
                print("\n⏰ 30 Tage erreicht. Tracking automatisch beendet.")
                break

            views = hole_aktuelle_aufrufe(video_id)
            if views is not None:
                # Zeile formatieren (Zeit auf 4 Nachkommastellen gerundet für exakte Minutenwerte)
                daten_zeile = f"{vergangene_stunden:.4f}, {views}\n"

                with open(dateiname, "a", encoding="utf-8") as f:
                    f.write(daten_zeile)

                print(f"[{datetime.now().strftime('%H:%M:%S')}] t = {vergangene_stunden:.2f}h | Aufrufe: {views} | Intervall: {wartezeit}s")
            else:
                print("Warnung: Aufrufzahlen konnten nicht geladen werden.")

            time.sleep(wartezeit)

        except KeyboardInterrupt:
            print("\nTracking vom Nutzer abgebrochen.")
            break

# ==========================================
# HAUPTPROGRAMM (MAIN)
# ==========================================
if __name__ == "__main__":
    print("=== YouTube Upload-Radar gestartet (PythonAnywhere-Edition) ===")

    gefunden_id = None
    while not gefunden_id:
        try:
            gefunden_id = scanne_nach_neuem_video()
            if not gefunden_id:
                time.sleep(RADAR_INTERVALL)
        except KeyboardInterrupt:
            print("\nRadar gestoppt.")
            exit()

    starte_daten_tracking(gefunden_id)

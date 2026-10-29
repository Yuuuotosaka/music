from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import pychromecast

SPOTIFY_APP_ID = "CC32E027"

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        data = json.loads(body.decode('utf-8'))

        speaker_name = data.get('speaker', '')
        token = data.get('token')

        print(f"Demande de réveil pour : {speaker_name}")
        success = self.wake_speaker(speaker_name)

        self.send_response(200 if success else 500)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': success}).encode('utf-8'))

    def wake_speaker(self, name):
        browser = None
        cast = None
        try:
            casts, browser = pychromecast.get_chromecasts(timeout=5)

            target = next((c for c in casts if c.name.lower() == name.strip().lower()), None)

            if not target:
                print(f"Appareil '{name}' introuvable sur le réseau local.")
                print(f"Appareils vus : {[c.name for c in casts]}")
                return False

            cast = target
            print(f"Connexion à '{cast.name}'...")
            cast.wait(timeout=6)
            cast.start_app(SPOTIFY_APP_ID)
            print(f"Spotify lancé avec succès sur '{cast.name}' !")
            time.sleep(1)
            return True

        except Exception as e:
            print(f"Erreur de réveil pour '{name}' : {e}")
            return False

        finally:
            if cast:
                try:
                    cast.disconnect()
                except Exception:
                    pass
            if browser:
                try:
                    pychromecast.discovery.stop_discovery(browser)
                except Exception:
                    pass

class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True

if __name__ == '__main__':
    print("Bridge Spotify démarré sur http://127.0.0.1:8080")
    httpd = ReusableHTTPServer(('127.0.0.1', 8080), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur...")
        httpd.server_close()

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import pychromecast

# Son bref (1 seconde de silence MP3) pour forcer le réveil matériel immédiat du Nest
SILENCE_MP3 = "https://raw.githubusercontent.com/anars/blank-audio/master/1-second-of-silence.mp3"
SPOTIFY_APP_ID = "CC32E027"

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Access-Control-Request-Private-Network')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        data = json.loads(body.decode('utf-8'))

        speaker_name = data.get('speaker', '')
        print(f"Demande de réveil pour : {speaker_name}")
        success = self.wake_speaker(speaker_name)

        self.send_response(200 if success else 500)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': success}).encode('utf-8'))

    def wake_speaker(self, name):
        browser = None
        cast = None
        try:
            casts, browser = pychromecast.get_chromecasts(timeout=5)
            target = next((c for c in casts if c.name.lower() == name.strip().lower()), None)

            if not target:
                print(f"Appareil '{name}' introuvable.")
                print(f"Appareils vus : {[c.name for c in casts]}")
                return False

            cast = target
            print(f"Connexion à '{cast.name}'...")
            cast.wait(timeout=6)

            # 1. Réveil matériel immédiat (carillon Cast)
            mc = cast.media_controller
            mc.play_media(SILENCE_MP3, 'audio/mp3')
            mc.block_until_active(timeout=4)

            # 2. Bascule immédiate sur l'application Spotify
            time.sleep(0.5)
            cast.start_app(SPOTIFY_APP_ID)

            print(f"'{cast.name}' réveillée et basculée sur Spotify avec succès !")
            time.sleep(2)
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
    def __init__(self, server_address, RequestHandlerClass):
        self.allow_reuse_address = True
        super().__init__(server_address, RequestHandlerClass, bind_and_activate=True)


if __name__ == '__main__':
    server_address = ('127.0.0.1', 8080)
    print(f"Bridge Spotify démarré sur http://{server_address[0]}:{server_address[1]}")
    httpd = ReusableHTTPServer(server_address, Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur...")
        httpd.server_close()

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import threading
import pychromecast
from pychromecast.controllers import BaseController

SPOTIFY_APP_ID = "CC32E027"
SPOTIFY_NAMESPACE = "urn:x-cast:com.spotify.chromecast.secure.v1"

class SpotifyCastBridge(BaseController):
    def __init__(self, access_token):
        super().__init__(SPOTIFY_NAMESPACE, SPOTIFY_APP_ID)
        self.access_token = access_token
        self.launched_event = threading.Event()

    def receive_message(self, message, data):
        # Dès que l'application Spotify sur l'enceinte répond
        if isinstance(data, dict):
            msg_type = data.get("type")
            if msg_type in ("setCredentials", "initialBridgeStatus", "ready"):
                self.launched_event.set()
        return True

    def launch_and_auth(self, timeout=7):
        def callback(*args, **kwargs):
            # Envoi des identifiants Spotify requis par le récepteur Google Nest
            self.send_message({
                "type": "setCredentials",
                "credentials": self.access_token
            })
            self.launched_event.set()

        self.launch(callback_function=callback)
        return self.launched_event.wait(timeout)


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
        token = data.get('token', '')

        print(f"Demande d'initialisation Spotify pour : {speaker_name}")
        success = self.wake_speaker(speaker_name, token)

        self.send_response(200 if success else 500)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': success}).encode('utf-8'))

    def wake_speaker(self, name, token):
        if not token:
            print("Erreur : Aucun token fourni par la page web.")
            return False

        browser = None
        cast = None
        try:
            casts, browser = pychromecast.get_chromecasts(timeout=5)
            target = next((c for c in casts if c.name.lower() == name.strip().lower()), None)

            if not target:
                print(f"Appareil '{name}' introuvable.")
                return False

            cast = target
            print(f"Connexion à '{cast.name}'...")
            cast.wait(timeout=6)

            # Lancement et transmission du token à l'enceinte
            sp = SpotifyCastBridge(token)
            cast.register_handler(sp)
            sp.launch_and_auth(timeout=6)

            print(f"'{cast.name}' authentifiée et active sur Spotify !")
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

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
import pychromecast
from pychromecast.controllers import BaseController

SPOTIFY_APP_ID = "CC32E753"
SPOTIFY_NAMESPACE = "urn:x-cast:com.spotify.chromecast.secure.v1"


class SpotifyCastBridge(BaseController):
    def __init__(self, access_token):
        super().__init__(SPOTIFY_NAMESPACE, SPOTIFY_APP_ID)
        self.access_token = access_token
        self.got_info = threading.Event()
        self.finished = threading.Event()
        self.success = False
        self.last_type = None

    def receive_message(self, message, data):
        # DIAGNOSTIC : on affiche tout ce que l'enceinte répond
        print("  <- réponse de l'enceinte :", json.dumps(data)[:400])
        if isinstance(data, dict):
            t = data.get("type")
            self.last_type = t
            if t in ("getInfoResponse", "getInfoError"):
                self.got_info.set()
            if t in ("addUserResponse", "setCredentialsResponse"):
                self.success = True
                self.finished.set()
            if t in ("addUserError", "setCredentialsError"):
                self.finished.set()
        return True

    def run(self, name):
        def on_launch(*args, **kwargs):
            print("  -> appli Spotify lancée sur l'enceinte, envoi de getInfo")
            self.send_message({
                "type": "getInfo",
                "payload": {"localName": name, "deviceID": "", "deviceAPI_isGroup": False},
            })

        self.launch(callback_function=on_launch)
        if not self.got_info.wait(8):
            print("  !! pas de réponse à getInfo en 8 s")
        print("  -> envoi de addUser avec le jeton")
        self.send_message({
            "type": "addUser",
            "payload": {"blob": self.access_token, "tokenType": "accesstoken"},
        })
        if not self.finished.wait(8):
            print("  !! pas de réponse à addUser en 8 s")
        return self.success


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Access-Control-Request-Private-Network')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(length).decode('utf-8'))
        name = data.get('speaker', '')
        token = data.get('token', '')

        print(f"\nDemande d'initialisation Spotify pour : {name}")
        success = self.wake_speaker(name, token)
        print("RÉSULTAT :", "CONFIRMÉ par l'enceinte" if success else "NON confirmé par l'enceinte")

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': success}).encode('utf-8'))

    def wake_speaker(self, name, token):
        if not token:
            print("Erreur : aucun jeton fourni par la page web.")
            return False
        browser = None
        try:
            casts, browser = pychromecast.get_chromecasts(timeout=6)
            target = next((c for c in casts if c.name.lower() == name.strip().lower()), None)
            if not target:
                print(f"Appareil '{name}' introuvable sur le Wi-Fi. Vus : {[c.name for c in casts]}")
                return False
            print(f"Connexion à '{target.name}'...")
            target.wait(timeout=6)
            sp = SpotifyCastBridge(token)
            target.register_handler(sp)
            return sp.run(target.name)
        except Exception as e:
            print(f"Erreur de réveil pour '{name}' : {e}")
            return False
        finally:
            if browser:
                try:
                    pychromecast.discovery.stop_discovery(browser)
                except Exception:
                    pass


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    addr = ('127.0.0.1', 8080)
    print(f"Bridge Spotify (diagnostic) démarré sur http://{addr[0]}:{addr[1]}")
    httpd = ReusableHTTPServer(addr, Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur...")
        httpd.server_close()

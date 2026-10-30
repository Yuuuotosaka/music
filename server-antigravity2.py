from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import threading
import pychromecast
from pychromecast.controllers import BaseController

SPOTIFY_APP_ID = "CC32E753"
SPOTIFY_NAMESPACE = "urn:x-cast:com.spotify.chromecast.secure.v1"

class SpotifyCastBridge(BaseController):
        def __init__(self, access_token):
            super().__init__(SPOTIFY_NAMESPACE, SPOTIFY_APP_ID)
            self.access_token = access_token
            self.launched_event = threading.Event()
            self.last_response = None

        def receive_message(self, message, data):
            print(f"\n[CAST REÇU] Données de l'enceinte : {data}")
            self.last_response = data
            if isinstance(data, dict):
                msg_type = data.get("type", "")
                if msg_type in ("setCredentialsResponse", "initialBridgeStatus", "ready"):
                    print("[CAST SUCCÈS] L'enceinte a validé le token Spotify !")
                    self.launched_event.set()
            return True

        def launch_and_auth(self, timeout=12):
            def callback(*args, **kwargs):
                print("[CAST INFO] Application lancée sur l'enceinte. Envoi de setCredentials...")
                self.send_message({
                    "type": "setCredentials",
                    "credentials": self.access_token
                })

            print(f"[CAST INFO] Démarrage de Spotify ({SPOTIFY_APP_ID})...")
            self.launch(callback_function=callback)
            success = self.launched_event.wait(timeout)
            print(f"[CAST INFO] Résultat de l'attente : {'Validé' if success else 'Expiré (Timeout)'}")
            return success


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

            print(f"\n--- Nouvelle demande pour : {speaker_name} ---")
            if token:
                print(f"[AUTH] Token reçu de la page web (longueur: {len(token)}, début: {token[:12]}...)")
            else:
                print("[AUTH ERREUR] Aucun token reçu !")

            success = self.wake_speaker(speaker_name, token)

            self.send_response(200 if success else 500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': success}).encode('utf-8'))

        def wake_speaker(self, name, token):
            if not token:
                return False

            browser = None
            cast = None
            try:
                print("[WIFI] Recherche de l'enceinte sur le réseau local...")
                casts, browser = pychromecast.get_chromecasts(timeout=5)
                target = next((c for c in casts if c.name.lower() == name.strip().lower()), None)

                if not target:
                    print(f"[WIFI ERREUR] Enceinte '{name}' introuvable sur le Wi-Fi.")
                    return False

                cast = target
                print(f"[WIFI] Connecté à '{cast.name}'. Initialisation Cast...")
                cast.wait(timeout=6)

                sp = SpotifyCastBridge(token)
                cast.register_handler(sp)
                auth_ok = sp.launch_and_auth(timeout=10)

                if not auth_ok:
                    print(f"[ERREUR] '{cast.name}' n'a pas confirmé l'authentification dans les 10s.")
                    return False

                print(f"[SUCCÈS TOTAL] '{cast.name}' est maintenant en ligne sur Spotify !")
                return True

            except Exception as e:
                print(f"[EXCEPTION] Erreur : {e}")
                return False

            finally:
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

from http.server import HTTPServer, BaseHTTPRequestHandler
    import json
    import pychromecast
    from pychromecast.controllers.spotify import SpotifyController

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

            speaker_name = data.get('speaker')
            token = data.get('token')

            print(f"Demande de réveil pour : {speaker_name}")
            success = self.wake_speaker(speaker_name, token)

            self.send_response(200 if success else 500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': success}).encode('utf-8'))

        def wake_speaker(self, name, token):
            try:
                casts, browser = pychromecast.get_listed_chromecasts(friendly_names=[name])
                if not casts:
                    all_casts, b2 = pychromecast.get_chromecasts()
                    casts = [c for c in all_casts if c.name.lower() == name.lower()]
                    pychromecast.discovery.stop_discovery(b2)

                pychromecast.discovery.stop_discovery(browser)

                if not casts:
                    print(f"Enceinte '{name}' introuvable sur le Wi-Fi.")
                    return False

                cast = casts[0]
                cast.wait()
                sp = SpotifyController(token)
                cast.register_handler(sp)
                sp.launch_app()
                cast.disconnect()
                print(f"Enceinte '{name}' réveillée avec succès !")
                return True
            except Exception as e:
                print(f"Erreur de réveil : {e}")
                return False

    if __name__ == '__main__':
        print("Bridge Spotify démarré sur http://127.0.0.1:8080")
        httpd = HTTPServer(('127.0.0.1', 8080), Handler)
        httpd.serve_forever()
    EOF

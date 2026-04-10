
class OAuthBase:

    def __init__(self, client_id, client_secret, redirect_uri):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_auth_url(self):
        raise NotImplementedError

    def get_token(self, code):
        raise NotImplementedError
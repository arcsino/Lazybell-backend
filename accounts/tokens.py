from rest_framework_simplejwt.tokens import RefreshToken


class CustomRefreshToken(RefreshToken):
    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token['token_version'] = user.token_version
        token['username'] = user.username
        return token

    @property
    def access_token(self):
        access = super().access_token
        access['token_version'] = self.payload.get('token_version', 0)
        access['username'] = self.payload.get('username', '')
        return access

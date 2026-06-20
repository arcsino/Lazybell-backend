from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'


class UserSearchRateThrottle(UserRateThrottle):
    scope = 'user_search'


class InviteRateThrottle(UserRateThrottle):
    scope = 'invite'

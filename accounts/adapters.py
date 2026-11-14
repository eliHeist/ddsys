from allauth.account.adapter import DefaultAccountAdapter


class NoSignupAdapter(DefaultAccountAdapter):
    """Only the few Dakdot staff use the system, and an admin adds them. Nobody signs up on their own."""

    def is_open_for_signup(self, request):
        return False

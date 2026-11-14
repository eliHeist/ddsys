from allauth.account.models import EmailAddress
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View


class ProfileView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        email_addresses = EmailAddress.objects.filter(
            user=user,
            email=user.email,
        )
        context = {
            "user": user,
            "email_addresses": email_addresses,
        }
        return render(request, "accounts/profile.html", context)
        
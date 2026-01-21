from django.shortcuts import redirect
from django.contrib.auth import logout
from django.urls import reverse

class AdminForceStaffLogoutMiddleware:
    """
    Logs out non-staff users who try to access the admin panel.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            user = request.user
            if user.is_authenticated and not user.is_staff:
                logout(request)
                return redirect(reverse('admin:login'))
        return self.get_response(request)

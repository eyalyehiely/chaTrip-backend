# authentication/urls.py

from django.urls import path
from .views import *

urlpatterns = [
    path('send-otp-email/', send_otp_email_view, name='send_otp_email'),
    path('verify-otp-email/', verify_otp_email_view, name='verify_otp_email'),
]
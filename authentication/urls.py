# authentication/urls.py

from django.urls import path
from .views import *
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('send-otp-email/', send_otp_email_view, name='send_otp_email'),
    path('verify-otp-email/', verify_otp_email_view, name='verify_otp_email'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('nearby-places/', get_nearby_places, name='get_nearby_places'),
    path('user/<uuid:user_id>/', user_details, name='user_details'),
    path('user/<uuid:user_id>/place/<uuid:place_id>/', delete_saving_place, name='delete_saving_place'),
    path('chat/', chat_with_ai, name='chat_with_ai'),
    path('conversations/', provide_conversations, name='provide_conversations'),
    path('conversations/<uuid:conversation_id>/',get_conversation_by_id),
    path('end-conversation/', end_conversation, name='end_conversation'),
    path('contact-us/',contact_us_mail,name='end_conversation')




]
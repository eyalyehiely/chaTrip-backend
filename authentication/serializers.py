# authentication/serializers.py

from rest_framework import serializers
from .models import Otp,CustomUser,Conversation

class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()

class OTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)
    class Meta:
        model = Otp
        fields = "__all__"


class CustomUserSerializer(serializers.ModelSerializer):
    saving_places = serializers.ListField()  # Or the appropriate field type

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'saving_places']  # Ensure saving_places is included




class ConversationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Conversation
        fields = ['id','user', 'title', 'messages', 'timestamp']  # Ensure saving_places is included


    
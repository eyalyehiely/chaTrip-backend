# authentication/serializers.py

from rest_framework import serializers

class PhoneNumberSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)

class OTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    code = serializers.CharField(max_length=6)
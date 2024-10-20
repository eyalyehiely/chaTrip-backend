# authentication/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .serializers import EmailSerializer, OTPSerializer
from .utils import generate_and_send_otp, verify_otp, can_request_otp
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
import logging,time,requests,math
from django_ratelimit.decorators import ratelimit
from chaTrip.settings import GOOGLE_PLACES_API_KEY


logger = logging.getLogger('auth') 
place_logger = logging.getLogger('place')
User = get_user_model()


@api_view(['POST'])
@ratelimit(key='ip', rate='5/m', method='POST', block=True)
@permission_classes([AllowAny]) 
def send_otp_email_view(request):
    start_time = time.time()
    logger.info("Received request to send OTP email.")
    serializer = EmailSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        logger.debug(f"Validated email: {email}")
        try:
            user = User.objects.filter(username=email).first()
            if user:
                logger.info(f"Found existing user for email: {email}")
            else:
                logger.info(f"No existing user found for email: {email}. Creating a new user.")
                user = User.objects.create(username=email)
                user.set_unusable_password()
                user.save()
                logger.debug(f"Created new user with email: {email}")
                


        except Exception as e:
            logger.error(f"Error querying or creating user for email {email}: {str(e)}")
            return Response({"detail": "Internal server error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not can_request_otp(user):
            logger.warning(f"OTP request limit exceeded for user: {email}")
            return Response(
                {"detail": "OTP request limit exceeded. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        try:
            generate_and_send_otp(user)
            logger.info(f"OTP generated and sent to email: {email}")
            end_time = time.time()  # Capture end time
            print(f"Function execution time: {end_time - start_time} seconds")
            return Response({"detail": "OTP sent successfully to your email."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to send OTP to email {email}: {str(e)}")
            return Response({"detail": "Failed to send OTP. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.warning(f"Invalid serializer data: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to verify OTPs
def verify_otp_email_view(request):
    start_time = time.time()
    logger.info("Received request to verify OTP.")
    serializer = OTPSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        logger.debug(f"Validated data - Email: {email}, OTP Code: {otp}")

        try:
            user = User.objects.filter(username=email).first()
            logger.info(f"Found user for OTP verification: {email}")
        except User.DoesNotExist:
            logger.warning(f"User with email {email} does not exist.")
            return Response({"detail": "User with this email does not exist."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            success, message = verify_otp(user,otp)
            print('success',success)
            if success:
                logger.info(f"OTP verified successfully for user: {email}")
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                refresh['username'] = user.username
                access_token = str(refresh.access_token)
                logger.debug(f"Generated JWT tokens for user: {email}")
                end_time = time.time()
                print(f"Function execution time: {end_time - start_time} seconds")
                return Response({
                    "detail": message,
                   'refresh': str(refresh),
                    'access': access_token
                }, status=status.HTTP_200_OK)
                

            else:
                logger.warning(f"OTP verification failed for user: {email}. Reason: {message}")
                return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error during OTP verification for user {email}: {str(e)}")
            return Response({"detail": "Internal server error during OTP verification."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    logger.warning(f"Invalid serializer data: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Haversine formula for calculating distance
def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points 
    on the Earth (specified in decimal degrees using the Haversine formula).
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    r = 6371  # Radius of earth in kilometers
    return r * c  # Distance in kilometers

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_nearby_places(request):
    # Get the latitude, longitude, and radius from the request
    user_lat = request.GET.get('latitude')
    user_lng = request.GET.get('longitude')
    radius = request.GET.get('radius', 3000)  # Default radius is 3km

    # Log the received parameters
    place_logger.info(f"Received parameters: Latitude: {user_lat}, Longitude: {user_lng}, Radius: {radius}")

    # Validate latitude and longitude
    if not user_lat or not user_lng:
        place_logger.error("Missing latitude or longitude in request")
        return Response({'error': 'Missing latitude or longitude'}, status=400)

    # Google Places API URL
    google_places_url = (
        "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    )

    # Parameters to pass to the Google Places API
    params = {
        'location': f'{user_lat},{user_lng}',
        'radius': radius,
        # 'key': GOOGLE_PLACES_API_KEY
    }

    # Log the outgoing API request
    place_logger.info(f"Making request to Google Places API with params: {params}")

    # Make the request to the Google Places API
    try:
        response = requests.get(google_places_url, params=params)
        response.raise_for_status()  # Raise an exception if the response code is not 200
    except requests.RequestException as e:
        place_logger.error(f"Error fetching data from Google Places API: {e}")
        return Response({'error': 'Failed to fetch data from Google Places API'}, status=500)

    places_data = response.json()

    # Log the response from Google Places API
    place_logger.info(f"Google Places API response status: {response.status_code}, Data: {places_data}")

    # Extract relevant data from the response
    results = []
    if 'results' in places_data:
        for place in places_data['results']:
            place_location = place.get('geometry', {}).get('location', {})
            place_lat = place_location.get('lat')
            place_lng = place_location.get('lng')
            
            if place_lat and place_lng:
                # Calculate the distance between the user's location and the place
                distance = haversine(float(user_lat), float(user_lng), place_lat, place_lng)
            else:
                distance = None

            if distance <= 3:
                place_info = {
                'name': place.get('name'),
                'kind_of_place': place.get('types', []),
                'location': place_location,
                'distance': f"{distance:.2f} km" if distance is not None else 'Unknown',  # Format distance
                'rating': place.get('rating', 'No rating available')
                }
                results.append(place_info)
            else:
                continue

    # Log the number of places found
    place_logger.info(f"Found {len(results)} places near location: {user_lat}, {user_lng}")

    # Return the data as JSON
    return Response({'places': results}, status=200)
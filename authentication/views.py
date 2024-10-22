# authentication/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .serializers import EmailSerializer, OTPSerializer,CustomUserSerializer,ConversationSerializer
from .utils import generate_and_send_otp, verify_otp, can_request_otp
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
import logging,time,requests,math,openai
from django_ratelimit.decorators import ratelimit
from chaTrip.settings import GOOGLE_PLACES_API_KEY,OPEN_AI_API_KEY
from .models import CustomUser,Conversation
from django.utils import timezone
from django.core.cache import cache


logger = logging.getLogger('auth') 
place_logger = logging.getLogger('place')
user_logger = logging.getLogger('user')

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
                refresh['user_id'] = str(user.id)
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
    start_time = time.time()
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
        'key': GOOGLE_PLACES_API_KEY
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
                'type': place.get('types', []),
                'location': place_location,
                'distance': f"{distance:.2f} km" if distance is not None else 'Unknown',  
                'rating': place.get('rating', 'No rating available'),
                'opening_hours': place.get('opening_hours', {}).get('open_now', 'No hours available')                }
                results.append(place_info)
            else:
                continue

    # Log the number of places found
    place_logger.info(f"Found {len(results)} places near location: {user_lat}, {user_lng}")

    # Return the data as JSON
    end_time = time.time()
    print(f"Function execution time: {end_time - start_time} seconds")
    return Response({'places': results}, status=200)



@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def user_details(request, user_id):
    # Log the request method and user_id
    user_logger.info(f"Received {request.method} request for user: {user_id}")

    try:
        # Try to find the user by id
        user = CustomUser.objects.filter(id=user_id).first()
        if not user:
            user_logger.warning(f"User {user_id} not found")
            return Response({'error': 'User not found'}, status=404)
    except Exception as e:
        user_logger.error(f"Exception while retrieving user: {e}")
        return Response({'error': 'Server error'}, status=500)

    if request.method == 'GET':
        # Log attempting to retrieve user details
        user_logger.info(f"Attempting to retrieve details for user {user_id}")
        
        serializer = CustomUserSerializer(user)  # Serialize user data
        return Response(serializer.data, status=200)

    elif request.method == 'PUT':
        # Log attempting to update user details
        user_logger.info(f"Attempting to update details for user {user_id}")
        
        # Log request data for debugging
        user_logger.info(f"Request data for updating user {user_id}: {request.data}")

        # Get the existing saving_places
        existing_places = user.saving_places if user.saving_places else []

        # Check if 'place' is provided in the request data
        place_data = request.data.get('place')
        if place_data:
            # Append the new place to the existing saving_places
            existing_places.append(place_data)
            # Update the request data with the modified saving_places
            request_data = {'saving_places': existing_places}

            # Log the updated saving_places
            user_logger.info(f"Updated saving_places for user {user_id}: {existing_places}")

            serializer = CustomUserSerializer(user, data=request_data, partial=True)  # Allow partial updates
        else:
            user_logger.warning(f"No 'place' data provided for user {user_id}")
            return Response({'error': 'No place data provided'}, status=400)

        if serializer.is_valid():
            try:
                # Attempt to save the data
                serializer.save()
                user_logger.info(f"User {user_id} details updated successfully")
                return Response({'message': f'User details updated successfully', 'data': serializer.data}, status=200)
            except Exception as e:
                # Log any exceptions during the save operation
                user_logger.error(f"Error saving user {user_id} details: {e}")
                return Response({'error': 'Error saving data to database'}, status=500)
        else:
            # Log validation errors
            user_logger.warning(f"Validation errors while updating user {user_id}: {serializer.errors}")
            return Response(serializer.errors, status=400)
    
    elif request.method == 'DELETE':
        try:
            # Attempt to delete the user
            user.delete()
            user_logger.info(f"User {user_id} deleted successfully")
            return Response({'message': 'User deleted successfully!'}, status=200)
        except Exception as e:
            user_logger.error(f"Error deleting user {user_id}: {e}")
            return Response({'error': 'Error deleting user from the database'}, status=500)
        


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def delete_saving_place(request, user_id, place_id):
    user_logger.info(f"Received DELETE request for place: {place_id} from user: {user_id}")
    
    try:
        # Fetch the user by id
        user = CustomUser.objects.filter(id=user_id).first()
        if not user:
            user_logger.warning(f"User {user_id} not found")
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure saving_places is a valid list
        if not user.saving_places:
            return Response({'error': 'No places saved for this user'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Log current saving_places
        user_logger.info(f"Current saving_places for user {user_id}: {user.saving_places}")
        
        # Filter out the place to delete by id
        updated_saving_places = [place for place in user.saving_places if place.get('id') != str(place_id)]
        
        # Check if the place was actually in the list
        if len(updated_saving_places) == len(user.saving_places):
            user_logger.warning(f"Place {place_id} not found in user's saving_places")
            return Response({'error': 'Place not found in saved places'}, status=status.HTTP_404_NOT_FOUND)

        # Update user's saving_places
        user.saving_places = updated_saving_places
        user.save()

        # Log the updated saving_places
        user_logger.info(f"Updated saving_places for user {user_id}: {user.saving_places}")
        
        return Response({'message': 'Place deleted successfully', 'saving_places': user.saving_places}, status=status.HTTP_200_OK)
    
    except Exception as e:
        user_logger.error(f"Error while deleting place {place_id} for user {user_id}: {e}")
        return Response({'error': 'An error occurred while deleting the place'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_with_ai(request):
    user = request.user
    user_message = request.data.get('message')
    
    logger.info(f"User {user.username} added a message: {user_message}")

    # Fetch the existing conversation from cache (or start a new one)
    conversation_key = f"conversation_{user.id}"
    conversation_data = cache.get(conversation_key, {'messages': [], 'title': ''})
    
    try:
        # Call OpenAI API for conversation
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=150,
            temperature=0.7,
        )
        
        ai_message = response['choices'][0]['message']['content'].strip()
        logger.info(f"OpenAI response: {ai_message}")

        # Add the user's and AI's message to the conversation data
        conversation_data['messages'].append({
            'role': 'user',
            'message': user_message,
            'timestamp': timezone.now().isoformat(),
        })
        conversation_data['messages'].append({
            'role': 'assistant',
            'message': ai_message,
            'timestamp': timezone.now().isoformat(),
        })

        # Generate a title from the user's first message if it hasn't been set
        if not conversation_data['title']:
            conversation_data['title'] = ' '.join(user_message.split()[:5]) + '...'

        # Store the updated conversation back in cache
        cache.set(conversation_key, conversation_data, timeout=600)  # Store for 10 minutes

        logger.info(f"Conversation stored temporarily for user {user.username}")

        return Response({'user_message': user_message, 'ai_message': ai_message}, status=200)

    except Exception as e:
        logger.error(f"Error occurred for user {user.username}: {str(e)}", exc_info=True)
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_conversation(request):
    user = request.user
    conversation_key = f"conversation_{user.id}"
    conversation_data = cache.get(conversation_key)

    if conversation_data:
        # Save the conversation to the database
        conversation = Conversation.objects.create(
            user=user,
            title=conversation_data['title'],
            messages=conversation_data['messages']
        )
        conversation.save()

        # Clear the cache
        cache.delete(conversation_key)

        logger.info(f"Conversation saved to the database for user {user.username}")

        return Response({'message': 'Conversation saved successfully.'}, status=200)
    else:
        return Response({'error': 'No active conversation found.'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def provide_conversations(request):
    try:
        user = request.user  # Get the current user
        conversations = Conversation.objects.filter(user=user).order_by('-timestamp')
        user_logger.info(f"providing all {user.username} conversations")

        # Serialize the conversations
        serialized_conversations = ConversationSerializer(conversations, many=True)

        return Response({'message': "providing all user's conversations", 'conversations': serialized_conversations.data}, status=200)
    
    except Exception as e:
        user_logger.error(f"Error occurred while providing conversations for user {user.username}: {str(e)}")
        return Response({'error': str(e)}, status=500)
    



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversation_by_id(request, conversation_id):
    try:
        user = request.user
        user_logger.info(f"User {user.username} is trying to fetch conversation with ID {conversation_id}")
        
        # Fetch the conversation
        conversation = Conversation.objects.filter(id=conversation_id, user=user).first()
        
        if not conversation:
            user_logger.warning(f"Conversation with ID {conversation_id} not found for user {user.username}")
            return Response({'error': 'Conversation not found'}, status=404)

        # Log successful fetching of the conversation
        user_logger.info(f"Conversation {conversation_id} retrieved successfully for user {user.username}")
        
        return Response({
            'id': conversation.id,
            'title': conversation.title,
            'messages': conversation.messages
        }, status=200)
    
    except Exception as e:
        # Log the error with full details
        user_logger.error(f"Error occurred while fetching conversation {conversation_id} for user {user.username}: {str(e)}", exc_info=True)
        return Response({'error': 'An error occurred while fetching the conversation'}, status=500)
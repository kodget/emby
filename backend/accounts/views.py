from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from google.oauth2 import id_token
from google.auth.transport import requests
import secrets
import hashlib
from datetime import timedelta

from accounts.permissions import can_manage_class
from .models import (
    Profile, School, ClassGroup, OnboardingQuestion,
    OnboardingResponse, Announcement, PaymentTransaction,
    SubscriptionTier, ClassRole, ExamCountdown
)
from .serializers import (
    SignupSerializer, LoginSerializer, GoogleAuthSerializer,
    CustomTokenRefreshSerializer,
    ProfileSerializer, UpdateProfileSerializer, OnboardingQuestionSerializer,
    OnboardingResponseSerializer, OnboardingSubmitSerializer,
    JoinClassSerializer, ClassGroupSerializer, AnnouncementSerializer,
    PaymentTransactionSerializer, SchoolSerializer, ExamCountdownSerializer,
    ClassMemberSerializer
)


class CustomTokenRefreshView(TokenRefreshView):
    """
    A safer TokenRefreshView that uses a custom serializer to catch 
    User.DoesNotExist errors (which happen if a user's account is deleted
    from the database while they still have a valid refresh token in the browser).
    Returns a 401 instead of crashing the server with a 500.
    """
    serializer_class = CustomTokenRefreshSerializer

def get_tokens_for_user(user):
    """Generate JWT tokens"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# -------------------------
# AUTHENTICATION ENDPOINTS
# -------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    from django.db import transaction
    from .email_service import request_email_verification
    serializer = SignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        user = serializer.save()
        profile, _ = Profile.objects.get_or_create(user=user)
    delivery = request_email_verification(user)
    profile.refresh_from_db()
    return Response({
        'message': 'Account created successfully. ' + delivery.message,
        'email_status': delivery.status,
        'user': ProfileSerializer(profile).data,
        'tokens': get_tokens_for_user(user),
    }, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Email/password login"""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        # Authenticate
        user = authenticate(username=email, password=password)
        
        if user is None:
            return Response({
                'error': 'Invalid credentials. Please check your email and password.',
                'suggestion': 'If you haven\'t created an account yet, please sign up first.'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if profile exists
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            return Response({
                'error': 'Profile not found. Please contact support.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Generate tokens
        tokens = get_tokens_for_user(user)
        
        return Response({
            'message': 'Login successful',
            'user': ProfileSerializer(profile).data,
            'tokens': tokens
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def google_login(request):
    """Google OAuth login/signup"""
    serializer = GoogleAuthSerializer(data=request.data)
    if serializer.is_valid():
        token = serializer.validated_data['token']
        
        try:
            # Verify Google token
            
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )
            
            
            if idinfo.get('email_verified') is not True:
                return Response({'error': 'Use a verified Google email address.'}, status=401)
            email = idinfo['email'].strip().lower()
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            photo_url = idinfo.get('picture', '')
            
            
            # Get or create user — filter by email to avoid MultipleObjectsReturned
            matches = list(User.objects.filter(email__iexact=email).order_by('pk')[:2])
            if len(matches) > 1:
                return Response({'error': 'Multiple accounts use this email. Contact support to recover the correct account.'}, status=409)
            user = matches[0] if matches else None
            if user and not user.is_active:
                return Response({'error': 'This account is inactive.'}, status=403)
            created = False
            if not user:
                username = email
                # Ensure username is unique
                if User.objects.filter(username=username).exists():
                    username = f"{email}_{secrets.token_urlsafe(4)}"
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name
                )
                created = True
            
            
            # Get or create profile
            profile, profile_created = Profile.objects.get_or_create(
                user=user,
                defaults={
                    'class_role': ClassRole.STUDENT,
                    'photo_url': photo_url,
                    'email_verified': True  # Google emails are pre-verified
                }
            )
            
            # Google OAuth accounts have verified emails by definition
            profile.email_verified = True
            if photo_url:
                profile.photo_url = photo_url
            profile.save()
            
            
            # Generate tokens
            tokens = get_tokens_for_user(user)
            
            
            return Response({
                'message': 'Login successful' if not created else 'Account created successfully',
                'user': ProfileSerializer(profile).data,
                'tokens': tokens,
                'is_new_user': created or not profile.onboarding_completed
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            print(f"Token verification failed: {str(e)}")
            return Response({
                'error': f'Invalid Google token: {str(e)}'
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'error': f'Authentication failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    print(f"Serializer errors: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    from .email_service import consume_verification_token
    if consume_verification_token(request.data.get('token')):
        return Response({'message': 'Email verified successfully'})
    return Response({'error': 'Invalid, expired or already-used verification link. Request a new email.'}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resend_verification(request):
    from .email_service import request_email_verification
    delivery = request_email_verification(request.user)
    response_code = 429 if delivery.status == 'throttled' else (
        503 if delivery.status in ('failed', 'unavailable') else 200
    )
    body = {'message': delivery.message, 'email_status': delivery.status, 'retry_after': delivery.retry_after}
    if response_code >= 400:
        body['error'] = delivery.message
    response = Response(body, status=response_code)
    if delivery.retry_after:
        response['Retry-After'] = str(delivery.retry_after)
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    from rest_framework import serializers
    from .passwords import request_password_reset, RESET_MESSAGE
    email = serializers.EmailField().run_validation(request.data.get('email'))
    request_password_reset(email)
    return Response({'message': RESET_MESSAGE})

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    from .passwords import reset_password_with_token
    reset_password_with_token(request.data.get('token'), request.data.get('new_password'))
    return Response({'message': 'Password reset successfully. You can now sign in with your new password.'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change password for logged in user"""
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not old_password or not new_password:
        return Response({'error': 'Old and new password required'}, status=status.HTTP_400_BAD_REQUEST)
    
    user = request.user
    
    # Check old password
    if not user.check_password(old_password):
        return Response({
            'error': 'Current password is incorrect'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate new password
    try:
        validate_password(new_password, user=user)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Set new password
    user.set_password(new_password)
    user.save()
    
    return Response({
        'message': 'Password changed successfully'
    }, status=status.HTTP_200_OK)


# -------------------------
# ONBOARDING ENDPOINTS
# -------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_onboarding_questions(request):
    """Get all onboarding questions"""
    questions = OnboardingQuestion.objects.filter(is_active=True)
    serializer = OnboardingQuestionSerializer(questions, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_onboarding(request):
    from .onboarding import complete_onboarding
    serializer = OnboardingSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    profile, created = complete_onboarding(request.user.pk, serializer.validated_data)
    response = {
        'message': 'Onboarding completed successfully' if created else 'Onboarding already completed',
        'user': ProfileSerializer(profile).data,
        'class_code': profile.class_group.code if profile.class_group else None,
    }
    if profile.class_role == ClassRole.CLASS_HEAD and not profile.class_head_verified:
        response['verification_message'] = 'Your class-head request is pending administrator review.'
    return Response(response)


@api_view(['POST'])
@permission_classes([AllowAny])
def validate_class_code(request):
    """Check if a class code is valid without joining"""
    code = request.data.get('class_code', '').strip().upper()
    if not code:
        return Response({'error': 'Class code required'}, status=status.HTTP_400_BAD_REQUEST)
    if ClassGroup.objects.filter(code=code, is_active=True).exists():
        return Response({'valid': True})
    return Response({'error': 'Invalid class code'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_class(request):
    from .onboarding import join_student_class
    serializer = JoinClassSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        group = join_student_class(request.user.pk, serializer.validated_data['class_code'])
    except ClassGroup.DoesNotExist:
        return Response({'error': 'Invalid or inactive class code.'}, status=400)
    return Response({'message': 'Successfully joined class', 'class': ClassGroupSerializer(group).data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_class(request):
    """Get current user's class info"""
    profile = request.user.profile
    
    if not profile.class_group:
        return Response({
            'message': 'Not in any class'
        }, status=status.HTTP_404_NOT_FOUND)
    
    return Response(ClassGroupSerializer(profile.class_group).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_class_members(request):
    """Get members of the current user's class group"""
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.class_group:
        return Response({
            'error': 'You are not enrolled in any class'
        }, status=status.HTTP_404_NOT_FOUND)

    profiles = (
        Profile.objects.filter(class_group=profile.class_group)
        .select_related('user', 'class_group')
        .prefetch_related('user__stats')
    )
    from learning.progress_evidence import roster_streaks
    streaks = roster_streaks(profiles)
    serializer = ClassMemberSerializer(profiles, many=True, context={'_roster_streaks': streaks})
    members = list(serializer.data)
    members.sort(key=lambda m: (-(m['total_points'] or 0), m['user']['id']))
    for idx, m in enumerate(members, start=1):
        m['rank'] = idx

    return Response(members, status=status.HTTP_200_OK)


# -------------------------
# CLASS HEAD VERIFICATION
# -------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_class_head_verification(request):
    from .class_heads import request_review
    profile, created = request_review(request.user.pk)
    message = 'Already approved' if profile.class_head_verified else 'Your request is pending administrator review.'
    return Response({'message': message, 'user': ProfileSerializer(profile).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_class_head(request):
    from .class_heads import review_class_head
    from .permissions import has_platform_admin_access
    if not has_platform_admin_access(request.user):
        return Response({'error': 'Admin permission required'}, status=403)
    user_id = request.data.get('user_id')
    if type(user_id) is not int or user_id < 1:
        return Response({'error': 'Provide the applicant user_id as a positive integer.'}, status=400)
    profile, changed = review_class_head(
        actor=request.user, user_id=user_id, approved=request.data.get('approved'),
        rejection_reason=request.data.get('rejection_reason', ''),
    )
    state = 'approved' if profile.class_head_verified else 'rejected'
    return Response({'message': f'Class-head request {state}', 'user': ProfileSerializer(profile).data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_class_head_verifications(request):
    """Admin endpoint to get pending class head verifications"""
    from .permissions import has_platform_admin_access
    if not has_platform_admin_access(request.user):
        return Response({
            'error': 'Admin permission required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    pending_profiles = Profile.objects.filter(
        class_role=ClassRole.CLASS_HEAD,
        class_head_verification_requested=True,
        class_head_verified=False
    )
    
    return Response(ProfileSerializer(pending_profiles, many=True).data)

@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """Get current user profile"""
    if request.method == 'DELETE':
        request.user.delete()
        return Response({'message': 'Account deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
    profile = request.user.profile
    return Response(ProfileSerializer(profile).data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update user profile including name and photo"""
    user = request.user
    profile = user.profile
    
    serializer = UpdateProfileSerializer(data=request.data, partial=True)
    
    if serializer.is_valid():
        # Update user's name if provided
        if 'first_name' in serializer.validated_data:
            user.first_name = serializer.validated_data['first_name']
        
        if 'last_name' in serializer.validated_data:
            user.last_name = serializer.validated_data['last_name']
        
        # Save user if name was updated
        if 'first_name' in serializer.validated_data or 'last_name' in serializer.validated_data:
            user.save()
        
        # Update profile photo if provided
        if 'photo_url' in serializer.validated_data:
            profile.photo_url = serializer.validated_data['photo_url']
            profile.save()
        
        # Return updated profile
        return Response({
            'message': 'Profile updated successfully',
            'user': ProfileSerializer(profile).data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_onboarding_responses(request):
    """Update onboarding responses"""
    user = request.user
    responses = request.data.get('responses', [])
    
    for response_data in responses:
        question_id = response_data.get('question_id')
        answer = response_data.get('answer')
        
        if question_id and answer:
            OnboardingResponse.objects.update_or_create(
                user=user,
                question_id=question_id,
                defaults={'answer': answer}
            )
    
    return Response({'message': 'Responses updated successfully'})


# -------------------------
# ANNOUNCEMENT ENDPOINTS
# -------------------------

class ClassNoticeViewSet(viewsets.ModelViewSet):
    """Read notices within one active class; only its managers may mutate them."""
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        from accounts.permissions import IsClassHead
        permissions = super().get_permissions()
        if self.request.method not in ('GET', 'HEAD', 'OPTIONS'):
            permissions.append(IsClassHead())
        return permissions

    def get_queryset(self):
        from curriculum.class_access import member_class
        group = member_class(self.request.user)
        model = self.serializer_class.Meta.model
        return model.objects.filter(class_group=group) if group else model.objects.none()

    def perform_create(self, serializer):
        from curriculum.class_access import upload_class
        serializer.save(created_by=self.request.user, class_group=upload_class(self.request.user))


class AnnouncementViewSet(ClassNoticeViewSet):
    serializer_class = AnnouncementSerializer

    def _notify(self, announcement):
        import logging
        from django.db import transaction
        from learning.notifications import announce_to_class
        def send():
            try:
                announce_to_class(announcement)
            except Exception:
                logging.getLogger(__name__).exception('Announcement notification dispatch failed')
        transaction.on_commit(send)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._notify(serializer.instance)

    def perform_update(self, serializer):
        self._notify(serializer.save())


# -------------------------
# EXAM COUNTDOWN ENDPOINTS
# -------------------------

class ExamCountdownViewSet(ClassNoticeViewSet):
    serializer_class = ExamCountdownSerializer


# -------------------------
# PAYMENT ENDPOINTS (Delegated to payments app)
# -------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    """Legacy route: delegates to payments.views.checkout with server-authoritative pricing"""
    from payments.views import checkout
    return checkout(request)


@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def verify_payment(request):
    """Legacy route: delegates to payments.views.verify with strict amount validation"""
    from payments.views import verify
    return verify(request)

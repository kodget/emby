from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
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

from .models import (
    Profile, School, ClassGroup, OnboardingQuestion,
    OnboardingResponse, Announcement, PaymentTransaction,
    SubscriptionTier, UserRole, ExamCountdown
)
from .serializers import (
    SignupSerializer, LoginSerializer, GoogleAuthSerializer,
    ProfileSerializer, UpdateProfileSerializer, OnboardingQuestionSerializer,
    OnboardingResponseSerializer, OnboardingSubmitSerializer,
    JoinClassSerializer, ClassGroupSerializer, AnnouncementSerializer,
    PaymentTransactionSerializer, SchoolSerializer, ExamCountdownSerializer
)


def get_tokens_for_user(user):
    """Generate JWT tokens"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


def send_verification_email(user, token):
    """Send email verification link"""
    verification_link = f"http://localhost:3000/verify-email?token={token}"
    send_mail(
        'Verify your email - Emby',
        f'Click this link to verify your email: {verification_link}',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


# -------------------------
# AUTHENTICATION ENDPOINTS
# -------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """Email/password signup"""
    serializer = SignupSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Create profile
        profile = Profile.objects.create(
            user=user,
            role=UserRole.STUDENT,  # Default role, will be updated in onboarding
            email_verification_token=secrets.token_urlsafe(32)
        )
        
        # Send verification email
        try:
            send_verification_email(user, profile.email_verification_token)
        except Exception as e:
            print(f"Email sending failed: {e}")
        
        # Generate tokens
        tokens = get_tokens_for_user(user)
        
        return Response({
            'message': 'Account created successfully. Please check your email to verify.',
            'user': ProfileSerializer(profile).data,
            'tokens': tokens
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
            print(f"Verifying Google token...")
            print(f"Client ID: {settings.GOOGLE_CLIENT_ID}")
            print(f"Token length: {len(token)}")
            
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )
            
            print(f"Token verified successfully: {idinfo}")
            
            email = idinfo['email']
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '')
            photo_url = idinfo.get('picture', '')
            
            print(f"User info - Email: {email}, Name: {first_name} {last_name}")
            
            # Get or create user — filter by email to avoid MultipleObjectsReturned
            user = User.objects.filter(email=email).first()
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
            
            print(f"User {'created' if created else 'found'}: {user.email}")
            
            # Get or create profile
            profile, profile_created = Profile.objects.get_or_create(
                user=user,
                defaults={
                    'role': UserRole.STUDENT,
                    'photo_url': photo_url,
                    'email_verified': True  # Google emails are pre-verified
                }
            )
            
            if not profile_created and photo_url:
                profile.photo_url = photo_url
                profile.email_verified = True
                profile.save()
            
            print(f"Profile ready: {profile.id}")
            
            # Generate tokens
            tokens = get_tokens_for_user(user)
            
            print(f"Tokens generated successfully")
            
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
    """Verify email with token"""
    token = request.data.get('token')
    
    if not token:
        return Response({'error': 'Token required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        profile = Profile.objects.get(email_verification_token=token)
        profile.email_verified = True
        profile.email_verification_token = ''
        profile.save()
        
        return Response({
            'message': 'Email verified successfully'
        }, status=status.HTTP_200_OK)
    
    except Profile.DoesNotExist:
        return Response({
            'error': 'Invalid or expired token'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification(request):
    """Resend verification email"""
    profile = request.user.profile
    
    if profile.email_verified:
        return Response({
            'message': 'Email already verified'
        }, status=status.HTTP_200_OK)
    
    # Generate new token
    profile.email_verification_token = secrets.token_urlsafe(32)
    profile.save()
    
    # Send email
    try:
        send_verification_email(request.user, profile.email_verification_token)
        return Response({
            'message': 'Verification email sent'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': 'Failed to send email'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    """Request password reset email"""
    email = request.data.get('email')
    
    if not email:
        return Response({'error': 'Email required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email)
        profile = user.profile
        
        # Generate reset token (valid for 1 hour)
        reset_token = secrets.token_urlsafe(32)
        profile.password_reset_token = reset_token
        profile.password_reset_token_expires = timezone.now() + timedelta(hours=1)
        profile.save()
        
        # Send reset email
        reset_link = f"http://localhost:3000/reset-password?token={reset_token}"
        try:
            send_mail(
                'Password Reset - Emby',
                f'Click this link to reset your password: {reset_link}\n\nThis link will expire in 1 hour.\n\nIf you did not request this, please ignore this email.',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            return Response({
                'message': 'Password reset email sent. Please check your inbox.'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Email sending failed: {e}")
            return Response({
                'error': 'Failed to send email'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except User.DoesNotExist:
        # Don't reveal if email exists or not (security)
        return Response({
            'message': 'If an account with that email exists, a password reset link has been sent.'
        }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """Reset password with token"""
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    
    if not token or not new_password:
        return Response({'error': 'Token and new password required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        profile = Profile.objects.get(password_reset_token=token)
        
        # Check if token is expired
        if profile.password_reset_token_expires and profile.password_reset_token_expires < timezone.now():
            return Response({
                'error': 'Reset token has expired. Please request a new one.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate password
        try:
            validate_password(new_password, user=profile.user)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Reset password
        profile.user.set_password(new_password)
        profile.user.save()
        
        # Clear reset token
        profile.password_reset_token = ''
        profile.password_reset_token_expires = None
        profile.save()
        
        return Response({
            'message': 'Password reset successfully. You can now login with your new password.'
        }, status=status.HTTP_200_OK)
        
    except Profile.DoesNotExist:
        return Response({
            'error': 'Invalid or expired reset token'
        }, status=status.HTTP_400_BAD_REQUEST)


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
    """Submit complete onboarding data"""
    serializer = OnboardingSubmitSerializer(data=request.data)
    
    if serializer.is_valid():
        try:
            user = request.user
            profile = user.profile
            
            role = serializer.validated_data['role']
            school_name = serializer.validated_data['school_name']
            set_name = serializer.validated_data['set_name']
            class_code = serializer.validated_data.get('class_code', '')
            subscription_tier = serializer.validated_data['subscription_tier']
            responses = serializer.validated_data.get('responses', [])
            
            # Get or create school
            school, _ = School.objects.get_or_create(name=school_name)
            
            # Update profile
            profile.role = role
            profile.school = school
            profile.set_name = set_name
            
            # Handle class code logic
            if role == UserRole.CLASS_HEAD:
                # Request verification for class head
                profile.class_head_verification_requested = True
                profile.subscription_tier = SubscriptionTier.CLASS_HEAD
                
                # Check if class already exists for this school and set
                class_group = ClassGroup.objects.filter(
                    school=school,
                    set_name=set_name
                ).first()
                
                is_new_class = False
                if class_group:
                    # Check if class already has 3 heads
                    if class_group.class_heads.count() >= 3:
                        return Response({
                            'error': 'This class already has 3 class heads. Maximum limit reached.'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Add to existing class
                    profile.class_group = class_group
                    
                    # Notify existing class heads about new class head
                    existing_heads = class_group.class_heads.all()
                    if existing_heads.exists():
                        existing_heads_emails = [head.email for head in existing_heads]
                        try:
                            send_mail(
                                'New Class Head Added - Emby',
                                f'A new class head has joined your class: {user.get_full_name()} ({user.email})\n\nYour class now has {class_group.class_heads.count() + 1} class head(s).\n\nClass Code: {class_group.code}',
                                settings.DEFAULT_FROM_EMAIL,
                                existing_heads_emails,
                                fail_silently=False,
                            )
                        except Exception as e:
                            print(f"Email sending to existing heads failed: {e}")
                else:
                    # Create new class and generate code
                    class_group = ClassGroup.objects.create(
                        code=ClassGroup.generate_code(),
                        school=school,
                        set_name=set_name
                    )
                    profile.class_group = class_group
                    is_new_class = True
                
                # Send email with class code to new class head
                try:
                    if is_new_class:
                        send_mail(
                            'Your Class Code - Emby',
                            f'Congratulations! You are the first class head for {school_name} - {set_name}.\n\nYour class code is: {class_group.code}\n\nShare this code with your classmates to join.\n\nNote: Your account is pending verification. You will be notified once approved.',
                            settings.DEFAULT_FROM_EMAIL,
                            [user.email],
                            fail_silently=False,
                        )
                    else:
                        send_mail(
                            'Your Class Code - Emby',
                            f'You have joined as class head for {school_name} - {set_name}.\n\nYour class code is: {class_group.code}\n\nShare this code with your classmates to join.\n\nThere are currently {class_group.class_heads.count()} other class head(s) in this class.\n\nNote: Your account is pending verification. You will be notified once approved.',
                            settings.DEFAULT_FROM_EMAIL,
                            [user.email],
                            fail_silently=False,
                        )
                except Exception as e:
                    print(f"Email sending failed: {e}")
                
            elif class_code:
                # Join existing class (class_code is already validated and uppercased by serializer)
                try:
                    class_group = ClassGroup.objects.get(code=class_code, is_active=True)
                    profile.class_group = class_group
                    profile.subscription_tier = subscription_tier
                except ClassGroup.DoesNotExist:
                    return Response({
                        'error': 'Invalid class code'
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                profile.subscription_tier = subscription_tier
            
            profile.onboarding_completed = True
            profile.save()
            
            # Save onboarding responses
            for response_data in responses:
                question_id = response_data.get('question_id')
                answer = response_data.get('answer')
                
                if question_id and answer:
                    OnboardingResponse.objects.update_or_create(
                        user=user,
                        question_id=question_id,
                        defaults={'answer': answer}
                    )
            
            response_data = {
                'message': 'Onboarding completed successfully',
                'user': ProfileSerializer(profile).data,
                'class_code': profile.class_group.code if profile.class_group else None
            }
            
            # Add verification message for class heads
            if role == UserRole.CLASS_HEAD:
                response_data['verification_message'] = 'Your class head account is pending verification. You will receive an email once approved.'
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            import traceback
            print(f"Onboarding error: {str(e)}")
            traceback.print_exc()
            return Response({
                'error': f'Failed to complete onboarding: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    print(f"Serializer validation errors: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
    """Join class with code"""
    serializer = JoinClassSerializer(data=request.data)
    
    if serializer.is_valid():
        class_code = serializer.validated_data['class_code']
        profile = request.user.profile
        
        try:
            class_group = ClassGroup.objects.get(code=class_code, is_active=True)
            profile.class_group = class_group
            profile.save()
            
            return Response({
                'message': 'Successfully joined class',
                'class': ClassGroupSerializer(class_group).data
            }, status=status.HTTP_200_OK)
            
        except ClassGroup.DoesNotExist:
            return Response({
                'error': 'Invalid class code'
            }, status=status.HTTP_404_NOT_FOUND)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


# -------------------------
# CLASS HEAD VERIFICATION
# -------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_class_head_verification(request):
    """Request class head verification"""
    profile = request.user.profile
    
    if profile.role != UserRole.CLASS_HEAD:
        return Response({
            'error': 'Only class heads can request verification'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if profile.class_head_verified:
        return Response({
            'message': 'Already verified'
        }, status=status.HTTP_200_OK)
    
    profile.class_head_verification_requested = True
    profile.save()
    
    return Response({
        'message': 'Verification request submitted. You will be notified once approved.'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_class_head(request):
    """Admin endpoint to verify class head (requires admin permission)"""
    if not request.user.is_staff:
        return Response({
            'error': 'Admin permission required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    user_id = request.data.get('user_id')
    approved = request.data.get('approved', True)
    rejection_reason = request.data.get('rejection_reason', '')
    
    try:
        profile = Profile.objects.get(user_id=user_id, role=UserRole.CLASS_HEAD)
        
        if approved:
            profile.class_head_verified = True
            profile.class_head_verification_requested = False
            profile.class_head_rejection_reason = ''
            
            # Add user to class_heads ManyToMany
            if profile.class_group:
                profile.class_group.class_heads.add(profile.user)
            
            # Send approval email to the verified class head
            try:
                send_mail(
                    'Class Head Verification Approved - Emby',
                    f'Congratulations! Your class head account has been verified.\n\nYou now have full access to all premium features.\n\nYour class code: {profile.class_group.code if profile.class_group else "N/A"}',
                    settings.DEFAULT_FROM_EMAIL,
                    [profile.user.email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Email sending failed: {e}")
            
            # Notify other class heads about the verification
            if profile.class_group:
                other_heads = profile.class_group.class_heads.exclude(id=profile.user.id)
                if other_heads.exists():
                    other_heads_emails = [head.email for head in other_heads]
                    try:
                        send_mail(
                            'Class Head Verified - Emby',
                            f'{profile.user.get_full_name()} has been verified as a class head for your class.\n\nYour class now has {profile.class_group.class_heads.filter(profile__class_head_verified=True).count()} verified class head(s).',
                            settings.DEFAULT_FROM_EMAIL,
                            other_heads_emails,
                            fail_silently=False,
                        )
                    except Exception as e:
                        print(f"Email sending to other heads failed: {e}")
            
            message = 'Class head verified successfully'
        else:
            profile.class_head_verified = False
            profile.class_head_verification_requested = False
            profile.class_head_rejection_reason = rejection_reason
            
            # Send rejection email
            try:
                send_mail(
                    'Class Head Verification - Emby',
                    f'Your class head verification request was not approved.\n\nReason: {rejection_reason}\n\nPlease contact support for more information.',
                    settings.DEFAULT_FROM_EMAIL,
                    [profile.user.email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Email sending failed: {e}")
            
            message = 'Class head verification rejected'
        
        profile.save()
        
        return Response({
            'message': message,
            'user': ProfileSerializer(profile).data
        }, status=status.HTTP_200_OK)
        
    except Profile.DoesNotExist:
        return Response({
            'error': 'Class head profile not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_class_head_verifications(request):
    """Admin endpoint to get pending class head verifications"""
    if not request.user.is_staff:
        return Response({
            'error': 'Admin permission required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    pending_profiles = Profile.objects.filter(
        role=UserRole.CLASS_HEAD,
        class_head_verification_requested=True,
        class_head_verified=False
    )
    
    return Response(ProfileSerializer(pending_profiles, many=True).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """Get current user profile"""
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

class AnnouncementViewSet(viewsets.ModelViewSet):
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        profile = user.profile
        
        if profile.class_group:
            return Announcement.objects.filter(class_group=profile.class_group)
        return Announcement.objects.none()

    def perform_create(self, serializer):
        profile = self.request.user.profile
        
        # Only verified class heads can create announcements
        if not profile.is_class_head:
            raise PermissionError("Only verified class heads can create announcements")
        
        if not profile.class_group:
            raise PermissionError("You must be part of a class to create announcements")
        
        serializer.save(
            created_by=self.request.user,
            class_group=profile.class_group
        )


# -------------------------
# EXAM COUNTDOWN ENDPOINTS
# -------------------------

class ExamCountdownViewSet(viewsets.ModelViewSet):
    serializer_class = ExamCountdownSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        profile = user.profile
        
        if profile.class_group:
            return ExamCountdown.objects.filter(class_group=profile.class_group)
        return ExamCountdown.objects.none()

    def perform_create(self, serializer):
        profile = self.request.user.profile
        
        # Only verified class heads can create exam countdowns
        if not profile.is_class_head:
            raise PermissionError("Only verified class heads can create exam countdowns")
        
        if not profile.class_group:
            raise PermissionError("You must be part of a class to create exam countdowns")
        
        serializer.save(
            created_by=self.request.user,
            class_group=profile.class_group
        )


# -------------------------
# PAYMENT ENDPOINTS
# -------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    """Initiate Paystack payment for premium subscription"""
    import requests as http_requests
    
    user = request.user
    months = request.data.get('months', 1)
    # 1499 NGN/month, 15000 NGN/year
    amount = 15000 if months == 12 else 1499 * months
    
    # Create transaction
    reference = f"EMBY-{user.id}-{secrets.token_urlsafe(8)}"
    transaction = PaymentTransaction.objects.create(
        user=user,
        reference=reference,
        amount=amount,
        subscription_months=months
    )
    
    # Initialize Paystack payment
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "email": user.email,
        "amount": int(amount * 100),  # Convert to kobo
        "reference": reference,
        "callback_url": settings.PAYSTACK_CALLBACK_URL
    }
    
    response = http_requests.post(url, json=data, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        return Response({
            'authorization_url': result['data']['authorization_url'],
            'reference': reference
        })
    
    return Response({
        'error': 'Payment initialization failed'
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_payment(request):
    """Verify Paystack payment and activate premium"""
    import requests as http_requests
    
    reference = request.data.get('reference')
    
    if not reference:
        return Response({'error': 'Reference required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        transaction = PaymentTransaction.objects.get(reference=reference)
    except PaymentTransaction.DoesNotExist:
        return Response({'error': 'Transaction not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Verify with Paystack
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }
    
    response = http_requests.get(url, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        
        if result['data']['status'] == 'success':
            # Update transaction
            transaction.status = 'success'
            transaction.verified_at = timezone.now()
            transaction.save()
            
            # Activate premium subscription
            profile = transaction.user.profile
            profile.subscription_tier = SubscriptionTier.PREMIUM
            profile.subscription_expires_at = timezone.now() + timedelta(days=30 * transaction.subscription_months)
            profile.save()
            
            return Response({
                'message': 'Payment verified successfully',
                'user': ProfileSerializer(profile).data
            })
    
    transaction.status = 'failed'
    transaction.save()
    
    return Response({
        'error': 'Payment verification failed'
    }, status=status.HTTP_400_BAD_REQUEST)

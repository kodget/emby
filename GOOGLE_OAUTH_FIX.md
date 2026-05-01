# GOOGLE OAUTH 401 ERROR FIX

## Error
Backend returns 401 Unauthorized when trying to sign in with Google.

## Root Cause
The Google token verification is failing. This happens when:
1. Google Client ID mismatch between frontend and backend
2. Token is invalid or expired
3. Google API library issue

## Current Configuration

### Frontend (.env.local)
```
NEXT_PUBLIC_GOOGLE_CLIENT_ID=625488391443-9090eim5i185shvjjqmk63b2kjs12aah.apps.googleusercontent.com
```

### Backend (.env)
```
GOOGLE_CLIENT_ID=625488391443-9090eim5i185shvjjqmk63b2kjs12aah.apps.googleusercontent.com
```

✅ Client IDs match

## Debug Steps

### 1. Check Backend Logs
Look at the Django console for detailed error messages when Google login is attempted.

### 2. Test Backend Endpoint Directly
```bash
curl -X POST http://localhost:8000/auth/google-login/ \
  -H "Content-Type: application/json" \
  -d '{"token":"test_token"}'
```

Expected: Should see detailed error message

### 3. Verify Google OAuth Setup
Go to: https://console.cloud.google.com/apis/credentials

Check:
- ✅ OAuth 2.0 Client ID exists
- ✅ Authorized JavaScript origins includes: http://localhost:3000
- ✅ Authorized redirect URIs includes: http://localhost:3000

## Quick Fix Options

### Option 1: Update Backend View (Recommended)
The backend view needs better error handling. Update the google_login view to catch and log specific errors.

### Option 2: Bypass Google Verification (Development Only)
For testing, you can temporarily modify the backend to skip token verification.

**⚠️ NEVER use this in production!**

### Option 3: Use Email/Password Instead
While debugging Google OAuth, use the email/password signup:
1. Go to /signup
2. Fill in email, password, name
3. Click "Create account"

## Common Issues

### Issue 1: "Invalid token" error
**Cause:** Token expired or malformed
**Fix:** Refresh the page and try again

### Issue 2: "Client ID mismatch"
**Cause:** Frontend and backend have different Client IDs
**Fix:** Ensure both .env files have the same GOOGLE_CLIENT_ID

### Issue 3: "Unauthorized origin"
**Cause:** Google Console doesn't have localhost:3000 authorized
**Fix:** Add http://localhost:3000 to Authorized JavaScript origins

### Issue 4: google-auth library not installed
**Cause:** Missing Python package
**Fix:**
```bash
cd backend
pip install google-auth==2.34.0
```

## Temporary Workaround

Use email/password authentication instead of Google:

1. **Sign Up:**
   - Go to http://localhost:3000/signup
   - Enter email, password, first name, last name
   - Click "Create account"

2. **Sign In:**
   - Go to http://localhost:3000/signin
   - Enter email and password
   - Click "Sign in"

This bypasses Google OAuth entirely and should work immediately.

## Backend Fix Needed

The backend `google_login` view in `accounts/views.py` needs to:
1. Better error logging
2. Return more specific error messages
3. Handle token verification failures gracefully

### Current Code Issue
```python
except ValueError as e:
    return Response({
        'error': f'Invalid Google token: {str(e)}'
    }, status=status.HTTP_401_UNAUTHORIZED)
```

This catches ValueError but the actual error might be different.

### Improved Code
```python
except ValueError as e:
    print(f"Token verification failed: {str(e)}")
    return Response({
        'error': 'Invalid Google token',
        'detail': str(e)
    }, status=status.HTTP_401_UNAUTHORIZED)
except Exception as e:
    print(f"Unexpected error: {str(e)}")
    import traceback
    traceback.print_exc()
    return Response({
        'error': 'Authentication failed',
        'detail': str(e)
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

## Next Steps

1. ✅ Use email/password signup for now
2. ⏳ Check Django console logs for specific error
3. ⏳ Verify Google Console settings
4. ⏳ Update backend error handling
5. ⏳ Test Google login again

## Testing Email/Password Flow

```bash
# Test signup
curl -X POST http://localhost:8000/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123",
    "first_name": "Test",
    "last_name": "User"
  }'

# Test login
curl -X POST http://localhost:8000/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123"
  }'
```

Both should return tokens and user data.

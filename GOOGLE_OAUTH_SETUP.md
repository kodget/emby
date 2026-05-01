# Google OAuth Setup Guide

## Steps to Enable Google Login

### 1. Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google+ API**:
   - Go to "APIs & Services" → "Library"
   - Search for "Google+ API"
   - Click "Enable"

4. Create OAuth 2.0 Credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Choose "Web application"
   - Add authorized JavaScript origins:
     - `http://localhost:3000`
     - `http://127.0.0.1:3000`
   - Add authorized redirect URIs:
     - `http://localhost:3000`
     - `http://127.0.0.1:3000`
   - Click "Create"
   - Copy the **Client ID**

### 2. Configure Environment Variables

1. Create `.env.local` file in the root directory:
   ```bash
   cp .env.local.example .env.local
   ```

2. Add your Google Client ID:
   ```env
   NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_actual_client_id_here.apps.googleusercontent.com
   NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
   ```

### 3. Install Required Packages

```bash
npm install @react-oauth/google
```

### 4. Restart the Development Server

```bash
# Stop the server (Ctrl+C)
# Start again
npm run dev
```

### 5. Test Google Login

1. Go to http://localhost:3000/login
2. Click "Continue with Google"
3. Select your Google account
4. You should be redirected to the dashboard

---

## Troubleshooting

### "Google Client ID not found" Warning

**Problem**: The Google Client ID environment variable is not set.

**Solution**:
1. Make sure `.env.local` exists in the root directory
2. Verify `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is set correctly
3. Restart the dev server after adding environment variables

### "redirect_uri_mismatch" Error

**Problem**: The redirect URI doesn't match what's configured in Google Console.

**Solution**:
1. Go to Google Cloud Console → Credentials
2. Edit your OAuth 2.0 Client ID
3. Add these authorized redirect URIs:
   - `http://localhost:3000`
   - `http://127.0.0.1:3000`
4. Save and try again

### "Access blocked: This app's request is invalid"

**Problem**: The OAuth consent screen is not configured.

**Solution**:
1. Go to Google Cloud Console → "OAuth consent screen"
2. Choose "External" user type
3. Fill in required fields:
   - App name: "Emby"
   - User support email: your email
   - Developer contact: your email
4. Save and continue
5. Add scopes: `email`, `profile`, `openid`
6. Add test users (your email)
7. Save

### Backend Connection Issues

**Problem**: Frontend can't connect to Django backend.

**Solution**:
1. Make sure Django is running: `python manage.py runserver`
2. Check CORS settings in Django `settings.py`:
   ```python
   CORS_ALLOWED_ORIGINS = [
       'http://localhost:3000',
       'http://127.0.0.1:3000',
   ]
   ```
3. Verify backend URL in `.env.local` matches Django server

---

## Testing Without Google OAuth

If you want to test the app without setting up Google OAuth:

1. Click "Browse as Guest" on the login page
2. This will take you to the dashboard without authentication
3. Some features may be limited in guest mode

---

## Production Deployment

When deploying to production:

1. Add your production domain to Google Console:
   - Authorized JavaScript origins: `https://yourdomain.com`
   - Authorized redirect URIs: `https://yourdomain.com`

2. Update environment variables:
   ```env
   NEXT_PUBLIC_GOOGLE_CLIENT_ID=your_client_id
   NEXT_PUBLIC_API_URL=https://your-backend-api.com
   ```

3. Update Django CORS settings:
   ```python
   CORS_ALLOWED_ORIGINS = [
       'https://yourdomain.com',
   ]
   ```

---

## Current Status

✅ Google OAuth button styled correctly
✅ GoogleAuthProvider wrapper created
✅ Environment variables template created
⏳ Waiting for Google Client ID configuration

**Next Step**: Follow steps 1-4 above to complete the setup!

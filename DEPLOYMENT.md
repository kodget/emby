# Vercel Deployment Instructions

## Pre-Deployment Checklist

### 1. Update Environment Variables
- [ ] Update `NEXT_PUBLIC_API_URL` in `.env.local` to your production backend URL
- [ ] Verify all API keys and secrets are correct for production
- [ ] Test the backend API is accessible from the internet

### 2. Backend Requirements
Your Django backend needs to be deployed and accessible. Common options:
- Railway: https://railway.app
- Render: https://render.com  
- DigitalOcean: https://digitalocean.com
- AWS/Heroku/Google Cloud

### 3. Google OAuth Setup
Add your Vercel domain to Google OAuth settings:
- Go to Google Cloud Console > APIs & Credentials
- Edit your OAuth 2.0 Client ID
- Add authorized JavaScript origins:
  - https://your-app-name.vercel.app
  - https://your-custom-domain.com (if using custom domain)

### 4. Database Setup
Ensure your production database is set up and accessible by your backend.

## Deployment Steps

### Option 1: Vercel CLI
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel

# Follow prompts to link to your Vercel account
```

### Option 2: Vercel Dashboard
1. Go to https://vercel.com/dashboard
2. Click "New Project"
3. Import your GitHub repository
4. Configure environment variables in Vercel dashboard
5. Deploy

### Environment Variables to Set in Vercel Dashboard:
- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_PAYSTACK_PUBLIC_KEY`
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID`
- `NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME`
- `NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET`
- `NEXT_PUBLIC_VERCEL_ANALYTICS`

## Post-Deployment
1. Test all functionality on the deployed app
2. Update CORS settings in your Django backend to allow your Vercel domain
3. Test authentication flows
4. Monitor performance and errors

## Current Configuration Status:
? Next.js project configured
? Environment variables template ready
? .gitignore configured to exclude secrets
??  Backend URL needs to be updated
??  Google OAuth domains need to be added

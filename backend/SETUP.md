# Backend Setup Instructions

## Step 1: Activate Virtual Environment
```bash
# Navigate to backend directory
cd backend

# Activate your virtual environment (if you have one)
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

## Step 2: Run Migrations

### Create migrations for accounts (Profile model with streak field)
```bash
python manage.py makemigrations accounts
```

### Create migrations for curriculum (all new models)
```bash
python manage.py makemigrations curriculum
```

### Apply all migrations
```bash
python manage.py migrate
```

## Step 3: Seed Curriculum Data
```bash
python manage.py shell
```

Then inside the Python shell:
```python
exec(open("seed_curriculum.py").read())
```

Or as a one-liner:
```bash
python manage.py shell -c "exec(open('seed_curriculum.py').read())"
```

## Step 4: Create Superuser (if not already created)
```bash
python manage.py createsuperuser
```

## Step 5: Start Development Server
```bash
python manage.py runserver
```

## Verify Setup

1. Visit http://localhost:8000/admin/
2. Login with superuser credentials
3. Check that you can see:
   - Subjects (3: Anatomy, Physiology, Biochemistry)
   - Blocks (10 total)
   - Topics (17 total - only for Anatomy and Physiology)

## API Endpoints Available

### Curriculum
- GET `/api/subjects/` - List all subjects
- GET `/api/blocks/` - List all blocks
- GET `/api/blocks/?subject=anatomy` - Filter blocks by subject
- GET `/api/topics/` - List all topics
- GET `/api/topics/?block=anatomy-block-1` - Filter topics by block
- GET `/api/slides/` - List all slides
- POST `/api/slides/` - Create new slide (authenticated)

### Progress
- GET `/api/progress/` - User's progress on all slides
- GET `/api/progress/recent/` - Recently accessed slides
- POST `/api/progress/update_progress/` - Update progress on a slide

### Schedule
- GET `/api/schedule/` - User's schedule items
- GET `/api/schedule/today/` - Today's schedule
- GET `/api/schedule/upcoming/` - Next 7 days
- POST `/api/schedule/` - Create schedule item
- PUT `/api/schedule/{id}/` - Update schedule item
- DELETE `/api/schedule/{id}/` - Delete schedule item
- POST `/api/schedule/{id}/complete/` - Mark as complete
- POST `/api/schedule/{id}/uncomplete/` - Mark as incomplete

### Stats & Gamification
- GET `/api/stats/me/` - Current user's stats
- GET `/api/stats/leaderboard/` - Top users by points
- POST `/api/stats/award_points/` - Award points to user
- POST `/api/stats/update_streak/` - Update user's streak

### Community
- GET `/api/community/` - List all posts
- POST `/api/community/` - Create new post
- POST `/api/community/{id}/like/` - Like a post
- POST `/api/community/{id}/unlike/` - Unlike a post
- POST `/api/community/{id}/comment/` - Add comment

### Tests
- GET `/api/tests/` - List upcoming tests
- POST `/api/tests/` - Create new test (authenticated)

## Next Steps

After backend is set up:
1. Update frontend to fetch curriculum from API instead of `lib/curriculum.ts`
2. Connect reader component to progress tracking API
3. Sync schedule with backend
4. Implement file upload for slides
5. Connect all dashboard components to real data

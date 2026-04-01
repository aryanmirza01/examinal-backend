# 1. Create virtual env
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install deps
pip install -r requirements.txt

# 3. Create .env from example and fill in your API keys
cp .env.example .env

# 4. Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 5. Open API docs
# http://localhost:8000/docs

# 6. Create admin user
```python -c "
from app.database import SessionLocal, engine, Base
from app.models.user import User
from app.utils.security import hash_password
Base.metadata.create_all(bind=engine)
db = SessionLocal()
if not db.query(User).filter(User.role == 'admin').first():
    db.add(User(
        email='admin@examinal.com',
        username='admin',
        hashed_password=hash_password('admin123'),
        full_name='System Admin',
        role='admin',
    ))
    db.commit()
    print('Admin created: admin / admin123')
else:
    print('Admin already exists')
db.close()
```


## API Endpoint Summary

| Method | Endpoint | Role | Purpose |
| --- | --- | --- | --- |
| POST | /api/auth/register | Public | Register |
| POST | /api/auth/login | Public | Login → JWT |
| POST | /api/auth/refresh | Any | Refresh token |
| GET | /api/auth/me | Any | Current user |
| GET/PATCH/DELETE | /api/users/{id} | Admin/self | User CRUD |
| POST/GET/PATCH/DELETE | /api/courses/... | Instructor+ | Course CRUD |
| POST | /api/courses/{id}/enroll | Instructor+ | Enroll student |
| POST | /api/content/upload/{course_id} | Instructor+ | Upload file |
| POST | /api/content/ingest/{doc_id} | Instructor+ | Parse & embed |
| POST | /api/questions/generate | Instructor+ | RAG question gen |
| CRUD | /api/questions/... | Instructor+ | Manual question CRUD |
| CRUD | /api/exams/... | Instructor+ | Exam lifecycle |
| POST | /api/exams/{id}/publish | Instructor+ | Publish exam |
| POST | /api/exams/{id}/assign | Instructor+ | Assign students |
| POST | /api/submissions/start | Student | Begin exam |
| POST | /api/submissions/{id}/autosave | Student | Save progress |
| POST | /api/submissions/{id}/submit | Student | Final submit |
| POST | /api/submissions/activity | Student | Log proctoring event |
| POST | /api/grading/auto/{sub_id} | Instructor+ | Auto‑grade |
| POST | /api/grading/auto/exam/{id} | Instructor+ | Batch auto‑grade |
| PATCH | /api/grading/manual/{ans_id} | Instructor+ | Override score |
| GET | /api/analytics/exam/{id} | Instructor+ | Exam stats |
| GET | /api/analytics/student/{id} | Instructor+/self | Performance |
| GET | /api/analytics/course/{id} | Instructor+ | Course overview |
| GET | /api/admin/stats | Admin | Platform stats |
| GET | /api/admin/activity-logs | Admin | Audit trail |
| GET | /api/admin/exam/{id}/integrity | Admin | Cheating flags |

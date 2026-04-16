# 🍲 Kya Saabzi? (Backend)

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQLAlchemy 2.0](https://img.shields.io/badge/SQLAlchemy_2.0-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

**Kya Saabzi** is a high-craft backend service designed to solve the age-old daily household dilemma: *"Aaj kya banau?"* (What should I cook today?). It provides an intelligent, multi-tenant recommendation engine that respects household history, dietary preferences, and variety.

---

## ✨ Core Features

-   **🏠 Multi-tenant Households**: Users can create or join households, share kitchen history, and manage collective preferences.
-   **🍱 Intelligent Recommendation Engine**: 
    -   **Meal-Aware**: Automatically suggests Breakfast, Lunch, Snack, or Dinner based on local time.
    -   **Variety Safeguard**: Implements a 6-day cooldown to ensure your meals don't get repetitive.
    -   **Dietary Smart**: Respects household vegetarian/vegan preferences at the core level.
    -   **Hybrid Scoring**: Combines global popularity, your own history/ratings, and a touch of randomness.
-   **📜 Kitchen History (Cook Logs)**: Track exactly what was cooked, when, and how well it was received with ratings and personal notes.
-   **🔐 Enterprise-grade Auth & Security**: Secure JWT-based authentication (PyJWT) with password hashing (bcrypt), role-based access, and robust rate limiting (slowapi) to protect against brute-force attacks.
-   **🚀 Ready for Production**: Built-in Docker support, Alembic migrations, asynchronous database operations, proper connection pooling, and comprehensive logging.

---

## 🧠 The Recommendation Engine

The heart of "Kya Saabzi" is its **Hybrid Scoring Model**, which ensures quality results every time:

| Factor | Weight | Description |
| :--- | :---: | :--- |
| **Household History** | 50% | Prioritizes dishes your household loves and has rated highly in the past. |
| **Weighted Randomness** | 30% | Ensures the "Discovery" factor so you don't get stuck in a loop. |
| **Global Popularity** | 20% | Leverages community trends to suggest dishes that are currently popular. |

---

## 🛠️ Tech Stack

-   **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Async Python)
-   **ORM**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/)
-   **Database**: [PostgreSQL](https://www.postgresql.org/)
-   **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
-   **Security**: [PyJWT](https://pyjwt.readthedocs.io/), [passlib](https://passlib.readthedocs.io/), [slowapi](https://slowapi.readthedocs.io/)
-   **Validation**: [Pydantic v2](https://docs.pydantic.dev/)

---

## 🚀 Getting Started

### 1. Prerequisites
-   Python 3.10+
-   PostgreSQL instance

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/manav-gkmit/kya-saabzi-backend.git
cd kya-saabzi-backend

# Initialize virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory (refer to `.env.example`):
```env
SECRET_KEY="your-super-secret-key"
DATABASE_URL="postgres://user:password@localhost:5432/kyasaabzi"
CORS_ORIGINS=["http://localhost:3000"]
```

### 4. Database Setup & Seeding
```bash
# Run migrations
alembic upgrade head

# (Optional) Seed initial data (dishes, users, sample logs)
python -m app.seeders
```

### 5. Running the API
```bash
uvicorn app.main:app --reload
```
The API will be available at: [http://localhost:8000](http://localhost:8000)  
Interactive Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🐳 Docker Deployment

To run the entire stack using Docker:
```bash
cp .env.example .env
docker compose up --build
```

By default the container runs Alembic migrations and seeders on startup. To disable, set
`RUN_MIGRATIONS=0` and/or `RUN_SEEDERS=0` in your environment.

---

## 📂 Project Structure

```text
kya-saabzi-backend/
├── app/
│   ├── api/
│   │   └── v1/       # Versioned API Routers (Auth, Dish, Recommendation...)
│   ├── services/     # Business logic layer
│   ├── models/       # SQLAlchemy 2.0 Models
│   ├── schemas/      # Pydantic v2 Validation Schemas
│   ├── seeders/      # Database seeding scripts
│   ├── database/     # DB Session & configuration
│   └── utils/        # Organized utilities (auth, time, etc.)
├── alembic/          # Database migrations
├── tests/            # Pytest test suite
└── Dockerfile        # Containerization
```

---

## 🤝 Contributing

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

*Created with ❤️ for home chefs everywhere.*

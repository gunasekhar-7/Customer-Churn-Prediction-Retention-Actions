# Human Dependency Audit Report
**Customer Churn Prediction + Retention Intelligence Platform**

---

## 1. Project X-Ray (Plain English Summary)

### What This Project Actually Is
This is a **customer churn prediction platform** with three main components:

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend API** | **FastAPI** (Python 3.11) + **Uvicorn** (ASGI server) | REST API for predictions, explanations, retention recommendations; rate-limited, authenticated |
| **Dashboard** | **Streamlit** + **Plotly** | Internal web UI for business users to explore churn analytics, customer risk, SHAP explanations, revenue exposure |
| **Database** | **PostgreSQL 15** (via **SQLAlchemy 2.0** + **Alembic** migrations) | Persists predictions, retention recommendations, supports data minimization/retention cleanup |
| **ML Pipeline** | **scikit-learn** (LogisticRegression) + **XGBoost** + **SHAP** | Trains churn model, selects threshold on validation set, serializes artifact with drift monitoring reference data |
| **Infrastructure** | **Docker** + **Docker Compose** (local) / **AWS ECS Fargate** + **CloudFormation** (production) | Containerized deployment; CloudFormation provisions VPC, ALB, ECS, RDS, S3, CloudWatch, IAM |
| **CI/CD** | **GitHub Actions** | Lint (Ruff), type-check (mypy), tests (≥90% coverage), Docker builds, CloudFormation lint, PostgreSQL integration tests |

### Key External Services (Production Only)
- **AWS**: ECS Fargate, ALB, RDS PostgreSQL, S3 (model artifacts), CloudWatch, Secrets Manager, ACM (SSL), VPC, NAT Gateway
- **No third-party AI APIs** (OpenAI, Anthropic, etc.) — model is self-trained LogisticRegression
- **No external auth providers** (Clerk, Auth0, etc.) — uses simple API key authentication

---

## 2. Missing Environment Variables & Secrets (.env Audit)

**File to create:** Copy `.env.example` → `.env` in project root, then fill in values below.

| Variable Name | What It Is | How to Get It | Where to Put It |
|---------------|------------|---------------|-----------------|
| **DATABASE_URL** | PostgreSQL connection string (REQUIRED for production) | **Local:** Run `docker-compose up -d db` → use `postgresql://postgres:postgrespassword@localhost:5432/churn_db`<br>**AWS:** After RDS created, format: `postgresql+psycopg2://{{secretsmanager:arn}:username:password}}@endpoint:5432/dbname` | `.env` line 18 |
| **API_KEY** | Secret token for API authentication (min 32 chars) | Run: `openssl rand -base64 32` (Linux/Mac/Git Bash) or `python -c "import secrets; print(secrets.token_urlsafe(32))"` (cross-platform) | `.env` line 35 |
| **API_KEY_HEADER** | HTTP header name for API key | Default: `X-API-Key` (usually fine as-is) | `.env` line 38 |
| **ENVIRONMENT** | Deployment environment | Set to `development` (local), `staging`, or `production` | `.env` line 56 |
| **MODEL_ARTIFACTS_BUCKET** | S3 bucket name for model artifacts (prod only) | **AWS Console → S3 → Create bucket** (e.g., `my-churn-model-artifacts`) | `.env` line 81 (uncomment) |
| **MODEL_ARTIFACTS_KEY** | S3 key/path for model artifact (prod only) | Usually `model_v1.joblib` | `.env` line 83 (uncomment) |
| **RATE_LIMIT_ENABLED** | Enable rate limiting | `true` or `false` | `.env` line 23 |
| **CORS_ORIGINS** | Comma-separated allowed origins | Local: `http://localhost:8501,http://127.0.0.1:8501`<br>Prod: your dashboard URL(s) | `.env` line 45 |
| **LOG_LEVEL** | Logging verbosity | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `.env` line 50 |
| **DATA_RETENTION_DAYS** | Days before prediction records auto-deleted | Integer (default `90`) | `.env` line 63 |
| **DATA_MINIMIZATION_ENABLED** | Strip PII from stored prediction data | `true` or `false` | `.env` line 75 |
| **DB_POOL_SIZE** | DB connections per worker | Integer (default `5`) | Not in `.env.example` — add if needed |
| **DB_MAX_OVERFLOW** | Extra DB connections per worker | Integer (default `10`) | Not in `.env.example` — add if needed |

### ⚠️ Production-Only Variables (Required when `ENVIRONMENT=production`)
| Variable | Must Be Set? | Validation |
|----------|--------------|------------|
| `DATABASE_URL` | ✅ Yes | Must not contain `postgres:postgres` |
| `API_KEY` | ✅ Yes | Must be ≥32 chars |
| `MODEL_ARTIFACTS_BUCKET` | ✅ Yes | S3 bucket must exist |
| `MODEL_ARTIFACTS_KEY` | ✅ Yes | Must match uploaded artifact |
| `SSLCertificateArn` | ✅ Yes (CloudFormation) | ACM cert in us-east-1 |

---

## 3. External Dashboard & Cloud Configurations

### Database Setup
| Environment | Action Required |
|-------------|-----------------|
| **Local (Docker Compose)** | Run `docker-compose up -d db` — starts PostgreSQL 15 in container, creates `churn_db` database, runs migrations via `migrate` service |
| **Local (No Docker)** | Install PostgreSQL 15 locally, create database `churn_dev.db` (SQLite fallback) or `churn_db` (PostgreSQL), run `alembic upgrade head` |
| **AWS (CloudFormation)** | **Two modes:**<br>1. **`DatabaseMode=external`** (default): You provide existing RDS endpoint + Secrets Manager ARN<br>2. **`DatabaseMode=create`**: Stack provisions RDS PostgreSQL 15 (Multi-AZ optional) in private subnets |

### Authentication / OAuth
- **No external auth provider** (Clerk, Auth0, Firebase, Google Login, etc.)
- **Simple API Key** authentication via `X-API-Key` header
- **No redirect/callback URLs** to configure anywhere

### CORS / Whitelisting
| Environment | Action |
|-------------|--------|
| **Local** | `.env` has `CORS_ORIGINS=http://localhost:8501,http://127.0.0.1:8501` — works out of the box |
| **AWS** | CloudFormation ALB allows `0.0.0.0/0` on port 443/80; dashboard talks to API via private ALB DNS name (`API_URL=https://<alb-dns>/api`) |

### Billing / Quotas / Credit Cards
| Service | Billing Impact |
|---------|----------------|
| **AWS** | **YES — requires credit card on AWS account**. Resources created: ECS Fargate tasks, ALB, NAT Gateways (2×), RDS (if `create`), S3, CloudWatch Logs/Metrics, KMS, VPC Endpoints. Estimated ~$200–400/month for staging (see `docs/AWS_DEPLOYMENT.md` §7). |
| **OpenAI / Anthropic / Other AI APIs** | **NO** — model is self-trained scikit-learn LogisticRegression |
| **Third-party SaaS (Auth0, Stripe, etc.)** | **NO** |

---

## 4. Local System Prerequisites

### Required Software
| Tool | Version | Verify Command | Install If Missing |
|------|---------|----------------|-------------------|
| **Python** | 3.11+ | `python --version` | [python.org](https://python.org) or `winget install Python.Python.3.11` |
| **Git** | 2.x | `git --version` | [git-scm.com](https://git-scm.com) |
| **Docker Desktop** | 24+ (with Buildx) | `docker version` && `docker buildx version` | [docker.com/products/docker-desktop](https://docker.com/products/docker-desktop) — **must be running** |
| **AWS CLI** | 2.x (for deployment only) | `aws --version` | `winget install Amazon.AWSCLI` |
| **PostgreSQL** | 15+ (if not using Docker) | `psql --version` | [postgresql.org/download](https://postgresql.org/download) |

### Background Services That Must Be Running
| Service | How to Start | Verify |
|---------|--------------|--------|
| **Docker Desktop** | Open Docker Desktop app; wait for "Docker Desktop is running" | `docker ps` returns without error |
| **PostgreSQL (if not Docker)** | `sudo systemctl start postgresql` (Linux) / `brew services start postgresql@15` (Mac) | `psql -h localhost -U postgres -c "SELECT 1"` |

### Verify Commands
```bash
# All should succeed before proceeding
python --version          # → Python 3.11.x
docker version            # → Client/Server version info
docker buildx version     # → Buildx version info
docker-compose --version  # → v2.x
git --version             # → Git version
```

---

## 5. Exact Ignition Sequence

### Option A: Local Development (No Docker) — Fastest for Coding
```bash
# 1. Clone & enter
git clone https://github.com/gunasekhar-7/Customer-Churn-Prediction-Retention-Actions.git
cd Customer-Churn-Prediction-Retention-Actions

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows PowerShell

# 3. Install dependencies
pip install --upgrade pip
pip install -e .[dev]

# 4. Configure environment
cp .env.example .env
# Edit .env — at minimum set: ENVIRONMENT=development (default), leave DATABASE_URL empty for SQLite fallback

# 5. Generate test model artifact (required for API tests)
python -m scripts.create_test_artifact

# 6. Run API server (terminal 1)
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000

# 7. Run dashboard (terminal 2)
streamlit run dashboard/app.py --server.port 8501

# 8. Run tests (terminal 3)
pytest --cov=src --cov-fail-under=90
ruff check .
mypy src/
```

### Option B: Full Local Stack (Docker Compose) — Matches Production Closest
```bash
# 1. Prerequisites: Docker Desktop RUNNING
docker ps  # should work without error

# 2. Clone & enter
git clone https://github.com/gunasekhar-7/Customer-Churn-Prediction-Retention-Actions.git
cd Customer-Churn-Prediction-Retention-Actions

# 3. Generate test model artifact (needed for Docker build)
python -m scripts.create_test_artifact

# 4. Build & start everything (PostgreSQL + migrations + API + Dashboard)
docker-compose up --build

# 5. Verify
curl http://localhost:8000/health        # → {"status":"ok"}
curl http://localhost:8501/_stcore/health # → 200 OK
open http://localhost:8501                # Dashboard UI

# 6. Run tests inside container (optional)
docker-compose exec api pytest --cov=src --cov-fail-under=90
```

### Option C: Production Deployment (AWS) — Requires Human AWS Setup
```bash
# Prerequisites (MANUAL — cannot be automated):
# 1. AWS account with credit card + admin IAM user/role
# 2. VPC with 2 public + 2 private subnets across 2 AZs
# 3. ACM certificate in us-east-1 for your domain (e.g., *.example.com)
# 4. (Optional) Existing RDS PostgreSQL 15 + Secrets Manager credential ARN
# 5. ECR repositories for API + Dashboard images (or let CI push them)

# 6. Push to trigger CI (builds Docker images, runs tests)
git push origin main

# 7. Deploy CloudFormation (replace values)
aws cloudformation deploy \
  --stack-name churn-platform-prod \
  --template-file cloudformation/ecs-cluster.yml \
  --parameter-overrides \
    VpcId=vpc-xxxxxxxx \
    PrivateSubnetIds=subnet-xxx,subnet-yyy \
    PublicSubnetIds=subnet-aaa,subnet-bbb \
    ApiImageUrl=123456789.dkr.ecr.us-east-1.amazonaws.com/churn-api:latest \
    DashboardImageUrl=123456789.dkr.ecr.us-east-1.amazonaws.com/churn-dashboard:latest \
    DatabaseMode=external \
    DatabaseEndpoint=churn-db.xxxxx.us-east-1.rds.amazonaws.com \
    DatabaseSecretArn=arn:aws:secretsmanager:us-east-1:123456789:secret:churn-db-creds-xxx \
    ApiKeySecretArn=arn:aws:secretsmanager:us-east-1:123456789:secret:churn-api-key-xxx \
    SSLCertificateArn=arn:aws:acm:us-east-1:123456789:certificate/xxxx \
    Environment=production \
  --capabilities CAPABILITY_NAMED_IAM
```

---

## Quick Reference: What Fails Without Human Action

| If You Skip… | What Breaks |
|--------------|-------------|
| `cp .env.example .env` + `API_KEY` | API returns 401/403 on all protected endpoints in production mode |
| `DATABASE_URL` (production) | Startup crash: `RuntimeError: DATABASE_URL must be set in production environment` |
| `MODEL_ARTIFACTS_BUCKET/KEY` (production) | Startup crash: `MODEL_ARTIFACTS_BUCKET and MODEL_ARTIFACTS_KEY must be set in production` |
| `docker-compose up -d db` (local Docker) | API can't connect to PostgreSQL; falls back to SQLite (no persistence across restarts) |
| `python -m scripts.create_test_artifact` | API tests fail: `FileNotFoundError: Artifact not found at models/model_v1.joblib` |
| AWS credit card / VPC / ACM cert | CloudFormation deploy fails at resource creation |
| Docker Desktop not running | `docker-compose` fails with "Cannot connect to the Docker daemon" |

---

## Need Help? Run This First
If anything fails, run this diagnostic and paste the output:
```bash
cd Customer-Churn-Prediction-Retention-Actions
python -c "
import sys, subprocess, os
print('Python:', sys.version)
print('Docker:', subprocess.run(['docker','version','--format','{{.Server.Version}}'], capture_output=True, text=True).stdout.strip() or 'NOT RUNNING')
print('Docker Compose:', subprocess.run(['docker-compose','version','--short'], capture_output=True, text=True).stdout.strip() or 'NOT FOUND')
print('Git:', subprocess.run(['git','--version'], capture_output=True, text=True).stdout.strip())
print('PostgreSQL:', subprocess.run(['psql','--version'], capture_output=True, text=True).stdout.strip() or 'NOT FOUND')
print('Env file exists:', os.path.exists('.env'))
print('DATABASE_URL set:', bool(os.getenv('DATABASE_URL')))
print('API_KEY set:', bool(os.getenv('API_KEY')))
print('Models dir exists:', os.path.exists('models/model_v1.joblib'))
"
```
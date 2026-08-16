# Project: DevOps Lab — URL Shortener in Production

## Core Idea

You will build and operate a **URL shortener** (like bit.ly) from scratch all the way to a full production setup.
The application is simple enough that you won't get stuck on the code, but rich enough to apply
every phase of the roadmap in a progressive and cohesive way.

Suggested repository name: `github.com/your-username/devops-lab`

---

## Phase 0 — Fundamentals: The App on a Bare Server

**Goal:** get the application running on a Linux server manually.

- Provision a VM (AWS EC2 Free Tier or local VirtualBox)
- Set up a non-root user, firewall (ufw), SSH key authentication, open ports
- Install Python and pip manually
- Start the URL shortener API directly with `python app.py`
- The application automatically writes logs to `logs/app.log`

> 💡 **Note for DevOps/SRE-focused learners:** the code below is already done. Your job in this phase is to **get it running on a Linux server** — installing dependencies, configuring the firewall, opening ports, and managing the process. The code itself is just the starting point.

---

### 📄 `requirements.txt`

```txt
flask==3.0.3
```

---

### 📄 `app.py`

```python
import os
import string
import random
import logging
from datetime import datetime
from flask import Flask, request, jsonify, redirect, abort

# ── Logging Setup ─────────────────────────────────────────────────────────────
# The logs/ directory is created automatically if it does not exist.
# In production, this file will be monitored by your observability stack (Phase 6).
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),   # file — read by Loki/ELK in Phase 6
        logging.StreamHandler()                 # stdout — captured by Docker in Phase 3
    ]
)
logger = logging.getLogger(__name__)

# ── Flask Application ─────────────────────────────────────────────────────────
app = Flask(__name__)

# In-memory database (simple to start with).
# In Phase 2 this will be replaced by PostgreSQL on AWS RDS.
db = {}


def generate_code(length=6):
    """Generates a random short code made of letters and digits."""
    characters = string.ascii_letters + string.digits
    return "".join(random.choices(characters, k=length))


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    """
    Health check endpoint — used by load balancers, Kubernetes liveness probes,
    and monitoring tools (Phase 6 and Phase 7).
    Returns 200 if the application is healthy.
    """
    logger.info("healthcheck ok")
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


@app.route("/shorten", methods=["POST"])
def shorten():
    """
    Shortens a URL.
    Receives: { "url": "https://example.com/very-long-path" }
    Returns:  { "short_code": "aB3xYz", "short_url": "/r/aB3xYz" }
    """
    data = request.get_json()

    if not data or "url" not in data:
        logger.warning("invalid request on /shorten — missing 'url' field")
        return jsonify({"error": "Please provide the 'url' field in the JSON body."}), 400

    original_url = data["url"]

    # Avoid duplicates: if the URL was already shortened, return the same code
    for code, url in db.items():
        if url == original_url:
            logger.info("existing url reused | code=%s url=%s", code, original_url)
            return jsonify({"short_code": code, "short_url": f"/r/{code}"})

    code = generate_code()
    while code in db:          # ensure uniqueness
        code = generate_code()

    db[code] = original_url
    logger.info("url shortened | code=%s url=%s", code, original_url)
    return jsonify({"short_code": code, "short_url": f"/r/{code}"}), 201


@app.route("/r/<code>")
def redirect_to(code):
    """
    Redirects to the original URL from the short code.
    Returns 404 if the code does not exist — tracked as an error in Phase 6.
    """
    original_url = db.get(code)

    if not original_url:
        logger.warning("code not found | code=%s ip=%s", code, request.remote_addr)
        abort(404)

    logger.info("redirect | code=%s destination=%s ip=%s",
                code, original_url, request.remote_addr)
    return redirect(original_url, code=302)


@app.route("/stats")
def stats():
    """
    Basic application statistics.
    Useful for validating the app and, later, exposing metrics to Prometheus (Phase 6).
    """
    logger.info("stats requested | total_urls=%d", len(db))
    return jsonify({
        "total_shortened_urls": len(db),
        "urls": {code: url for code, url in db.items()}
    })


# ── Error Handlers ────────────────────────────────────────────────────────────
# JSON error responses — standard for APIs. Error logs here
# will be counted as 4xx/5xx on the Grafana dashboard in Phase 6.

@app.errorhandler(404)
def not_found(e):
    logger.error("404 not found | path=%s", request.path)
    return jsonify({"error": "Resource not found."}), 404


@app.errorhandler(500)
def internal_error(e):
    logger.error("500 internal server error | path=%s error=%s", request.path, str(e))
    return jsonify({"error": "Internal server error."}), 500


# ── Startup ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    logger.info("application starting on port %d", port)
    app.run(host="0.0.0.0", port=port)
```

---

### ▶️ How to run (Linux commands — DevOps focus)

```bash
# 1. Install dependencies (run on your EC2 instance or local VM)
pip install -r requirements.txt

# 2. Create the logs directory (created automatically by the app, but good to know)
mkdir -p logs

# 3. Start the application
python app.py

# 4. Test the endpoints (in a separate terminal)

# Shorten a URL:
curl -X POST http://localhost:5001/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.google.com"}'

# Check the health endpoint:
curl http://localhost:5001/health

# View statistics:
curl http://localhost:5001/stats

# 5. Watch logs in real time (essential SRE skill):
tail -f logs/app.log
```

---

### 🔍 What to look for in the logs (SRE mindset from day one)

```
# Successful URL shortening:
2026-08-03 10:01:02,123 INFO url shortened | code=aB3xYz url=https://google.com

# Redirect log (shows client IP — useful for traffic analysis):
2026-08-03 10:01:05,456 INFO redirect | code=aB3xYz destination=https://google.com ip=192.168.1.10

# Warning log (code not found — a spike of 404s is a potential incident):
2026-08-03 10:01:08,789 WARNING code not found | code=xYz999 ip=192.168.1.55

# Error log (500 — should trigger an alert in Grafana in Phase 6):
2026-08-03 10:01:10,000 ERROR 500 internal server error | path=/shorten error=...
```

> 💡 **Why are logs formatted this way?** The `key=value` format (known as logfmt) is intentional — tools like Loki and Elasticsearch can automatically index and filter these fields in Phase 6. Good practice from day one.

---

### Deliverable on GitHub

```
/
├── app.py
├── requirements.txt
├── README.md           # How to run manually (describe the steps above)
└── logs/
    └── .gitkeep        # Commits the empty directory; app.log is generated at runtime
```

> Add `logs/app.log` to your `.gitignore` — never commit log files to the repository.

---

### 📚 References for this phase

| Resource | What you will use it for |
|---|---|
| [Linux Journey](https://linuxjourney.com) | Permissions, processes, SSH, firewall |
| [Introduction to Linux — edX / Linux Foundation](https://www.edx.org/course/introduction-to-linux) | Full Linux CLI and administration fundamentals |
| [OverTheWire: Bandit](https://overthewire.org/wargames/bandit/) | Gamified terminal practice |
| [Flask — Quickstart Docs](https://flask.palletsprojects.com/en/latest/quickstart/) | Understanding the URL shortener API |
| [Pro Git Book](https://git-scm.com/book/en/v2) | Git: branches, commits, version tags |
| [AWS Free Tier](https://aws.amazon.com/free/) | Spin up the EC2 instance for free |

---

## Phase 1 — Scripting: Automate the Tedium

**Goal:** no repetitive task should ever be done by hand twice.

- Script `setup.sh`: installs dependencies, creates a non-root user, configures the firewall
- Script `parse_logs.py`: reads `app.log` and generates a report (top accessed URLs, errors, peak hours)
- Script `backup.sh`: backs up the SQLite database to a timestamped directory
- Set up a `cron job` to run the backup daily

### Deliverable

```
/scripts
├── setup.sh
├── parse_logs.py
└── backup.sh
```

### 📚 References for this phase

| Resource | What you will use it for |
|---|---|
| [Automate the Boring Stuff with Python](https://automatetheboringstuff.com) | File manipulation, log parsing, and automation with Python |
| [Bash Scripting Tutorial — Ryan's Tutorials](https://ryanstutorials.net/bash-scripting-tutorial/) | Writing `setup.sh` and `backup.sh` |
| [freeCodeCamp — Python for Everybody (YouTube)](https://www.youtube.com/watch?v=8DvywoWv6fI) | Python logic for `parse_logs.py` |
| [Cron Job Tutorial — phoenixNAP](https://phoenixnap.com/kb/set-up-cron-job-linux) | Setting up the automated daily backup |
| [techiescamp/python-for-devops (GitHub)](https://github.com/techiescamp/python-for-devops) | Real-world examples of log parsing and SSH automation |

---

## Phase 2 — Cloud: Off Your Laptop

**Goal:** the application moves to AWS, managed via the console first.

- Migrate to EC2 (t2.micro) with an Elastic IP
- Move the SQLite database to RDS (PostgreSQL Free Tier)
- Store backups in S3 (update `backup.sh`)
- Set up users and minimal permissions via IAM (principle of least privilege)
- Use CloudWatch to receive CPU and error alerts by email

**Deliverable:** update `README.md` with the current architecture and an AWS diagram (draw.io works well).

### 📚 References for this phase

| Resource | What you will use it for |
|---|---|
| [AWS Skill Builder](https://skillbuilder.aws) | Official AWS courses on EC2, S3, RDS, IAM, and CloudWatch |
| [freeCodeCamp — AWS Cloud Practitioner (YouTube)](https://www.youtube.com/watch?v=SOTamWNgDKc) | Understanding the AWS services used in this phase |
| [AWS — Getting Started with EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html) | Official EC2 documentation |
| [AWS — Setting up RDS PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_GettingStarted.CreatingConnecting.PostgreSQL.html) | Migrating the database to the cloud |
| [draw.io](https://draw.io) | Drawing the AWS architecture diagram for the README |
| [IAM Best Practices — AWS Docs](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html) | Configuring minimal permissions correctly |

---

## Phase 3 — Containers: Goodbye "Works on My Machine"

**Goal:** package everything in Docker to guarantee reproducibility.

- Write a `Dockerfile` for the Flask application
- Create a `docker-compose.yml` with the app + local PostgreSQL
- Configure environment variables via `.env` (never commit secrets!)
- Add a `.dockerignore` and apply image best practices (multi-stage build)
- Publish the image to Docker Hub or GitHub Container Registry

### Deliverable

```
/
├── Dockerfile
├── docker-compose.yml
├── .env.example        # Template without real values
└── .dockerignore
```

### 📚 References for this phase

| Resource | What you will use it for |
|---|---|
| [Play with Docker](https://labs.play-with-docker.com) | Practice Docker in the browser without installing anything |
| [Docker — Get Started (Official Docs)](https://docs.docker.com/get-started/) | Writing a correct Dockerfile and docker-compose file |
| [Docker — Dockerfile Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/) | Multi-stage builds and lean images |
| [Docker Hub](https://hub.docker.com) | Publishing the application image |
| [freeCodeCamp — Docker Tutorial (YouTube)](https://www.youtube.com/watch?v=fqMOX6JJhGo) | Full Docker video course |
| [Play with Kubernetes](https://labs.play-with-k8s.com) | Browser-based Kubernetes practice for the next phase |

---

## Phase 4 — IaC: Infrastructure as Code

**Goal:** all AWS infrastructure must be reproducible with a single command.

- Write Terraform to provision: VPC, subnet, security group, EC2, RDS, S3
- Use variables and outputs to make modules reusable
- Separate environments using workspaces: `dev` and `prod`
- Store `terraform.tfstate` in S3 with locking via DynamoDB

### Deliverable

```
/infra
├── main.tf
├── variables.tf
├── outputs.tf
├── modules/
│   ├── ec2/
│   ├── rds/
│   └── s3/
└── README.md           # How to use: terraform init, plan, apply
```

### 📚 References for this phase

| Resource | What you will use it for |
|---|---|
| [HashiCorp Developer — Terraform Tutorials](https://developer.hashicorp.com/terraform/tutorials) | Official tutorials: AWS provider, modules, remote state |
| [freeCodeCamp — Terraform Course (YouTube)](https://www.youtube.com/watch?v=SLB_c_ayRMo) | Full Terraform video course |
| [Terraform AWS Provider Docs](https://registry.terraform.io/providers/hashicorp/aws/latest/docs) | Reference for every AWS resource (EC2, RDS, S3...) |
| [Terraform — Remote State with S3 + DynamoDB](https://developer.hashicorp.com/terraform/language/settings/backends/s3) | Setting up a secure backend for tfstate |
| [awesome-tf (GitHub)](https://github.com/shuaibiyy/awesome-tf) | Curated list of Terraform examples and ready-made modules |

---

## Phase 5 — CI/CD: Automated Deployment

**Goal:** every push to `main` should automatically test and deploy.

- Create a GitHub Actions pipeline with the following stages:
  1. `lint` — code style check (flake8)
  2. `test` — unit tests (pytest)
  3. `build` — Docker image build and push
  4. `deploy` — apply Terraform and restart the service on EC2 via SSH
- Use GitHub Secrets for AWS credentials and SSH keys
- Enable branch protection: PRs must pass CI before merging

### Deliverable

```
/.github/workflows
├── ci.yml              # Lint + Test on every PR
└── deploy.yml          # Build + Deploy when merging to main
```

### 📚 References for this phase

| Resource | What you will use it for |
|---|---|
| [GitHub Actions — Official Docs](https://docs.github.com/en/actions) | Workflow syntax, jobs, steps, and secrets |
| [freeCodeCamp — GitHub Actions Course (YouTube)](https://www.youtube.com/watch?v=R8_veQiYBjI) | Building the full CI/CD pipeline |
| [GitHub Actions — Marketplace](https://github.com/marketplace?type=actions) | Ready-made actions: checkout, setup-python, configure-aws |
| [GitHub Docs — Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) | Requiring CI to pass before merging to main |
| [pytest — Official Docs](https://docs.pytest.org/en/stable/) | Writing unit tests for the Flask application |

---

## Phase 6 — Observability: See What Is Happening

**Goal:** know what the application is doing without ever SSHing into the server.

- Install and configure **Prometheus** + **Grafana** via docker-compose
- Expose Flask metrics with `prometheus-flask-exporter`
- Build Grafana dashboards for:
  - Requests per second
  - Latency (p50, p95, p99)
  - Error rate (4xx, 5xx)
  - Top shortened URLs
- Set up alerts: error rate > 5% or latency > 500ms triggers a Slack/email notification

### Deliverable

```
/monitoring
├── prometheus.yml
├── alert.rules.yml
└── grafana/
    └── dashboards/
        └── url-shortener.json
```

### 📚 References for this phase

| Resource | What you will use it for |
|---|---|
| [Prometheus — Getting Started](https://prometheus.io/docs/prometheus/latest/getting_started/) | Configuring `prometheus.yml` and writing PromQL queries |
| [prometheus-flask-exporter (GitHub)](https://github.com/rycus86/prometheus_flask_exporter) | Automatically exposing Flask application metrics |
| [Grafana — Official Tutorials](https://grafana.com/tutorials/) | Building latency and error rate dashboards |
| [Grafana — Alerting Docs](https://grafana.com/docs/grafana/latest/alerting/) | Configuring Slack/email alert notifications |
| [KillerCoda — Prometheus Labs](https://killercoda.com/killercoda/course/Prometheus) | Browser-based PromQL and alerting practice |
| [freeCodeCamp — Prometheus & Grafana (YouTube)](https://www.youtube.com/watch?v=9TJx7QTrTyo) | Full monitoring stack setup video |

---

## Phase 7 — SRE: Operating Like a Professional

**Goal:** treat the application with production-grade rigor.

- Define SLOs in the README:
  - Availability: 99.5% per month
  - Latency: p95 < 200ms
  - Error budget: 3.6 hours/month of acceptable downtime
- Write **Runbooks** for common incidents:
  - "App is returning mass 500 errors"
  - "Database is unreachable"
  - "EC2 disk is full"
- Intentionally simulate an incident (take the database down, generate load) and write a **postmortem**
- Configure health checks and automatic restarts with `systemd` or a Kubernetes liveness probe

### Deliverable

```
/docs
├── SLO.md
├── runbooks/
│   ├── high-error-rate.md
│   ├── database-down.md
│   └── disk-full.md
└── postmortems/
    └── 2026-08-01-database-outage.md
```

### 📚 References for this phase

| Resource | What you will use it for |
|---|---|
| [Google SRE Book — SLOs (free online)](https://sre.google/sre-book/service-level-objectives/) | Correctly defining SLIs, SLOs, and error budgets |
| [Google SRE Workbook — Implementing SLOs](https://sre.google/workbook/implementing-slos/) | Real-world examples of SLO implementation |
| [Google SRE Book — Postmortem Culture](https://sre.google/sre-book/postmortem-culture/) | Blameless postmortem structure and culture |
| [Postmortem template — PagerDuty (GitHub)](https://github.com/PagerDuty/postmortem-docs) | Ready-to-use postmortem template to adapt |
| [Runbook template — Atlassian](https://www.atlassian.com/incident-management/runbook) | Runbook structure for incident response |
| [Google SRE Classroom](https://sre.google/classroom/) | Google's workshop on designing reliable systems |
| [Awesome SRE (GitHub)](https://github.com/dastergon/awesome-sre) | Curated list of SRE articles, tools, and resources |

---

## Final Repository Structure

```
devops-lab/
├── app.py                # URL shortener Flask application
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── scripts/              # Bash and Python automation scripts
├── infra/                # Terraform infrastructure code
├── monitoring/           # Prometheus, Grafana, alert rules
├── docs/                 # SLOs, Runbooks, Postmortems
├── .github/workflows/    # CI/CD pipelines
└── README.md             # Overview + architecture + how to run
```

---

## Golden Tips

- **Commit at every sub-step**: use git tags (`v0-linux`, `v1-scripts`, `v2-cloud`...) to mark the evolution — recruiters can see your entire journey in the commit history
- **Document the "why"**: not just what you did, but why you chose that approach
- **Open issues for yourself**: simulate a real work environment with tasks and pull requests
- **Write an impeccable README**: it is your showcase for recruiters
- **Don't skip phases**: the beauty of this project is showing the complete progression
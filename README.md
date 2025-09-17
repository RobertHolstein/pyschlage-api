pyschlage-api
=============

[![CI](https://github.com/RobertHolstein/pyschlage-api/actions/workflows/ci.yml/badge.svg)](https://github.com/RobertHolstein/pyschlage-api/actions/workflows/ci.yml)

A FastAPI wrapper around the [`pyschlage`](https://pypi.org/project/pyschlage/) library that exposes Schlage lock functionality over a local REST API. It is intended for use with home-automation systems (for example n8n) that need a simple HTTP interface to Schlage Connect/Encode locks.

Features
--------

- Lists Schlage locks registered to your account
- Retrieves detailed lock state (battery, jammed, firmware, etc.)
- Requests lock/unlock actions
- Exposes recent activity logs
- Reads programmed access codes, including schedule metadata
- Ships with Docker support and a lightweight smoke-test script

Requirements
------------

- Python 3.9+ (if running locally)
- Schlage account credentials (email + password)
- [`pyschlage` API access](https://github.com/bdraco/pyschlage)
- Docker (optional, for containerized deployment)

Quick Start
-----------

### 1. Configure Environment Variables

Copy the example file and populate it with your credentials:

```
cp .env.example .env
```

Edit `.env` and set:

```
SCHLAGE_USERNAME=your-email@example.com
SCHLAGE_PASSWORD=your-password
```

> **Security:** Never commit `.env`—it is already ignored by `.gitignore`.

### 2. Run Locally (without Docker)

```
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit <http://localhost:8000/docs> for interactive API documentation and manual testing.

### 3. Run Using Docker

```
docker build -t pyschlage-api .
docker run -d --name schlage-api-container \
  -p 8000:8000 \
  --env-file .env \
  pyschlage-api
```

Confirm the service is healthy:

```
curl http://localhost:8000/health
```

### 4. Smoke Test All Endpoints

The repository includes a simple script that validates every endpoint without actuating the lock by default:

```
python3 scripts/test_api.py --base-url http://localhost:8000
```

Add `--actuate` if you want to exercise the lock/unlock endpoints.

API Summary
-----------

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/health` | Simple health probe |
| GET | `/locks` | List available locks |
| GET | `/locks/{device_id}` | Lock status details |
| POST | `/locks/{device_id}/lock` | Request lock action |
| POST | `/locks/{device_id}/unlock` | Request unlock action |
| GET | `/locks/{device_id}/logs` | Recent activity logs |
| GET | `/locks/{device_id}/access_codes` | Programmed access codes + schedules |

> The service wraps `SchlageService` (in `app/schlage_service.py`) and consolidates all direct interactions with the `pyschlage` library.

Development Notes
-----------------

- `app/main.py` instantiates a single `SchlageService` at startup. Verify your credentials before launching; missing credentials raise a helpful HTTP 500 message.
- `SchlageService` serializes logs and codes with JSON-safe payloads to accommodate the dataclasses returned by `pyschlage`.
- Troubleshooting tip: check container logs with `docker logs schlage-api-container` for detailed stack traces.

Continuous Integration
----------------------

GitHub Actions automatically checks Python syntax, builds multi-architecture Docker images, and pushes them to GHCR whenever changes land on `main` (or when tags starting with `v` are created). Pull requests run the same validation steps but skip the push.

Deployment
----------

You can run the container anywhere that supports Docker. To publish the image to the GitHub Container Registry (GHCR):

```
# Authenticate (once per host)
echo "$GITHUB_TOKEN" | docker login ghcr.io -u <github-username> --password-stdin

# Tag and push
docker tag pyschlage-api ghcr.io/<github-username>/pyschlage-api:latest
docker push ghcr.io/<github-username>/pyschlage-api:latest
```

Consumers can then pull with:

```
docker pull ghcr.io/<github-username>/pyschlage-api:latest
```

Contributing
------------

1. Fork & clone the repository.
2. Run `scripts/test_api.py` before submitting PRs.
3. Open issues for feature requests or bugs.

License
-------

This project inherits whatever license you choose to apply. Update this section once a license is selected.

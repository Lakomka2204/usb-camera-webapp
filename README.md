# USB Camera Web Interface

This is a FastAPI web app that streams video from a USB camera (e.g. `/dev/video1`) with login access.

## Features

- Web-based login (session-based)
- Environment-based configuration
- Docker-ready and deployable behind a reverse proxy
- GitHub Actions to build Docker images

## Configuration

Set the following environment variables:

- `ADMIN_USERNAME` – Login username (default: `admin`)
- `ADMIN_PASSWORD` – Login password (default: `admin`)
- `DEVICE_PATH` – Path to USB camera (default: `/dev/video1`)
- `SESSION_SECRET_KEY` – Secret key for session (default: `supersecretkey`)
- `FRAME_WIDTH` – Stream width (default: `640`)
- `FRAME_HEIGHT` – Stream height (default: `480`)
- `PORT` – Server port (default: `8000`)

## Run Locally with Docker

```bash
docker build -t usb-camera-webapp .
docker run -d \\
  -e ADMIN_USERNAME=admin \\
  -e ADMIN_PASSWORD=changeme \\
  -e DEVICE_PATH=/dev/video1 \\
  -e SESSION_SECRET_KEY=somesecret \\
  -p 8000:8000 \\
  --device=/dev/video1 \\
  usb-camera-webapp

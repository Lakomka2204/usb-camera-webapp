from fastapi import FastAPI, Request, Form, Depends, Response, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
from PIL import Image, ImageDraw, ImageFont
import io
import cv2
import os
import uvicorn
from typing import Generator
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Environment variables with warnings if unset
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
DEVICE_PATH = os.getenv("DEVICE_PATH")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "640"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "480"))
PORT = int(os.getenv("PORT", "8000"))

missing_vars = []
if not ADMIN_USERNAME: missing_vars.append("ADMIN_USERNAME")
if not ADMIN_PASSWORD: missing_vars.append("ADMIN_PASSWORD")
if not DEVICE_PATH: missing_vars.append("DEVICE_PATH")
if not SESSION_SECRET_KEY: missing_vars.append("SESSION_SECRET_KEY")
if missing_vars:
    logger.warning(f"Missing required environment variables: {', '.join(missing_vars)}")

app = FastAPI()

# Middleware for logging all HTTP requests
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info(f"Incoming request: {request.method} {request.url.path}")
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response

app.add_middleware(LoggingMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY or "fallbacksecret")

def is_authenticated(request: Request) -> bool:
    return request.session.get("authenticated", False)

def authenticate_user(username: str, password: str) -> bool:
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def gen_frames() -> Generator[bytes, None, None]:
    device = DEVICE_PATH
    logger.info(f"Attempting to open camera device: {device}")
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        logger.error(f"Cannot open camera device: {device}")
        raise RuntimeError(f"Cannot open camera {device}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    while True:
        success, frame = cap.read()
        if not success:
            logger.warning("Failed to read frame from camera")
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    cap.release()
    logger.info("Camera device released")

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/stream")
    return f"""
    <html><body>
    <h2>Login</h2>
    <form method="post" action="/login">
      <input type="text" name="username" placeholder="Username"><br>
      <input type="password" name="password" placeholder="Password"><br>
      <input type="submit" value="Login">
    </form>
    </body></html>
    """

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if authenticate_user(username, password):
        logger.info(f"User '{username}' logged in successfully")
        request.session["authenticated"] = True
        return RedirectResponse(url="/stream", status_code=303)
    logger.warning(f"Failed login attempt with username: {username}")
    return HTMLResponse("Invalid credentials", status_code=401)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    logger.info("User logged out")
    return RedirectResponse(url="/")

@app.get("/stream", response_class=HTMLResponse)
async def stream_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/")
    return f"""
    <html><body>
    <h2>Camera Stream</h2>
    <button id="reload-btn">Reload Stream</button>
    <br><a href="/logout">Logout</a>
    <img src="/video_feed" width="{FRAME_WIDTH}" height="{FRAME_HEIGHT}">
<script>
document.getElementById('reload-btn').addEventListener('click', function () {
    const img = document.querySelector('img');
    if (img) {
        const baseUrl = img.src.split('?')[0];
        const timestamp = Date.now();
        img.src = `${baseUrl}?t=${timestamp}`;
    }
});
</script>
    </body></html>
    """

def generate_error_image(message: str = "Camera error") -> bytes:
    width, height = 640, 480
    image = Image.new("RGB", (width, height), color="black")
    draw = ImageDraw.Draw(image)
    text = f"ERROR:\n{message}"
    draw.text((10, 10), text, fill="red")  # Add a font if you want
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    buf.seek(0)
    return buf

@app.get("/video_feed")
async def video_feed(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/")
    try:
        return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")
    except Exception as e:
        err_img = generate_error_image(str(e))
        return Response(content=err_img.read(), media_type="image/jpeg", status_code=HTTP_500_INTERNAL_SERVER_ERROR)

if __name__ == "__main__":
    logger.info("Starting server...")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)

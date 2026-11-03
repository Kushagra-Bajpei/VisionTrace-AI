"""
Visual Verification Script.
Spawns the VisionTrace API server and Vite preview server with local SQLite DB fallback,
seeds sample CCTV footage, captures browser screenshots using headless Chrome,
and verifies layout integrity.
"""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent.resolve()
ROOT_DIR = BACKEND_DIR.parent
STORAGE_DIR = ROOT_DIR / "storage"
FRONTEND_DIR = ROOT_DIR / "frontend"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DB_PATH = BACKEND_DIR / "dev_visiontrace.db"

# Set local database for visual verification
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

import time
import subprocess
import cv2
import numpy as np


def create_sample_cctv(filename: str, width: int, height: int, duration_sec: int, fps: float = 25.0):
    dest = STORAGE_DIR / "videos" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(dest), fourcc, fps, (width, height))
    total_frames = int(duration_sec * fps)

    for i in range(total_frames):
        # Create dark CCTV surveillance frame with target box and timecode
        frame = np.full((height, width, 3), 28, dtype=np.uint8)
        noise = np.random.randint(0, 15, (height, width, 3), dtype=np.uint8)
        frame = cv2.add(frame, noise)

        timecode = f"CAM-01 [REC] 2026-11-03 14:15:{i // int(fps):02d}:{int(i % fps):02d}"
        cv2.putText(frame, timecode, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 229, 255), 2)
        cv2.rectangle(frame, (width // 3, height // 3), (width // 3 + 140, height // 3 + 280), (0, 255, 128), 2)
        cv2.putText(frame, "PERSON 0.94", (width // 3, height // 3 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 128), 2)

        out.write(frame)

    out.release()

    # Generate thumbnail
    thumb_path = STORAGE_DIR / "thumbnails" / f"thumb_{dest.stem}.jpg"
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(dest))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * 1.0))
    ret, thumb_frame = cap.read()
    if ret:
        cv2.imwrite(str(thumb_path), thumb_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    cap.release()

    return dest


def seed_database():
    """Seed test surveillance videos into local database with Phase 4A lifecycle states."""
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except Exception:
            pass

    sys.path.insert(0, str(BACKEND_DIR))
    from app.core.database import SessionLocal, Base, engine
    from app.models.video import Video
    from app.services.video_service import video_service

    Base.metadata.create_all(engine)
    session = SessionLocal()

    # Clear old visual verify records so fresh Phase 4A telemetry is rendered
    session.query(Video).delete()
    session.commit()

    # Create 2 sample video files
    v1_name = "cctv_lobby_north_entrance.mp4"
    v1_path = create_sample_cctv(v1_name, 1920, 1080, 10, 25.0)

    v2_name = "cctv_perimeter_gate_02.mp4"
    v2_path = create_sample_cctv(v2_name, 1280, 720, 6, 30.0)

    video1 = Video(
        filename=v1_name,
        original_filename="Lobby_North_Entrance_Cam01.mp4",
        file_path=str(v1_path),
        file_size=v1_path.stat().st_size,
        duration=10.0,
        width=1920,
        height=1080,
        fps=25.0,
        status="completed",
        processing_progress=100.0,
        thumbnail_path=f"thumb_{v1_path.stem}.jpg",
        video_metadata={"codec": "h264", "frame_count": 250, "extracted_frames_count": 10},
    )
    video2 = Video(
        filename=v2_name,
        original_filename="Perimeter_Gate_Cam02.mp4",
        file_path=str(v2_path),
        file_size=v2_path.stat().st_size,
        duration=6.0,
        width=1280,
        height=720,
        fps=30.0,
        status="processing",
        processing_progress=45.0,
        thumbnail_path=f"thumb_{v2_path.stem}.jpg",
        video_metadata={"codec": "h264", "frame_count": 180},
    )
    video3 = Video(
        filename=v2_name,
        original_filename="Parking_Structure_West.mp4",
        file_path=str(v2_path),
        file_size=v2_path.stat().st_size,
        duration=6.0,
        width=1280,
        height=720,
        fps=30.0,
        status="uploaded",
        processing_progress=0.0,
        thumbnail_path=f"thumb_{v2_path.stem}.jpg",
        video_metadata={"codec": "h264", "frame_count": 180},
    )
    session.add_all([video1, video2, video3])
    session.commit()

    # Extract sample frames for video1 so the keyframe gallery renders
    video_service.extract_frames(v1_path, str(video1.id), target_fps=1.0)
    print("Database seeded with Phase 4A surveillance videos and extracted keyframes.")
    session.close()


def take_screenshot(url: str, output_png: Path, width: int = 1440, height: int = 900):
    user_data = STORAGE_DIR / "temp_chrome_profile"
    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        f"--user-data-dir={user_data}",
        f"--window-size={width},{height}",
        f"--screenshot={output_png}",
        url,
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    time.sleep(1.5)


def main():
    print("1. Seeding sample surveillance video feeds...")
    seed_database()

    print("2. Starting FastAPI Backend on port 8000...")
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("3. Starting Vite Preview Server on port 5173...")
    frontend_proc = subprocess.Popen(
        ["pnpm", "preview", "--port", "5173"],
        cwd=str(FRONTEND_DIR),
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(6)  # Wait for servers and database connection to be fully ready

    try:
        shot_dashboard = STORAGE_DIR / "visual_dashboard_desktop.png"
        shot_library_desktop = STORAGE_DIR / "visual_library_desktop.png"
        shot_library_mobile = STORAGE_DIR / "visual_library_mobile.png"

        print("4. Capturing Desktop Dashboard (1440x900)...")
        take_screenshot("http://localhost:5173/", shot_dashboard, 1440, 900)

        print("5. Capturing Desktop Video Library (1440x900)...")
        take_screenshot("http://localhost:5173/videos", shot_library_desktop, 1440, 900)

        print("6. Capturing Mobile Video Library (390x844)...")
        take_screenshot("http://localhost:5173/videos", shot_library_mobile, 390, 844)

        print("Screenshots captured:")
        for p in (shot_dashboard, shot_library_desktop, shot_library_mobile):
            if p.exists() and p.stat().st_size > 0:
                print(f"  [OK] {p.name} ({p.stat().st_size} bytes)")
            else:
                print(f"  [FAIL] {p.name} missing")

    finally:
        print("7. Terminating servers...")
        backend_proc.terminate()
        frontend_proc.terminate()


if __name__ == "__main__":
    main()

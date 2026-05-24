import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv
import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials as firebase_credentials
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

load_dotenv(Path(__file__).resolve().parent / ".env")

app = Flask(__name__)
CORS(app)

PAGE_SIZE = 20
DEFAULT_GCP_PROJECT = "lunar-2b4b4"

_db = None
_firebase_initialized = False


def init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
    if raw:
        info = json.loads(raw)
        firebase_admin.initialize_app(firebase_credentials.Certificate(info))
    else:
        firebase_admin.initialize_app()
    _firebase_initialized = True


def get_db():
    global _db
    if _db is None:
        project_id = os.environ.get("GCP_PROJECT", DEFAULT_GCP_PROJECT)
        raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
        if raw:
            info = json.loads(raw)
            _db = firestore.Client.from_service_account_info(
                info, project=project_id
            )
        else:
            # Cloud Run / GCE: use the runtime service account (ADC).
            _db = firestore.Client(project=project_id)
    return _db


def fetch_videos_in_index_range(db, min_idx: int, max_idx: int):
    q = (
        db.collection("videos")
        .where(filter=FieldFilter("index", ">=", min_idx))
        .where(filter=FieldFilter("index", "<=", max_idx))
        .order_by("index")
        .limit(PAGE_SIZE)
    )
    videos = []
    for doc in q.stream():
        data = doc.to_dict() or {}
        videos.append(
            {
                "id": doc.id,
                "index": data.get("index"),
                "media_url": data.get("media_url"),
            }
        )
    return videos


def count_videos(db) -> int:
    result = db.collection("videos").count().get()
    return result[0][0].value


def video_batch_no_auth(db):
    videos = fetch_videos_in_index_range(db, 0, 19)
    return jsonify({"videos": videos, "count": len(videos)})


@app.before_request
def parse_auth_jwt():
    g.authenticated = False
    g.uid = None
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return
    token = auth_header[7:].strip()
    if not token:
        return
    try:
        init_firebase()
        decoded = firebase_auth.verify_id_token(token)
        g.authenticated = True
        g.uid = decoded.get("uid")
    except Exception:
        pass


@app.route("/videos", methods=["GET"])
def get_videos():
    initial = request.args.get("initial", "").lower() == "true"
    last_raw = request.args.get("last_index")
    if last_raw is None or last_raw == "":
        last_index = None
    else:
        try:
            last_index = int(last_raw)
        except ValueError:
            return jsonify({"error": "last_index must be an integer"}), 400

    db = get_db()

    if not g.authenticated:
        return video_batch_no_auth(db)

    if initial:
        total = count_videos(db)
        if total == 0:
            return jsonify({"videos": [], "count": 0})
        start = random.randint(0, max(0, total - 1))
        end = start + PAGE_SIZE - 1
        videos = fetch_videos_in_index_range(db, start, end)
        return jsonify({"videos": videos, "count": len(videos)})

    if last_index is None:
        start, end = 0, PAGE_SIZE - 1
    else:
        start = last_index + 1
        end = last_index + PAGE_SIZE

    videos = fetch_videos_in_index_range(db, start, end)
    if not videos and last_index is not None:
        videos = fetch_videos_in_index_range(db, 0, PAGE_SIZE - 1)

    return jsonify({"videos": videos, "count": len(videos)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5005"))
    app.run(debug=True, host="0.0.0.0", port=port)

source venv/bin/activate

python app.py  

[http://localhost:5000/videos?video_index=0](http://localhost:5000/videos?video_index=0)   

gcloud run deploy lunar-server \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT=lunar-2b4b4
  
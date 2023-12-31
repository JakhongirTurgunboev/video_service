# Video Service
    Video service application written using FastAPI, Celery, Redis, MoviePy, Pydantic, localstack (s3,dynamodb)

# Installation
1. Install or pull the repository to your local environment.
2. Write `docker-compose up --build` in your ternminal

# Usage
Open `http:localhost:8000/docs`, that should open project API endpoints with API documentation.

There are 5 API endpoints: 

/upload/ - send video, it takes some time to upload the video, then returns video_id.

/video/{video_id}/info/ - video_id should be replaced by video_id taken from previous endpoint, There is no need to use quotes (") for video_id. It returns information about video.

/video/{video_id}/original/ - downloading the original video file.

/video/{video_id}/compressed/ - downloading the compressed video file.

/video/{video_id}/delete/ - delete the all information related to video like,
original video, compressed video and video information.
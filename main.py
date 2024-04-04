import os

from fastapi import FastAPI
from threading import Lock
import logging

from starlette.responses import FileResponse

app = FastAPI()
logger = logging.getLogger(__name__)
mpd_cache = {}
seg_cache = {}
mpd_cache_counter = 0
seg_cache_counter = 0
mpd_cache_lock = Lock()
seg_cache_lock = Lock()
mpd_dir = os.getenv("MPD_DIR")
seg_cache_dir = os.getenv("SEG_CACHE_DIR")

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


async def get_video_mpd_from_origin(videoId):
    pass


@app.get("/mpd/{videoId}")
async def get_video_mpd(videoId: str):
    global mpd_cache_counter
    if videoId in mpd_cache:
        logger.info("Acquired mpd cache counter lock")
        mpd_cache_lock.acquire()
        mpd_cache[videoId] = mpd_cache_counter
        mpd_cache_counter += 1
        mpd_cache_lock.release()
        logger.info("Released mpd cache counter lock")
        return FileResponse(mpd_dir + "/" + videoId + ".mpd")
    else:
        await get_video_mpd_from_origin(videoId)
        return get_video_mpd(videoId)

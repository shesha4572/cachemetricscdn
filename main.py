import os
from fastapi import FastAPI, Response
from threading import Lock
import logging
import httpx
import random
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse

app = FastAPI()
logger = logging.getLogger("uvicorn")
mpd_cache = {}
seg_cache = {}
mpd_cache_counter = 0
seg_cache_counter = 0
mpd_cache_lock = Lock()
seg_cache_lock = Lock()
mpd_dir = os.getenv("MPD_DIR")
seg_cache_dir = os.getenv("SEG_CACHE_DIR")
origin_server_base_url = os.getenv("ORIGIN_SERVER_URL")
SEG_CACHE_MAX_COUNT = 128

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
    expose_headers=["X-Segment-Cache-Hit-Flag"]
)


async def request_origin(url):
    client = httpx.AsyncClient()
    res = await client.get(url)
    if res.status_code == 200:
        return res
    return None


def save_mpd(content, video_id):
    logger.info(f"Saving MPD {video_id} to local storage")
    with open(mpd_dir + "/" + video_id + ".mpd", "wb") as file:
        file.write(content)
    logger.info(f"Successfully saved MPD {video_id} to local storage")


def increment_mpd_cache_count(video_id):
    global mpd_cache_counter
    mpd_cache_lock.acquire()
    logger.info("Acquired mpd cache counter lock")
    mpd_cache[video_id] = mpd_cache_counter
    mpd_cache_counter += 1
    mpd_cache_lock.release()
    logger.info("Released mpd cache counter lock")


def increment_seg_cache_count(video_id, bitrate, segment_id, lock=None):
    global seg_cache_counter
    if lock is None:
        seg_cache_lock.acquire()
    logger.info("Acquired segment cache lock")
    seg_cache[(video_id, bitrate, segment_id)] = seg_cache_counter
    seg_cache_counter += 1
    if lock is None:
        seg_cache_lock.release()
    logger.info("Released segment cache lock")


async def get_video_mpd_from_origin(video_id):
    logger.info("Contacting Origin Server for MPD " + video_id)
    res = await request_origin(origin_server_base_url + "/" + video_id + "/manifest.mpd")
    if res is None:
        logger.error("Failed to fetch MPD of video " + video_id)
        raise FileNotFoundError
    logger.info(f"MPD {video_id} fetched successfully from origin server")
    increment_mpd_cache_count(video_id)
    save_mpd(res.content, video_id)
    return res.content


@app.get("/{video_id}/manifest.mpd")
async def get_video_mpd(video_id: str):
    if video_id in mpd_cache:
        logger.info(f"{video_id} MPD cache hit")
        increment_mpd_cache_count(video_id)
        response = FileResponse(mpd_dir + "/" + video_id + ".mpd")
        response.headers["X-Segment-Cache-Hit-Flag"] = "1"
        return response

    else:
        logger.info(f"{video_id} MPD cache miss")
        mpd = await get_video_mpd_from_origin(video_id)
        response = Response(content=mpd, media_type="application/dash+xml")
        response.headers["X-Segment-Cache-Hit-Flag"] = "0"
        return response


def delete_seg(param):
    logger.info(f"Cache evicting segment {param}")
    video_id , bitrate , segment_id = param
    os.remove(seg_cache_dir + "/" + video_id + "_" + bitrate + "_" + segment_id)



def seg_cache_evict():
    first = random.randint(0, SEG_CACHE_MAX_COUNT - 1)
    second = random.randint(0, SEG_CACHE_MAX_COUNT - 1)
    while first == second:
        second = random.randint(0, SEG_CACHE_MAX_COUNT - 1)
    logger.info(f"Random choices for eviction : {first} , {second}")
    keys = list(seg_cache.keys())
    if seg_cache[keys[first]] > seg_cache[keys[second]]:
        delete_seg(keys[second])
        del seg_cache[keys[second]]
    else:
        delete_seg(keys[first])
        del seg_cache[keys[first]]


def save_seg(video_id, bitrate, segment_id, content):
    logger.info(f"Saving segment {video_id, bitrate, segment_id} to local storage")
    with open(seg_cache_dir + "/" + video_id + "_" + bitrate + "_" + segment_id, "wb") as file:
        file.write(content)
    logger.info(f"Successfully saved segment {video_id, bitrate, segment_id} to local storage")


async def get_video_seg_from_origin(video_id, bitrate, segment_id):
    global seg_cache_counter
    logger.info(f"Contacting Origin Server for segment {video_id, bitrate, segment_id}")
    res = await request_origin(origin_server_base_url + "/" + video_id + "/seg/" + bitrate + "/" + segment_id)
    if res is None:
        logger.error("Failed to fetch segment of video " + video_id)
        raise FileNotFoundError
    logger.info(f"Segment {video_id, bitrate, segment_id} fetched successfully from origin server")
    seg_cache_lock.acquire()
    if len(seg_cache) == SEG_CACHE_MAX_COUNT:
        seg_cache_evict()
    increment_seg_cache_count(video_id, bitrate, segment_id, lock=seg_cache_lock)
    seg_cache_lock.release()
    save_seg(video_id, bitrate, segment_id, res.content)
    return res.content


@app.get("/{video_id}/seg/{bitrate}/{segment_id}")
async def get_video_segment(video_id: str, bitrate: str, segment_id: str):
    if (video_id, bitrate, segment_id) in seg_cache:
        logger.info(f"Segment {video_id, bitrate, segment_id} cache hit")
        increment_seg_cache_count(video_id, bitrate, segment_id)
        response = FileResponse(seg_cache_dir + "/" + video_id + "_" + bitrate + "_" + segment_id)
        response.headers["X-Segment-Cache-Hit-Flag"] = "1"
        return response
    else:
        logger.info(f"Segment {video_id, bitrate, segment_id} cache miss")
        seg = await get_video_seg_from_origin(video_id, bitrate, segment_id)
        response = Response(content=seg, media_type="application/octet-stream")
        response.headers["X-Segment-Cache-Hit-Flag"] = "0"
        return response

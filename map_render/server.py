'''
Launcch the map server:
```sh
# Probably more like --workers=4 for production
hypercorn server:app --workers=2 --bind=0.0.0.0:9100
```

Try it out!

```sh
curl -X POST "http://localhost:9100/render-map" -H "Content-Type: application/json" -d @map_render/test_map_obj.json \
  --output /tmp/map.png
```
'''
from io import BytesIO
from typing import Any
import warnings
# import logger

# import fire
# import hypercorn
from fastapi.responses import StreamingResponse
from fastapi import FastAPI, Body, HTTPException, status  #Request
# from fastapi.responses import FileResponse  # , JSONResponse, StreamingResponse
# from contextlib import asynccontextmanager

from map_render import render_map
from dflib.map_struct import deserialize_map


# XXX: May not be needed: remove section after  few beats, if not
# Context manager for the FastAPI app's lifespan: https://fastapi.tiangolo.com/advanced/events/
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     '''Inner bracketing of the FastAPI event loop'''
#     # Startup async code here, in order to share app's correct event loop
#     logger.info('Startup…')
#     yield
#     # Shutdown code here, if any
#     logger.info('Shutdown…')

# app = FastAPI(lifespan=lifespan)

# WORKER_COUNT = 4


def do_render_map(data):
    assert 'tiles' in data
    unknown_keys = {
        k for k in data.keys() if k not in (
            'tiles',
            'highlights',
            'lowlights',
            'highlight_color',
            'lowlight_color'
        )
    }
    if unknown_keys:
        warnings.warn(f'unknown keys used: {unknown_keys}', stacklevel=2)

    map_img = render_map(
        data['tiles'],
        data.get('highlights'),
        data.get('lowlights'),
        data.get('highlight_color'),
        data.get('lowlight_color')
    )

    # Convert the Pillow image to bytes
    img_byte_arr = BytesIO()
    map_img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    return img_byte_arr


app = FastAPI()


@app.post("/unpack-map")
async def unpack_map_(data: bytes):
    '''
    Dev utility to unpack a map struct
    '''
    try:
        map_data = deserialize_map(data)
        return {"status": "success", "map": map_data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/render-map")
async def render_map_(data: bytes):
    try:
        data = deserialize_map(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    img_byte_arr = do_render_map(data)
    return StreamingResponse(img_byte_arr, media_type="image/png")


@app.post('/render-map-json')
async def render_map_json_(data: Any = Body(...)):  # noqa B008
    '''
    Request body is a top-level JSON object with keys:

        "tiles": list[list[dict]],
        "highlights" (optional): list[list]
        "lowlights" (optional): list[list]
        "highlight_color" (optional): str
        "lowlight_color" (optional): str
    '''
    img_byte_arr = do_render_map(data)
    return StreamingResponse(img_byte_arr, media_type="image/png")


@app.get('/health-check', status_code=status.HTTP_200_OK, tags=['healthcheck'])
async def health_check():
    '''Health check for Docker, etc.'''
    # Feel free to test any dependent resources (e.g. working DB connections) here
    return {'status': 'OK'}

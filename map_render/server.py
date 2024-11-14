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
from fastapi import FastAPI, Body, status  #Request
# from fastapi.responses import FileResponse  # , JSONResponse, StreamingResponse
# from contextlib import asynccontextmanager

from map_render import render_map

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


app = FastAPI()


@app.post('/arbitrary-json')
async def receive_arbitrary_json(data: Any = Body(...)):
    return {'received_data': data}


@app.post('/render-map')
async def render_map_http(data: Any = Body(...)):
    '''
    Request body is a top-level JSON object with keys:

        "tiles": list[list[dict]],
        "highlights" (optional): list[list]
        "lowlights" (optional): list[list]
        "highlight_color" (optional): str
        "lowlight_color" (optional): str
    '''
    assert 'tiles' in data
    unknown_keys = set([
        k for k in data.keys() if k not in (
            'tiles',
            'highlights',
            'lowlights',
            'highlight_color',
            'lowlight_color'
        )
    ])
    if unknown_keys:
        warnings.warn(f'unknown keys used: {unknown_keys}')

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

    return StreamingResponse(img_byte_arr, media_type="image/png")


@app.get('/health-check', status_code=status.HTTP_200_OK, tags=['healthcheck'])
async def health_check():
    '''Health check for Docker, etc.'''
    # Feel free to test any dependent resources (e.g. working DB connections) here
    return {'status': 'OK'}

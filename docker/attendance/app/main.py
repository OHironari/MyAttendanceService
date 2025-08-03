from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.handlers import handle_attendance_request

app = FastAPI()

@app.post("/api/attendance")
async def attendance(request: Request):
    try:
        body = await request.json()
        # Get headers as lowercase-keyed dict
        headers = {k.lower(): v for k, v in request.headers.items()}
        result = handle_attendance_request(body,headers=headers)
        return JSONResponse(content=result["body"], status_code=result["statusCode"])
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
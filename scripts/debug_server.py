
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import json


app = FastAPI()
upi_logs_storage = []
)
        return f.read()


# POST endpoint to receive logs for UPI display
@app.post("/api/upi-logs")
async def post_upi_logs(request: Request):
        print("UPI LOG RECEIVED:", data)
        data = await request.json()
        upi_logs_storage.append(data)
        print("UPI LOG ERROR:", str(e))
        return {"status": "error", "detail": str(e)}
    except Exception as e:
def get_upi_logs():
    return JSONResponse(content={"status": "success", "logs": upi_logs_storage})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5173)

import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Cookie, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional

from database.crud import (
    create_conversation as db_create_conversation,
    get_conversations,
    get_messages,
    save_dataset,
    get_datasets,
    get_dataset,
    delete_dataset,
    update_dataset_name,
    link_dataset_to_conversation,
    delete_conversation
)
from graph import build_graph

app = FastAPI(title="AeroAnalyst AI Server")

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure public directory exists
os.makedirs("public", exist_ok=True)

class QueryPayload(BaseModel):
    query: str

class ConversationPayload(BaseModel):
    title: str = "New Analysis"
    dataset_id: Optional[int] = None

class RenameDatasetPayload(BaseModel):
    filename: str

# API Routes

# Authentication Helpers
def get_active_user(session_token: Optional[str] = Cookie(None)):
    from database.db import SessionLocal
    from database.auth_utils import verify_session
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    db = SessionLocal()
    user = verify_session(db, session_token)
    db.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return user

class SignupPayload(BaseModel):
    name: str
    email: str
    password: str

class LoginPayload(BaseModel):
    email: str
    password: str

# Auth Routes
@app.post("/api/auth/signup")
def api_signup(payload: SignupPayload):
    from database.db import SessionLocal
    from database.models import User
    from database.auth_utils import hash_password
    
    db = SessionLocal()
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered")
        
    pwd_hash, salt = hash_password(payload.password)
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=pwd_hash,
        salt=salt
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return {"status": "success", "message": "User created successfully"}

@app.post("/api/auth/login")
def api_login(payload: LoginPayload, response: Response):
    from database.db import SessionLocal
    from database.models import User
    from database.auth_utils import verify_password, create_session
    
    db = SessionLocal()
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        db.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    if not verify_password(payload.password, user.password_hash, user.salt):
        db.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    user_data = {"id": user.id, "name": user.name, "email": user.email}
    token = create_session(db, user.id)
    db.close()
    
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,
        samesite="none",
        secure=True,
        path="/"
    )
    return {"status": "success", "user": user_data}

@app.post("/api/auth/logout")
def api_logout(response: Response, session_token: Optional[str] = Cookie(None)):
    from database.db import SessionLocal
    from database.auth_utils import delete_session
    
    db = SessionLocal()
    delete_session(db, session_token)
    db.close()
    
    response.delete_cookie(
        key="session_token",
        path="/",
        samesite="none",
        secure=True
    )
    return {"status": "success", "message": "Logged out successfully"}

@app.get("/api/auth/status")
def api_auth_status(session_token: Optional[str] = Cookie(None)):
    from database.db import SessionLocal
    from database.auth_utils import verify_session
    
    if not session_token:
        return {"authenticated": False}
        
    db = SessionLocal()
    user = verify_session(db, session_token)
    db.close()
    
    if not user:
        return {"authenticated": False}
        
    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    }

@app.get("/api/datasets")
def api_get_datasets(user = Depends(get_active_user)):
    try:
        return get_datasets(user_id=user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def api_upload_dataset(file: UploadFile = File(...), user = Depends(get_active_user)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    filename = file.filename
    unique_prefix = uuid.uuid4().hex[:8]
    saved_filename = f"{unique_prefix}_{filename}"
    
    from utils.s3_helper import get_s3_client, upload_to_s3
    s3_client = get_s3_client()
    
    if s3_client:
        s3_key = f"uploads/{saved_filename}"
        try:
            upload_to_s3(file.file, s3_key)
            dataset_id = save_dataset(filename=filename, filepath=s3_key, user_id=user.id)
            return {
                "id": dataset_id,
                "filename": filename,
                "filepath": s3_key
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"R2 Upload failed: {str(e)}")
    else:
        filepath = os.path.join("public", saved_filename).replace('\\', '/')
        try:
            with open(filepath, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            dataset_id = save_dataset(filename=filename, filepath=filepath, user_id=user.id)
            return {
                "id": dataset_id,
                "filename": filename,
                "filepath": filepath
            }
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/datasets/{id}")
def api_rename_dataset(id: int, payload: RenameDatasetPayload, user = Depends(get_active_user)):
    try:
        dataset = get_dataset(id, user_id=user.id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        update_dataset_name(id, payload.filename, user_id=user.id)
        return {"status": "success", "message": "Dataset renamed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/datasets/{id}")
def api_delete_dataset(id: int, user = Depends(get_active_user)):
    try:
        filepath = delete_dataset(id, user_id=user.id)
        if filepath:
            from utils.s3_helper import get_s3_client, delete_s3_object
            s3_client = get_s3_client()
            if s3_client and not filepath.startswith("public/"):
                delete_s3_object(filepath)
            else:
                if os.path.exists(filepath):
                    os.remove(filepath)
        return {"status": "success", "message": "Dataset deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/datasets/{id}/download")
def api_download_dataset(id: int, user = Depends(get_active_user)):
    try:
        dataset = get_dataset(id, user_id=user.id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
            
        filepath = dataset["filepath"]
        from utils.s3_helper import get_s3_client, download_from_s3
        s3_client = get_s3_client()
        
        if s3_client and not filepath.startswith("public/"):
            try:
                buffer = download_from_s3(filepath)
                from fastapi.responses import StreamingResponse
                return StreamingResponse(
                    buffer,
                    media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={dataset['filename']}"}
                )
            except Exception as e:
                raise HTTPException(status_code=404, detail=f"Failed to download from R2: {str(e)}")
        else:
            if not os.path.exists(filepath):
                raise HTTPException(status_code=404, detail="Dataset file not found locally")
            return FileResponse(
                path=filepath,
                filename=dataset["filename"],
                media_type="text/csv"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations")
def api_get_conversations(user = Depends(get_active_user)):
    try:
        return get_conversations(user_id=user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/conversations")
def api_create_conversation(payload: ConversationPayload, user = Depends(get_active_user)):
    try:
        if payload.dataset_id is not None:
            dataset = get_dataset(payload.dataset_id, user_id=user.id)
            if not dataset:
                raise HTTPException(status_code=404, detail="Dataset not found")
        conv_id = db_create_conversation(title=payload.title, dataset_id=payload.dataset_id, user_id=user.id)
        if payload.dataset_id is not None:
            link_dataset_to_conversation(conv_id, payload.dataset_id)
        return {"id": conv_id, "title": payload.title, "dataset_id": payload.dataset_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/conversations/{id}")
def api_delete_conversation(id: int, user = Depends(get_active_user)):
    try:
        print(f"Deleting conversation {id} for user {user.id} ({user.email})")
        success = delete_conversation(id, user_id=user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"status": "success", "message": "Conversation deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/conversations/{id}/download")
def api_download_conversation_dataset(id: int, user = Depends(get_active_user)):
    try:
        from database.db import SessionLocal
        from database.models import Conversation
        
        db = SessionLocal()
        conv = db.query(Conversation).filter(Conversation.id == id, Conversation.user_id == user.id).first()
        if not conv:
            db.close()
            raise HTTPException(status_code=404, detail="Conversation not found")
            
        file_path = conv.filepath
        
        from utils.s3_helper import get_s3_client, download_from_s3
        s3_client = get_s3_client()
        
        def file_exists(path):
            if not path:
                return False
            if s3_client and not path.startswith("public/"):
                return True
            return os.path.exists(path)
            
        if not file_exists(file_path):
            if conv.dataset_id:
                dataset = get_dataset(conv.dataset_id, user_id=user.id)
                if dataset and file_exists(dataset["filepath"]):
                    file_path = dataset["filepath"]
                    
        if not file_exists(file_path):
            db.close()
            raise HTTPException(status_code=404, detail="Dataset file not found")
            
        db.close()
        
        filename = os.path.basename(file_path)
        clean_filename = filename
        if filename.startswith("conv_"):
            parts = filename.split("_", 3)
            if len(parts) >= 4:
                clean_filename = parts[3]
            else:
                clean_filename = filename[len("conv_"):]
        elif "/" in file_path and file_path.startswith("mutations/"):
            filename_part = file_path.split("/")[-1]
            parts = filename_part.split("_", 3)
            if len(parts) >= 4:
                clean_filename = parts[3]
            else:
                clean_filename = filename_part
        
        download_name = f"mutated_{clean_filename}"
        
        if s3_client and not file_path.startswith("public/"):
            try:
                buffer = download_from_s3(file_path)
                from fastapi.responses import StreamingResponse
                return StreamingResponse(
                    buffer,
                    media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={download_name}"}
                )
            except Exception as e:
                raise HTTPException(status_code=404, detail=f"Failed to download from R2: {str(e)}")
        else:
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Dataset file not found locally")
            return FileResponse(
                path=file_path,
                filename=download_name,
                media_type="text/csv"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations/{id}/messages")
def api_get_messages(id: int, user = Depends(get_active_user)):
    try:
        from database.db import SessionLocal
        from database.models import Conversation
        db = SessionLocal()
        conv = db.query(Conversation).filter(Conversation.id == id, Conversation.user_id == user.id).first()
        db.close()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return get_messages(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/conversations/{id}/dataset/{dataset_id}")
def api_link_dataset(id: int, dataset_id: int, user = Depends(get_active_user)):
    try:
        from database.db import SessionLocal
        from database.models import Conversation
        db = SessionLocal()
        conv = db.query(Conversation).filter(Conversation.id == id, Conversation.user_id == user.id).first()
        db.close()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
            
        dataset = get_dataset(dataset_id, user_id=user.id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        link_dataset_to_conversation(id, dataset_id)
        return {"status": "success", "message": "Dataset linked to conversation"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/conversations/{id}/upload")
async def api_upload_dataset_for_conv(id: int, file: UploadFile = File(...), user = Depends(get_active_user)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    from database.db import SessionLocal
    from database.models import Conversation
    db = SessionLocal()
    conv = db.query(Conversation).filter(Conversation.id == id, Conversation.user_id == user.id).first()
    db.close()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    filename = file.filename
    unique_prefix = uuid.uuid4().hex[:8]
    saved_filename = f"{unique_prefix}_{filename}"
    
    from utils.s3_helper import get_s3_client, upload_to_s3
    s3_client = get_s3_client()
    
    if s3_client:
        s3_key = f"uploads/{saved_filename}"
        try:
            upload_to_s3(file.file, s3_key)
            dataset_id = save_dataset(filename=filename, filepath=s3_key, user_id=user.id)
            link_dataset_to_conversation(id, dataset_id)
            return {
                "id": dataset_id,
                "filename": filename,
                "filepath": s3_key
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"R2 Upload failed: {str(e)}")
    else:
        filepath = os.path.join("public", saved_filename).replace('\\', '/')
        try:
            with open(filepath, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            dataset_id = save_dataset(filename=filename, filepath=filepath, user_id=user.id)
            link_dataset_to_conversation(id, dataset_id)
            return {
                "id": dataset_id,
                "filename": filename,
                "filepath": filepath
            }
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            raise HTTPException(status_code=500, detail=str(e))

def make_json_serializable(val):
    import numpy as np
    import pandas as pd
    
    if val is None:
        return {
            "type": "scalar",
            "data": "None"
        }
    if isinstance(val, pd.DataFrame):
        return {
            "type": "dataframe",
            "columns": [str(c) for c in val.columns],
            "data": [[make_json_serializable_scalar(cell) for cell in row] for row in val.head(50).values.tolist()],
            "total_rows": len(val)
        }
    elif isinstance(val, pd.Series):
        return {
            "type": "series",
            "index": [str(idx) for idx in val.index],
            "data": [make_json_serializable_scalar(item) for item in val.values.tolist()]
        }
    else:
        # Standard variable/type
        return {
            "type": "scalar",
            "data": str(make_json_serializable_scalar(val))
        }

def make_json_serializable_scalar(val):
    import numpy as np
    import pandas as pd
    import datetime
    
    if val is None:
        return None
        
    # Check for NaN / Inf
    if isinstance(val, float):
        if np.isnan(val) or np.isinf(val):
            return None
            
    if isinstance(val, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(val)
    elif isinstance(val, (np.floating, np.float64, np.float32)):
        if np.isnan(val) or np.isinf(val):
            return None
        return float(val)
    elif isinstance(val, np.ndarray):
        return [make_json_serializable_scalar(x) for x in val.tolist()]
    elif isinstance(val, pd.Timestamp):
        return val.isoformat()
    elif isinstance(val, (datetime.datetime, datetime.date)):
        return val.isoformat()
    elif isinstance(val, dict):
        return {str(k): make_json_serializable_scalar(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple, set)):
        return [make_json_serializable_scalar(x) for x in val]
    return val

@app.get("/api/conversations/{id}/preview")
def api_get_conversation_preview(id: int, user = Depends(get_active_user)):
    try:
        from database.db import SessionLocal
        from database.models import Conversation
        import pandas as pd
        import numpy as np

        db = SessionLocal()
        conv = db.query(Conversation).filter(Conversation.id == id, Conversation.user_id == user.id).first()
        if not conv:
            db.close()
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        file_path = conv.filepath
        
        from utils.s3_helper import get_s3_client, read_dataframe_from_s3
        s3_client = get_s3_client()
        
        def file_exists(path):
            if not path:
                return False
            if s3_client and not path.startswith("public/"):
                return True
            return os.path.exists(path)
            
        if not file_exists(file_path):
            if conv.dataset_id:
                dataset = get_dataset(conv.dataset_id, user_id=user.id)
                if dataset and file_exists(dataset["filepath"]):
                    file_path = dataset["filepath"]
            
        if not file_exists(file_path):
            db.close()
            return {"status": "empty", "message": "No dataset linked or file missing"}
            
        db.close()

        # Load dataframe
        if s3_client and not file_path.startswith("public/"):
            try:
                df = read_dataframe_from_s3(file_path)
            except Exception as e:
                return {"status": "error", "message": f"Failed to load dataset from R2: {str(e)}"}
        else:
            if not os.path.exists(file_path):
                return {"status": "empty", "message": "No dataset linked or file missing"}
            df = pd.read_csv(file_path)
        
        # Limit rows for preview (first 100 rows)
        preview_rows = df.head(100)
        
        # Clean dataframe preview so it has no NaN/Inf elements
        clean_data = []
        for row in preview_rows.values.tolist():
            clean_row = []
            for cell in row:
                clean_row.append(make_json_serializable_scalar(cell))
            clean_data.append(clean_row)

        # Get column names and types
        columns = list(df.columns)
        dtypes = {col: str(df[col].dtype) for col in df.columns}
        
        # Missing values
        missing = {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()}
        
        # Unique values
        nunique = {str(k): int(v) for k, v in df.nunique().to_dict().items()}
        
        # Quick summary stats
        summary = {}
        try:
            desc = df.describe(include='all')
            for col in desc.columns:
                col_stats = desc[col].to_dict()
                summary[str(col)] = {str(k): make_json_serializable_scalar(v) for k, v in col_stats.items()}
        except Exception:
            pass

        return {
            "status": "success",
            "filename": os.path.basename(file_path),
            "shape": list(df.shape),
            "columns": columns,
            "dtypes": dtypes,
            "missing": missing,
            "nunique": nunique,
            "summary": summary,
            "data": clean_data
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/conversations/{id}/query")
def api_run_query(id: int, payload: QueryPayload, user = Depends(get_active_user)):
    try:
        # Get dataset associated with conversation
        db_conversations = get_conversations(user_id=user.id)
        conv = next((c for c in db_conversations if c["id"] == id), None)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Determine the file path (use local conversation file if it exists)
        file_path = conv.get("filepath")
        
        from utils.s3_helper import get_s3_client
        s3_client = get_s3_client()
        
        def file_exists(path):
            if not path:
                return False
            if s3_client and not path.startswith("public/"):
                return True
            return os.path.exists(path)

        if not file_exists(file_path):
            dataset_id = conv["dataset_id"]
            dataset = get_dataset(dataset_id, user_id=user.id)
            if not dataset or not file_exists(dataset["filepath"]):
                raise HTTPException(status_code=400, detail="Associated dataset not found")
            file_path = dataset["filepath"]
        else:
            dataset_id = conv["dataset_id"]
            
        # Build state and invoke LangGraph pipeline
        state = {
            "file_path": file_path,
            "query": payload.query,
            "conversation_id": id,
            "dataset_id": dataset_id
        }
        
        graph = build_graph()
        result_state = graph.invoke(state)
        
        # Check for errors in state execution
        error = result_state.get("error")
        
        # Format response
        result_val = make_json_serializable(result_state.get("result"))
            
        return {
            "result": result_val,
            "insights": result_state.get("insights"),
            "chart_path": result_state.get("chart_path"),
            "error": error
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# Mount public directory for files and static assets
app.mount("/public", StaticFiles(directory="public"), name="public")

# Serve Frontend
@app.get("/")
def serve_landing_page():
    landing_path = os.path.join("public", "landing.html")
    if os.path.exists(landing_path):
        return FileResponse(landing_path)
    return FileResponse(os.path.join("public", "index.html"))

@app.get("/workspace")
def serve_workspace(session_token: Optional[str] = Cookie(None)):
    from database.db import SessionLocal
    from database.auth_utils import verify_session
    from fastapi.responses import RedirectResponse
    
    if not session_token:
        return RedirectResponse(url="/", status_code=303)
        
    db = SessionLocal()
    user = verify_session(db, session_token)
    db.close()
    
    if not user:
        return RedirectResponse(url="/", status_code=303)
        
    workspace_path = os.path.join("public", "index.html")
    if os.path.exists(workspace_path):
        return FileResponse(workspace_path)
    return HTMLResponse("<h2>Frontend index.html not created yet. Please implement frontend assets.</h2>")

import os
import secrets
import traceback
from typing import List

# --- FIX for insecure_transport error ---
# This line is for local development only to allow OAuth over HTTP.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
# -----------------------------------------

from fastapi import FastAPI, Request, HTTPException, Depends, APIRouter
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel
from dotenv import load_dotenv
from googleapiclient.discovery import build


# --- Local Imports ---
from database import init_db, save_or_update_user, get_user_by_email, update_spreadsheet_id, User
from security import create_access_token, get_current_user, encrypt_token
from sheets_api import (
    get_google_credentials, create_spreadsheet, setup_erp_sheets,
    append_row, get_all_rows, update_row, delete_row, SHEET_STRUCTURE
)
from models import *

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]
REDIRECT_URI = "http://127.0.0.1:8000/auth/callback"

# --- FastAPI App ---
app = FastAPI(
    title="School ERP API",
    description="An API to manage school data using Google Sheets as a backend.",
    version="1.0.0"
)

# In-memory storage for the OAuth state token.
# In a distributed system, this should be a shared cache like Redis.
app.state.session_storage = {}

@app.on_event("startup")
def on_startup():
    """Initializes the database when the application starts."""
    init_db()

# --- HELPER FUNCTIONS ---
def get_spreadsheet_id(current_user: User) -> str:
    user_data = get_user_by_email(current_user['email'])
    spreadsheet_id = user_data.get('spreadsheet_id')

    # ✅ Defensive check to catch invalid or corrupted values
    if not spreadsheet_id or not isinstance(spreadsheet_id, str) or len(spreadsheet_id) < 30:
        raise HTTPException(
            status_code=400,
            detail="Invalid spreadsheet ID. Please re-run /api/setup-sheet to initialize your sheet."
        )

    return spreadsheet_id


def map_row_to_model(row: dict, model: BaseModel) -> BaseModel:
    """Converts a dictionary from a sheet row to a Pydantic model instance."""
    # Maps "Column Header" to "column_header"
    mapped_data = {key.lower().replace(' ', '_').replace('/', '_'): value for key, value in row.items()}
    return model(**mapped_data)

def map_model_to_row(model_instance: BaseModel, sheet_name: str) -> list:
    """Converts a Pydantic model instance to a list of values for a sheet row."""
    headers = SHEET_STRUCTURE[sheet_name]
    data_dict = model_instance.model_dump(mode='json') # Use mode='json' to serialize date objects
    # Maps "column_header" back to "Column Header" to get the correct value
    return [str(data_dict.get(header.lower().replace(' ', '_').replace('/', '_'), '')) for header in headers]

# --- AUTHENTICATION ENDPOINTS ---

@app.get("/", tags=["Authentication"])
def read_root(current_user: User = Depends(get_current_user)):
    return {"message": f"Welcome! You are logged in as {current_user['email']}"}

@app.get("/login/google", tags=["Authentication"])
def login_google():
    """Initiates the Google OAuth2 login flow."""
    state = secrets.token_urlsafe(32)
    app.state.session_storage['state'] = state
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    authorization_url, _ = flow.authorization_url(
        access_type='offline', include_granted_scopes='true', prompt='consent', state=state
    )
    return RedirectResponse(authorization_url)

@app.get("/auth/callback", tags=["Authentication"])
def auth_callback(request: Request):
    """
    Callback endpoint for Google OAuth2. Handles the token exchange and user session creation.
    """
    try:
        state_from_google = request.query_params.get('state')
        saved_state = app.state.session_storage.pop('state', None)
        if not saved_state or saved_state != state_from_google:
            raise HTTPException(status_code=400, detail="Invalid state token (CSRF attack suspected).")

        flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
        flow.fetch_token(authorization_response=str(request.url))

        credentials = flow.credentials
        user_info = build('oauth2', 'v2', credentials=credentials).userinfo().get().execute()
        user_email, user_name = user_info.get('email'), user_info.get('name')

        if not user_email or not credentials.refresh_token:
            raise HTTPException(status_code=400, detail="Could not retrieve user info or refresh token.")

        # --- SECURITY FIX: Encrypt the token before saving ---
        encrypted_token = encrypt_token(credentials.refresh_token)
        save_or_update_user(user_email, user_name, encrypted_token)

        access_token = create_access_token(data={"sub": user_email})
        response = RedirectResponse(url="/api/me")
        response.set_cookie(key="access_token", value=access_token, httponly=True, samesite='lax')
        return response
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during auth: {e}")

@app.get("/logout", tags=["Authentication"])
def logout():
    """Logs out the user by deleting the session cookie."""
    response = RedirectResponse(url="/login/google")
    response.delete_cookie("access_token")
    return response

# --- USER & SETUP ENDPOINTS ---

@app.get("/api/me", response_model=User, tags=["User"])
def read_users_me(current_user: User = Depends(get_current_user)):
    """Gets the details of the currently logged-in user."""
    return get_user_by_email(current_user['email'])

@app.post("/api/setup-sheet", tags=["User"])
def setup_sheet(current_user: User = Depends(get_current_user)):
    """Creates and initializes the ERP Google Sheet for the user."""
    user_data = get_user_by_email(current_user['email'])
    if user_data.get('spreadsheet_id'):
        return {"message": "Spreadsheet already set up.", "spreadsheet_id": user_data['spreadsheet_id']}
    try:
        credentials = get_google_credentials(user_data)
        spreadsheet_id = create_spreadsheet(credentials, f"ERP Data - {user_data['email']}")
        update_spreadsheet_id(user_data['email'], spreadsheet_id)
        setup_erp_sheets(credentials, spreadsheet_id)
        return {"message": "Successfully created and set up ERP spreadsheet!", "spreadsheet_id": spreadsheet_id, "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sheet setup failed: {e}")

# --- GENERIC CRUD FACTORY ---
def create_crud_endpoints(router: APIRouter, model: BaseModel, create_model: BaseModel, update_model: BaseModel, sheet_name: str, id_field: str):
    """A factory to create standard CRUD endpoints for a given resource."""
    
    @router.post("", response_model=model)
    def add_record(data: create_model, current_user: User = Depends(get_current_user)):
        spreadsheet_id = get_spreadsheet_id(current_user)
        credentials = get_google_credentials(current_user)
        row_values = map_model_to_row(data, sheet_name)
        append_row(credentials, spreadsheet_id, sheet_name, row_values)
        return data

    @router.get("", response_model=List[model])
    def get_records(current_user: User = Depends(get_current_user)):
        spreadsheet_id = get_spreadsheet_id(current_user)
        credentials = get_google_credentials(current_user)
        rows = get_all_rows(credentials, spreadsheet_id, sheet_name)
        return [map_row_to_model(row, model) for row in rows]

    @router.put("/{item_id}", response_model=model)
    def update_record(item_id: str, data: update_model, current_user: User = Depends(get_current_user)):
        spreadsheet_id = get_spreadsheet_id(current_user)
        credentials = get_google_credentials(current_user)
        rows = get_all_rows(credentials, spreadsheet_id, sheet_name)
        existing_item = next((map_row_to_model(r, model) for r in rows if r.get(id_field) == item_id), None)
        if not existing_item:
            raise HTTPException(status_code=404, detail=f"Record '{item_id}' not found.")
        
        updated_data = data.model_dump(exclude_unset=True)
        updated_item = existing_item.model_copy(update=updated_data)
        new_row_values = map_model_to_row(updated_item, sheet_name)
        update_row(credentials, spreadsheet_id, sheet_name, item_id, id_field, new_row_values)
        return updated_item

    @router.delete("/{item_id}", status_code=204)
    def delete_record(item_id: str, current_user: User = Depends(get_current_user)):
        spreadsheet_id = get_spreadsheet_id(current_user)
        credentials = get_google_credentials(current_user)
        try:
            delete_row(credentials, spreadsheet_id, sheet_name, item_id, id_field)
            return
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

# --- CREATE AND INCLUDE ROUTERS FOR EACH MODULE ---

admissions_router = APIRouter()
create_crud_endpoints(admissions_router, Admission, AdmissionCreate, AdmissionUpdate, "Admissions", "Admission ID")
app.include_router(admissions_router, prefix="/api/admissions", tags=["Admissions"])

library_router = APIRouter()
create_crud_endpoints(library_router, Book, BookCreate, BookUpdate, "Library", "Book ID")
app.include_router(library_router, prefix="/api/library", tags=["Library"])

hostel_router = APIRouter()
create_crud_endpoints(hostel_router, HostelOccupancy, HostelOccupancyCreate, HostelOccupancyUpdate, "Hostel", "Occupancy ID")
app.include_router(hostel_router, prefix="/api/hostel", tags=["Hostel"])

fees_router = APIRouter()
create_crud_endpoints(fees_router, FeeReceipt, FeeReceiptCreate, FeeReceiptUpdate, "Fees", "Receipt ID")
app.include_router(fees_router, prefix="/api/fees", tags=["Fees"])

users_router = APIRouter()
create_crud_endpoints(users_router, AppUser, AppUserCreate, AppUserUpdate, "Users", "User ID")
app.include_router(users_router, prefix="/api/users", tags=["Users"])


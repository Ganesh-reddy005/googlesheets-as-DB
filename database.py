import sqlite3
from pydantic import BaseModel, EmailStr

# --- Pydantic Model for User Data ---
# This defines the structure of the user object that will be used
# throughout the application, especially for API responses.
class User(BaseModel):
    email: EmailStr
    name: str
    spreadsheet_id: str | None = None

# --- Database Connection ---
def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    # The database is a single file named 'erp_users.db'
    conn = sqlite3.connect('erp_users.db')
    # This line is crucial: it allows accessing columns by their names (like a dictionary)
    # instead of by their index, which makes the code much more readable.
    conn.row_factory = sqlite3.Row
    return conn

# --- Database Initialization ---
def init_db():
    """
    Initializes the database. It creates the 'users' table if it doesn't already exist.
    This function is designed to be safely run every time the application starts.
    """
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                encrypted_refresh_token TEXT NOT NULL,
                spreadsheet_id TEXT
            )
        ''')
        conn.commit()

# --- User Data Functions ---
def save_or_update_user(email: str, name: str, encrypted_refresh_token: str):
    """
    Saves a new user or updates an existing user's name and token.
    This function handles the logic for both new and returning users during the
    authentication callback. It does NOT handle the spreadsheet_id.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # First, check if the user already exists in the database.
        cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
        user_exists = cursor.fetchone()

        if user_exists:
            # If the user exists, update their name and refresh token.
            # This is useful if they re-authenticate to refresh their permissions.
            cursor.execute(
                "UPDATE users SET name = ?, encrypted_refresh_token = ? WHERE email = ?",
                (name, encrypted_refresh_token, email)
            )
        else:
            # If the user is new, insert a new record. The spreadsheet_id is
            # intentionally left NULL as it will be set later.
            cursor.execute(
                "INSERT INTO users (email, name, encrypted_refresh_token) VALUES (?, ?, ?)",
                (email, name, encrypted_refresh_token)
            )
        conn.commit()

def update_spreadsheet_id(email: str, spreadsheet_id: str):
    """
    Updates the spreadsheet_id for a given user after the sheet has been created.
    This function is called by the /api/setup-sheet endpoint.
    """
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET spreadsheet_id = ? WHERE email = ?",
            (spreadsheet_id, email)
        )
        conn.commit()

def get_user_by_email(email: str) -> dict | None:
    """
    Retrieves a user's full details from the database by their email.
    Returns the data as a dictionary, or None if the user is not found.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        if user:
            # Convert the sqlite3.Row object to a standard Python dictionary
            return dict(user)
    return None


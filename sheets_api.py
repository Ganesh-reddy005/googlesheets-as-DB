import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from security import decrypt_token

# This structure defines the exact headers for each sheet.
# It's crucial that these match your Pydantic models.
SHEET_STRUCTURE = {
    "Admissions": [
        "Admission ID", "Student Name", "Date of Birth", "Gender", "Contact Number",
        "Email", "Address", "Course Applied", "Department", "Admission Date",
        "Admission Status", "Parent/Guardian Name", "Parent/Guardian Contact",
        "Nationality", "Category", "Remarks"
    ],
    "Library": [
        "Book ID", "Title", "Author", "Genre", "Publisher", "Edition/Year", "ISBN",
        "Shelf Location", "Availability Status", "Issued To", "Issue Date",
        "Return Date", "Fine Rate", "Fine Accrued"
    ],
    "Hostel": [
        "Occupancy ID", "Hostel ID", "Room Type", "Fee Status", "Room Number",
        "Occupied Beds", "Vacant Beds", "Student ID", "Student Name",
        "Check IN Date", "Check Out Date", "Status"
    ],
    "Fees": [
        "Receipt ID", "Student ID", "Student Name", "Course", "Semester/Year",
        "Fee Type", "Amount", "Payment Mode", "Transaction ID", "Payment Date",
        "Status", "Remarks"
    ],
    "Users": [
        "User ID", "Username", "Password", "Role"
    ]
}

CLIENT_SECRETS_FILE = "client_secret.json"

def get_google_credentials(user_data: dict) -> Credentials:
    """
    Creates a Google OAuth2 Credentials object from stored user data.

    Args:
        user_data: A dictionary containing the user's encrypted refresh token.

    Returns:
        A google.oauth2.credentials.Credentials object ready for API calls.
    """
    decrypted_refresh_token = decrypt_token(user_data['encrypted_refresh_token'])
    
    with open(CLIENT_SECRETS_FILE) as f:
        client_secrets = json.load(f)['web']

    return Credentials(
        token=None,
        refresh_token=decrypted_refresh_token,
        token_uri=client_secrets['token_uri'],
        client_id=client_secrets['client_id'],
        client_secret=client_secrets['client_secret'],
        scopes=None
    )

def create_spreadsheet(credentials: Credentials, title: str) -> str:
    """
    Creates a new Google Spreadsheet.

    Args:
        credentials: The user's Google credentials.
        title: The title for the new spreadsheet.

    Returns:
        The ID of the newly created spreadsheet.
    """
    try:
        service = build('sheets', 'v4', credentials=credentials)
        spreadsheet = {'properties': {'title': title}}
        spreadsheet = service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
        return spreadsheet.get('spreadsheetId')
    except HttpError as error:
        print(f"An error occurred creating spreadsheet: {error}")
        raise error

def setup_erp_sheets(credentials: Credentials, spreadsheet_id: str):
    """
    Initializes a spreadsheet with all the required ERP sheets and headers.

    Args:
        credentials: The user's Google credentials.
        spreadsheet_id: The ID of the spreadsheet to set up.
    """
    try:
        service = build('sheets', 'v4', credentials=credentials)
        
        requests = []
        for sheet_name in SHEET_STRUCTURE.keys():
            requests.append({'addSheet': {'properties': {'title': sheet_name}}})
        
        requests.append({'deleteSheet': {'sheetId': 0}})
        
        body = {'requests': requests}
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()

        data_to_write = []
        for sheet_name, headers in SHEET_STRUCTURE.items():
            data_to_write.append({'range': f"'{sheet_name}'!A1", 'values': [headers]})
            
        body = {'valueInputOption': 'USER_ENTERED', 'data': data_to_write}
        service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()

    except HttpError as error:
        print(f"An error occurred during sheet setup: {error}")
        raise error

def append_row(credentials: Credentials, spreadsheet_id: str, sheet_name: str, values: list):
    """
    Appends a new row of data to a specified sheet.

    Args:
        credentials: The user's Google credentials.
        spreadsheet_id: The ID of the spreadsheet.
        sheet_name: The name of the sheet to append to.
        values: A list of values for the new row.
    """
    try:
        service = build('sheets', 'v4', credentials=credentials)
        body = {'values': [values]}
        range_name = f"'{sheet_name}'!A:A"
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
    except HttpError as error:
        raise error

def get_all_rows(credentials: Credentials, spreadsheet_id: str, sheet_name: str) -> list[dict]:
    """
    Retrieves all rows from a specified sheet as a list of dictionaries.

    Args:
        credentials: The user's Google credentials.
        spreadsheet_id: The ID of the spreadsheet.
        sheet_name: The name of the sheet to read from.

    Returns:
        A list of dictionaries, where each dictionary represents a row.
    """
    try:
        service = build('sheets', 'v4', credentials=credentials)
        range_name = f"'{sheet_name}'!A:Z"
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name).execute()
        
        values = result.get('values', [])
        if not values or len(values) < 2:
            return []
            
        headers = values[0]
        records = []
        for row in values[1:]:
            padded_row = row + [''] * (len(headers) - len(row))
            records.append(dict(zip(headers, padded_row)))
        return records
    except HttpError as error:
        raise error

def find_row_index(credentials: Credentials, spreadsheet_id: str, sheet_name: str, search_value: str, search_column_name: str) -> int:
    """
    Finds the 1-based index of a row based on a value in a specific column.

    Args:
        credentials: The user's Google credentials.
        spreadsheet_id: The ID of the spreadsheet.
        sheet_name: The name of the sheet to search in.
        search_value: The value to search for.
        search_column_name: The header of the column to search in.

    Returns:
        The 1-based row index if found.
    
    Raises:
        ValueError: If the record or column is not found.
    """
    try:
        service = build('sheets', 'v4', credentials=credentials)
        range_name = f"'{sheet_name}'!A:Z"
        result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get('values', [])

        if not values:
            raise ValueError(f"Sheet '{sheet_name}' is empty or not found.")

        headers = values[0]
        try:
            col_index = headers.index(search_column_name)
        except ValueError:
            raise ValueError(f"Column '{search_column_name}' not found in sheet '{sheet_name}'.")

        for i, row in enumerate(values):
            if len(row) > col_index and row[col_index] == search_value:
                return i + 1

        raise ValueError(f"Record with {search_column_name} '{search_value}' not found.")
    except HttpError as error:
        raise error

def update_row(credentials: Credentials, spreadsheet_id: str, sheet_name: str, search_value: str, search_column_name: str, new_values: list):
    """
    Updates an entire row in a sheet, identified by a value in a specific column.

    Args:
        credentials: The user's Google credentials.
        spreadsheet_id: The ID of the spreadsheet.
        sheet_name: The name of the sheet.
        search_value: The value to find the row to update.
        search_column_name: The header of the column to search in.
        new_values: A list of the new values for the entire row.
    """
    try:
        row_index = find_row_index(credentials, spreadsheet_id, sheet_name, search_value, search_column_name)
        service = build('sheets', 'v4', credentials=credentials)
        range_name = f"'{sheet_name}'!A{row_index}"
        body = {'values': [new_values]}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
    except (HttpError, ValueError) as error:
        raise error

def delete_row(credentials: Credentials, spreadsheet_id: str, sheet_name: str, search_value: str, search_column_name: str):
    """
    Deletes a row from a sheet, identified by a value in a specific column.

    Args:
        credentials: The user's Google credentials.
        spreadsheet_id: The ID of the spreadsheet.
        sheet_name: The name of the sheet.
        search_value: The value to find the row to delete.
        search_column_name: The header of the column to search in.
    """
    try:
        service = build('sheets', 'v4', credentials=credentials)
        
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = sheet_metadata.get('sheets', [])
        sheet_id = next((s['properties']['sheetId'] for s in sheets if s['properties']['title'] == sheet_name), None)
        
        if sheet_id is None:
            raise ValueError(f"Sheet with name '{sheet_name}' not found.")

        row_index = find_row_index(credentials, spreadsheet_id, sheet_name, search_value, search_column_name)
        
        requests = [{'deleteDimension': {'range': {
            'sheetId': sheet_id,
            'dimension': 'ROWS',
            'startIndex': row_index - 1,
            'endIndex': row_index
        }}}]
        body = {'requests': requests}
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    except (HttpError, ValueError) as error:
        raise error


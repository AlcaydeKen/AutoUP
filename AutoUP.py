import os
import sys
from alive_progress import alive_bar
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime

class colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    END = '\033[0m'

SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/drive.metadata']
PDF_FOLDER_PATH = sys.argv[1]
PROTECTED_PDF_FOLDER_PATH = sys.argv[3]

def authenticate(credentials_file):
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def get_email_address(service):
    try:
        user_info = service.about().get(fields="user").execute()
        return user_info['user']['emailAddress']
    except Exception as e:
        print(colors.RED + f"Error retrieving email address: {e}" + colors.END)
        return "Unknown"

def set_pdf_password(input_path, output_path, password):
    with open(input_path, 'rb') as input_file, open(output_path, 'wb') as output_file:
        reader = PdfReader(input_file)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(password, use_128bit=True)
        writer.write(output_file)

def list_files_in_folder(service, folder_id):
    try:
        response = service.files().list(q=f"'{folder_id}' in parents and trashed=false",
                                        spaces='drive',
                                        fields='files(id, name)').execute()
        files = response.get('files', [])
        return files
    except Exception as e:
        print(colors.RED + f"An error occurred while listing files in folder: {e}" + colors.END)
        return []

def are_files_identical(folder_path, existing_files):
    existing_filenames = [file['name'] for file in existing_files]
    folder_filenames = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    return sorted(existing_filenames) == sorted(folder_filenames)

def create_protected_pdf_folder():
    if not os.path.exists(PROTECTED_PDF_FOLDER_PATH):
        os.makedirs(PROTECTED_PDF_FOLDER_PATH)
        print(colors.GREEN + f"Protected_PDF folder created at: {PROTECTED_PDF_FOLDER_PATH}" + colors.END)

def upload_folder(folder_path, service, credentials_file, log_file):
    try:
        creds = authenticate(credentials_file)
        chosen_folder_name = os.path.basename(folder_path)
        chosen_parent_folder_id = None
        all_uploads_successful = True
        
        patreon_folders = folder_exists(service, "Patreon", "root")
        if patreon_folders:
            chosen_parent_folder_id = patreon_folders[0]['id']
        else:
            folder_metadata = {
                'name': "Patreon",
                'mimeType': 'application/vnd.google-apps.folder'
            }
            patreon_folder = service.files().create(body=folder_metadata, fields='id').execute()
            chosen_parent_folder_id = patreon_folder['id']
            log_message = "Folder 'Patreon' created in Google Drive\n"
            print(colors.GREEN + log_message + colors.END)
            log_file.write(f"{datetime.now()} - {log_message}")
        
        existing_folders = folder_exists(service, chosen_folder_name, chosen_parent_folder_id)
        
        if existing_folders:
            chosen_parent_folder_id = existing_folders[0]['id']
            print(colors.BLUE + f"Folder '{chosen_folder_name}' already exists in Google Drive." + colors.END)
            print()
            
            existing_files = list_files_in_folder(service, chosen_parent_folder_id)
            
            if existing_files:
                if are_files_identical(folder_path, existing_files):
                    print(colors.BLUE + "Files already exist in Google Drive." + colors.END)
                    print()

                    while True:
                        overwrite_choice = input(colors.YELLOW + "Do you want to overwrite them all? (Y/N): " + colors.END).strip().lower()
                        print()

                        if overwrite_choice == 'y':
                            password = input(colors.YELLOW + "Enter password for PDFs: " + colors.END)
                            print()
                            break
                        elif overwrite_choice == 'n':
                            print(colors.YELLOW + "Skipping file upload." + colors.END)
                            print()
                            return
                        else:
                            print(colors.RED + "Invalid input. Please enter 'Y' or 'N'." + colors.END)

                else:
                    print(colors.BLUE + "There are existing and new files being uploaded." + colors.END)
                    print()
                    
                    while True:
                        overwrite_choice = input(colors.YELLOW + "Do you want to overwrite existing files and upload the new ones? (Y/N): " + colors.END).strip().lower()
                        print()

                        if overwrite_choice == 'y':
                            password = input(colors.YELLOW + "Enter password for PDFs: " + colors.END)
                            print()
                            break
                        elif overwrite_choice == 'n':
                            print(colors.YELLOW + "Skipping file upload." + colors.END)
                            print()
                            return
                        else:
                            print(colors.RED + "Invalid input. Please enter 'Y' or 'N'." + colors.END)

            else:
                print(colors.BLUE + "Folder is empty." + colors.END)
                print()
                password = input(colors.YELLOW + "Enter password for PDFs: " + colors.END)
                print()
        else:
            folder_metadata = {
                'name': chosen_folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [chosen_parent_folder_id]
            }
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            chosen_parent_folder_id = folder['id']
            log_message = f"Folder '{chosen_folder_name}' created in Google Drive\n"
            print(colors.GREEN + log_message + colors.END)
            log_file.write(f"{datetime.now()} - {log_message}")
            password = input(colors.YELLOW + "Enter password for PDFs: " + colors.END)
            print()

        files_to_upload = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        total_files = len(files_to_upload)

        with alive_bar(total_files, bar='squares', spinner='waves') as bar:
            for filename in files_to_upload:
                file_path = os.path.join(folder_path, filename)
                protected_file_path = os.path.join(PROTECTED_PDF_FOLDER_PATH, filename)
                set_pdf_password(file_path, protected_file_path, password)

                existing_files = list_files_in_folder(service, chosen_parent_folder_id)
                existing_file_id = None
                for file in existing_files:
                    if file['name'] == filename:
                        existing_file_id = file['id']
                        break

                file_metadata = {
                    'name': filename,
                    'addParents': chosen_parent_folder_id
                }

                with open(protected_file_path, 'rb') as f:
                    media = MediaIoBaseUpload(f, mimetype='application/pdf')
                    try:
                        if existing_file_id:
                            uploaded_file = service.files().update(fileId=existing_file_id, body=file_metadata, media_body=media).execute()
                            log_message = f"Existing: Uploaded: {filename}    Password: {password}    Folder: {chosen_folder_name}\n"
                            print(colors.GREEN + log_message + colors.END)
                            log_file.write(f"{datetime.now()} - {log_message}")
                        else:
                            file_metadata['parents'] = [chosen_parent_folder_id]
                            uploaded_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                            log_message = f"New: Uploaded: {filename}    Password: {password}    Folder: {chosen_folder_name}\n"
                            print(colors.GREEN + log_message + colors.END)
                            log_file.write(f"{datetime.now()} - {log_message}")
                    except Exception as e:
                        print(colors.RED + f"An error occurred while uploading file '{filename}': {e}" + colors.END)
                        log_message = f"Upload Interrupted: {filename}\n"
                        log_file.write(f"{datetime.now()} - {log_message}")
                        all_uploads_successful = False

                permission = {
                    'type': 'anyone',
                    'role': 'reader',
                    'capabilities': {
                        'canDownload': False
                    }
                }
                service.permissions().create(fileId=uploaded_file['id'], body=permission).execute()
                os.remove(protected_file_path)
                bar()

        if all_uploads_successful:
            print()
            print(colors.GREEN + "All Uploads Completed Successfully" + colors.END)
        else:
            print()
            print(colors.RED + "Upload Interrupted" + colors.END)

    except Exception as e:
        print(colors.RED + f"An error occurred: {e}" + colors.END)

def folder_exists(service, folder_name, parent_folder_id):
    try:
        response = service.files().list(q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_folder_id}' in parents and trashed=false",
                                        spaces='drive',
                                        fields='files(id, name)').execute()
        folders = response.get('files', [])
        return folders
    except Exception as e:
        print(colors.RED + f"An error occurred while checking folder existence: {e}" + colors.END)
        return []

def list_folders_in_pdf_folder(pdf_folder_path):
    print(colors.CYAN + "Folders available for upload:" + colors.END)
    folders = [f for f in os.listdir(pdf_folder_path) if os.path.isdir(os.path.join(pdf_folder_path, f))]
    for i, folder in enumerate(folders):
        print(f"{i + 1}. {colors.CYAN}{folder}{colors.END}")
        
    print()
    return folders

def choose_folder(pdf_folder_path, folders):
    while True:
        try:
            folder_choice = int(input(colors.YELLOW + "Choose folder to upload (Enter Number): " + colors.END)) - 1
            print()
            chosen_folder = os.path.join(pdf_folder_path, folders[folder_choice])
            return chosen_folder
        except (ValueError, IndexError):
            print(colors.RED + "Invalid input. Please enter a valid folder number." + colors.END)
            print()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(colors.RED + "Usage: python script.py <folder_path> <credentials_file> <protected_pdf_folder_path>" + colors.END)
        sys.exit(1)
        
    folder_path = sys.argv[1]
    credentials_file = sys.argv[2]
    protected_pdf_folder_path = sys.argv[3]
    
    create_protected_pdf_folder()
    
    with open('logs.txt', 'a') as log_file:
        service = build('drive', 'v3', credentials=authenticate(credentials_file))
        email_address = get_email_address(service)
        log_message = f"Email: {email_address}\n"
        print(colors.CYAN + log_message + colors.END)
        log_file.write(f"{datetime.now()} - {log_message}")
        folders = list_folders_in_pdf_folder(PDF_FOLDER_PATH)
        chosen_folder = choose_folder(PDF_FOLDER_PATH, folders)
        upload_folder(chosen_folder, service, credentials_file, log_file)

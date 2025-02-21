import sys
import json
import hashlib
import os
import logging
import subprocess
from datetime import datetime
from PIL import Image, ImageTk, ImageDraw
import shutil

# Configure logging
logging.basicConfig(filename='icd10_explorer.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_error(error_message, solution):
    error_entry = {
        "error_message": error_message,
        "solution": solution,
        "timestamp": datetime.now().isoformat()
    }
    try:
        with open('error_log.json', 'r') as error_log_file:
            error_log = json.load(error_log_file)
    except FileNotFoundError:
        error_log = {"errors": []}

    error_log["errors"].append(error_entry)

    with open('error_log.json', 'w') as error_log_file:
        json.dump(error_log, error_log_file, indent=4)

try:
    import customtkinter as ctk
    from tkinter import ttk, messagebox, Menu, filedialog
    from PIL import Image, ImageTk
except ImportError as e:
    logging.error(f"ImportError: {e}")
    sys.exit("Error: tkinter is not installed. Please install it using 'pip install tk'.")

try:
    import tkinter
    print("tkinter is installed and accessible.")
except ImportError:
    print("tkinter is not installed.")

# Load configuration
CONFIG_PATH = os.path.expanduser("~/config.json")
BUNDLED_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

if not os.path.exists(CONFIG_PATH):
    try:
        with open(BUNDLED_CONFIG_PATH, 'r') as bundled_config_file:
            bundled_config = json.load(bundled_config_file)
        with open(CONFIG_PATH, 'w') as user_config_file:
            json.dump(bundled_config, user_config_file, indent=4)
        logging.info(f"Copied bundled config.json to {CONFIG_PATH}")
    except Exception as e:
        logging.error(f"Error copying config.json: {e}")
        sys.exit("Error: Could not copy config.json to the user's home directory.")

try:
    with open(CONFIG_PATH, 'r') as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    logging.error("config.json file not found.")
    sys.exit("Error: config.json file not found.")
except json.JSONDecodeError as e:
    logging.error(f"Error decoding config.json: {e}")
    sys.exit("Error: config.json is not properly formatted.")

ICD10_FILE = config["ICD10_FILE"]
USER_DB_FILE = config["USER_DB_FILE"]
SETTINGS_FILE = config["SETTINGS_FILE"]
CPT_FILE = config["CPT_FILE"]
SETTINGS_DIR = os.path.expanduser(config["SETTINGS_DIR"])
DEFAULT_SETTINGS = config["DEFAULT_SETTINGS"]

def ensure_settings_file():
    """Ensure the settings directory and file exist and populate with default settings if needed."""
    os.makedirs(SETTINGS_DIR, exist_ok=True)

    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        logging.info(f"Created default settings file at: {SETTINGS_FILE}")

def load_settings():
    """Load settings from the file."""
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading settings: {e}")
        os.makedirs(SETTINGS_DIR, exist_ok=True)  # Ensure directory exists
        with open(SETTINGS_FILE, "w") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        return DEFAULT_SETTINGS

def save_settings(new_settings):
    """Save updated settings to the file."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(new_settings, f, indent=4)
    logging.info("Settings saved successfully!")

def update_settings(key, value):
    """Update a specific setting."""
    settings = load_settings()
    settings[key] = value
    save_settings(settings)

def load_icd10_codes():
    try:
        with open(ICD10_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError as e:
        logging.error(f"FileNotFoundError: {e}")
        return {}

def save_icd10_codes(codes):
    with open(ICD10_FILE, "w") as file:
        json.dump(codes, file, indent=4)
    logging.info("ICD-10 codes saved successfully!")

def load_user_db():
    try:
        with open(USER_DB_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError as e:
        logging.error(f"FileNotFoundError: {e}")
        return {}

def save_user_db(users):
    with open(USER_DB_FILE, "w") as file:
        json.dump(users, file, indent=4)
    logging.info("User database saved successfully!")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_cpt_codes():
    try:
        with open(CPT_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError as e:
        logging.error(f"FileNotFoundError: {e}")
        return {}

def save_cpt_codes(codes):
    with open(CPT_FILE, "w") as file:
        json.dump(codes, file, indent=4)
    logging.info("CPT codes saved successfully!")

ICD10_CODES = load_icd10_codes()
USER_DB = load_user_db()
CPT_CODES = load_cpt_codes()

EVENT_DOUBLE_CLICK = "<Double-1>"

class ICD10Explorer(ctk.CTk):
    def __init__(self):
        logging.info("Initializing ICD10Explorer.")
        try:
            # Initialize settings
            ensure_settings_file()
            self.settings = load_settings()

            super().__init__()
            self.title(self.settings.get("login_title", "ICD-10 and CPT Codes Reference Guide"))
            self.geometry(f"{self.settings['window_size'][0]}x{self.settings['window_size'][1]}")

            ctk.set_appearance_mode(self.settings.get("theme", "light"))
            ctk.set_default_color_theme("green")

            self.logged_in_user = None  # Add this attribute to store the logged-in user
            self.current_tab = "ICD-10"  # Initialize current_tab attribute

            # Initialize login_image_label
            self.login_image_label = ctk.CTkLabel(self, text="")
            self.login_image_label.grid(row=0, column=0, pady=10, sticky="nw")

            # Initialize clinic_image_label
            self.clinic_image_label = ctk.CTkLabel(self, text="")
            self.clinic_image_label.grid(row=0, column=2, pady=10, sticky="ne")

            # Load the login image
            self.login_photo = None
            self.load_login_image()

            # Menu button
            self.menu_button = ctk.CTkButton(self, text="Menu", command=self.open_menu_window, corner_radius=15, fg_color="#4caf50", text_color="#ffffff")
            self.menu_button.grid(row=0, column=1, pady=10, padx=10, sticky="n")

            # Create main frame
            main_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#f0f0f0")
            main_frame.grid(row=1, column=0, columnspan=3, padx=20, pady=20, sticky="nsew")

            # Label to display the logged-in user in a small box at the bottom
            self.user_label_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#e0e0e0")
            self.user_label_frame.grid(row=2, column=0, columnspan=3, padx=10, pady=10, sticky="se")
            self.user_label = ctk.CTkLabel(self.user_label_frame, text="", font=("Helvetica", 12), text_color="red")
            self.user_label.grid(padx=10, pady=5)

            # Menu frame (initially hidden)
            self.menu_frame = ctk.CTkFrame(main_frame, corner_radius=15, fg_color="#e0e0e0")
            self.menu_frame.grid(row=0, column=0, padx=10, pady=50, sticky="ne")
            self.menu_frame.grid_remove()

            self.test_button_1 = ctk.CTkButton(self.menu_frame, text="Test", command=lambda: print("Test selected"), corner_radius=15, fg_color="#4caf50", text_color="#ffffff")
            self.test_button_2 = ctk.CTkButton(self.menu_frame, text="Test 1", command=lambda: print("Test 1 selected"), corner_radius=15, fg_color="#4caf50", text_color="#ffffff")
            self.test_button_3 = ctk.CTkButton(self.menu_frame, text="Test 2", command=lambda: print("Test 2 selected"), corner_radius=15, fg_color="#4caf50", text_color="#ffffff")
            # Initially hide test buttons
            self.test_buttons = [self.test_button_1, self.test_button_2, self.test_button_3]
            for button in self.test_buttons:
                button.grid_remove()

            # Search bar
            search_frame = ctk.CTkFrame(main_frame, corner_radius=15, fg_color="#e0e0e0")
            search_frame.grid(row=1, column=0, pady=10)

            self.search_entry = ctk.CTkEntry(search_frame, width=400, placeholder_text="🔍 Search Codes", corner_radius=15, fg_color="#ffffff")
            self.search_entry.grid(row=0, column=0, padx=5)

            search_button = ctk.CTkButton(search_frame, text="Search", command=self.search_codes, corner_radius=15, fg_color="#4caf50", text_color="#ffffff")
            search_button.grid(row=0, column=1, padx=5)

            # Buttons to switch between ICD-10 and CPT Codes
            button_frame = ctk.CTkFrame(main_frame, corner_radius=15, fg_color="#e0e0e0")
            button_frame.grid(row=2, column=0, pady=10)

            icd10_button = ctk.CTkButton(button_frame, text="ICD-10 Codes", command=self.show_icd10_codes, corner_radius=15, fg_color="#2196f3", text_color="#ffffff")
            icd10_button.grid(row=0, column=0, padx=5)

            cpt_button = ctk.CTkButton(button_frame, text="CPT Codes", command=self.show_cpt_codes, corner_radius=15, fg_color="#ff9800", text_color="#ffffff")
            cpt_button.grid(row=0, column=1, padx=5)

            add_button = ctk.CTkButton(button_frame, text="Add New", command=self.toggle_add_new_options, corner_radius=15, fg_color="#4caf50", text_color="#ffffff")
            add_button.grid(row=0, column=2, padx=5)

            # Add New options frame (initially hidden)
            self.add_new_frame = ctk.CTkFrame(button_frame, corner_radius=15, fg_color="#e0e0e0")
            self.add_new_frame.grid(row=1, column=0, columnspan=3, pady=5)
            self.add_new_frame.grid_remove()

            self.add_new_code_button = ctk.CTkButton(self.add_new_frame, text="Add New Code", command=self.add_new_code, corner_radius=15, fg_color="#4caf50", text_color="#ffffff")
            self.add_new_code_button.grid(row=0, column=0, pady=5)

            self.add_new_category_button = ctk.CTkButton(self.add_new_frame, text="Add New Category", command=self.create_new_category, corner_radius=15, fg_color="#4caf50", text_color="#ffffff")
            self.add_new_category_button.grid(row=1, column=0, pady=5)

            # Treeview for displaying codes
            self.tree = ttk.Treeview(main_frame, style="Custom.Treeview")
            self.tree.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")

            self.context_menu = Menu(self, tearoff=0, bg="#ffffff", fg="#000000", activebackground="#4caf50", activeforeground="#ffffff")
            self.context_menu.add_command(label="✏️ Edit", command=self.edit_code)
            self.context_menu.add_command(label="❌ Delete", command=self.delete_selected)

            style = ttk.Style()
            style.configure('Custom.Treeview', 
                            font=('Helvetica', 12))
            style.map('Custom.Treeview', 
                      background=[('selected', '#4caf50')],
                      foreground=[('selected', '#ffffff')])

            self.protocol("WM_DELETE_WINDOW", self.on_closing)
            logging.info("ICD10Explorer initialized successfully.")
        except Exception as e:
            error_message = str(e)
            solution = "Check the configuration and ensure all necessary files are present."
            log_error(error_message, solution)
            logging.error(f"Error: {error_message}")
            sys.exit("An error occurred. Please check the error_log.json file for details.")

    def on_closing(self):
        """Handle window close event."""
        logging.info("Application is closing.")
        self.destroy()
        if ctk.get_default_root():
            ctk.get_default_root().quit()  # Terminate mainloop
        sys.exit()

    def open_menu_window(self):
        try:
            menu_window = ctk.CTkToplevel(self)
            menu_window.title("Menu")
            menu_window.geometry("300x200")

            edit_links_button = ctk.CTkButton(menu_window, text="Edit Links", command=self.edit_links)
            edit_links_button.pack(pady=5)

            add_user_button = ctk.CTkButton(menu_window, text="Add User", command=self.add_user)
            add_user_button.pack(pady=5)

            advanced_editor_button = ctk.CTkButton(menu_window, text="Advanced Editor", command=self.open_advanced_editor)
            advanced_editor_button.pack(pady=5)

            run_tests_button = ctk.CTkButton(menu_window, text="Run Tests", command=self.run_tests)
            run_tests_button.pack(pady=5)

            logout_button = ctk.CTkButton(menu_window, text="Log Out", command=self.logout)
            logout_button.pack(pady=5)

            back_button = ctk.CTkButton(menu_window, text="Back", command=lambda: self.back_to_login(menu_window, self))
            back_button.pack(pady=5)
        except Exception as e:
            logging.error(f"Error opening menu window: {e}")

    def logout(self):
        try:
            self.logged_in_user = None  # Clear the logged-in user
            self.withdraw()  # Hide the main window
            self.login()  # Show the login window
        except Exception as e:
            logging.error(f"Error during logout: {e}")

    def edit_links(self):
        try:
            edit_links_window = ctk.CTkToplevel(self)
            edit_links_window.title("Edit Links")
            edit_links_window.geometry("400x300")

            ctk.CTkLabel(edit_links_window, text="Link 1:").grid(row=0, column=0, padx=5, pady=5)
            link1_entry = ctk.CTkEntry(edit_links_window)
            link1_entry.grid(row=0, column=1, padx=5, pady=5)

            ctk.CTkLabel(edit_links_window, text="Link 2:").grid(row=1, column=0, padx=5, pady=5)
            link2_entry = ctk.CTkEntry(edit_links_window)
            link2_entry.grid(row=1, column=1, padx=5, pady=5)

            save_button = ctk.CTkButton(edit_links_window, text="Save", command=lambda: self.save_links(link1_entry.get(), link2_entry.get()))
            save_button.grid(row=2, column=0, columnspan=2, pady=10)

            back_button = ctk.CTkButton(edit_links_window, text="Back", command=edit_links_window.destroy)
            back_button.grid(row=3, column=0, columnspan=2, pady=10)
        except Exception as e:
            logging.error(f"Error editing links: {e}")

    def add_user(self):
        try:
            add_user_window = ctk.CTkToplevel(self)
            add_user_window.title("Add User")
            add_user_window.geometry("400x300")

            ctk.CTkLabel(add_user_window, text="Username:").grid(row=0, column=0, padx=5, pady=5)
            username_entry = ctk.CTkEntry(add_user_window)
            username_entry.grid(row=0, column=1, padx=5, pady=5)

            ctk.CTkLabel(add_user_window, text="First Name:").grid(row=1, column=0, padx=5, pady=5)
            first_name_entry = ctk.CTkEntry(add_user_window)
            first_name_entry.grid(row=1, column=1, padx=5, pady=5)

            ctk.CTkLabel(add_user_window, text="Last Name:").grid(row=2, column=0, padx=5, pady=5)
            last_name_entry = ctk.CTkEntry(add_user_window)
            last_name_entry.grid(row=2, column=1, padx=5, pady=5)

            ctk.CTkLabel(add_user_window, text="Provider Type:").grid(row=3, column=0, padx=5, pady=5)
            provider_type_var = ctk.StringVar(add_user_window)
            provider_type_var.set("MD")  # default value
            provider_type_menu = ctk.CTkComboBox(add_user_window, variable=provider_type_var, values=["MD", "PA", "NP"])
            provider_type_menu.grid(row=3, column=1, padx=5, pady=5)

            ctk.CTkLabel(add_user_window, text="Password:").grid(row=4, column=0, padx=5, pady=5)
            password_entry = ctk.CTkEntry(add_user_window, show="*")
            password_entry.grid(row=4, column=1, padx=5, pady=5)

            def save_user():
                try:
                    username = username_entry.get().strip()
                    first_name = first_name_entry.get().strip()
                    last_name = last_name_entry.get().strip()
                    provider_type = provider_type_var.get().strip()
                    password = password_entry.get().strip()

                    if not username or not first_name or not last_name or not provider_type or not password:
                        messagebox.showerror("Error", "All fields are required!")
                        return

                    if username in USER_DB:
                        messagebox.showerror("Error", "Username already exists!")
                        return

                    USER_DB[username] = {
                        "password": hash_password(password),
                        "first_name": first_name,
                        "last_name": last_name,
                        "provider_type": provider_type
                    }
                    save_user_db(USER_DB)
                    messagebox.showinfo("Success", "User added successfully!")
                    add_user_window.destroy()
                except Exception as e:
                    logging.error(f"Error saving user: {e}")

            save_button = ctk.CTkButton(add_user_window, text="Save", command=save_user)
            save_button.grid(row=5, column=0, columnspan=2, pady=10)

            back_button = ctk.CTkButton(add_user_window, text="Back", command=lambda: self.back_to_login(add_user_window, self))
            back_button.grid(row=6, column=0, columnspan=2, pady=10)
        except Exception as e:
            logging.error(f"Error adding user: {e}")

    def login(self):
        try:
            self.withdraw()  # Hide the main window
            login_window = ctk.CTkToplevel(self)
            login_window.title("Login")
            login_window.geometry("500x650")  # Increased height and width for better layout

            login_frame = ctk.CTkFrame(login_window, corner_radius=15, fg_color="#f5f5f5", width=400, height=500)
            login_frame.place(relx=0.5, rely=0.5, anchor="center")

            self.login_title_label = ctk.CTkLabel(login_frame, text=self.settings["login_title"], font=("Helvetica", 20, "bold"), text_color="#333333")
            self.login_title_label.grid(row=0, column=0, columnspan=2, padx=10, pady=10)

            # Add image box for login logo
            self.login_image_label = ctk.CTkLabel(login_frame, text="")
            self.login_image_label.grid(row=1, column=0, padx=10, pady=10)

            # Add image box for clinic logo
            self.clinic_image_label = ctk.CTkLabel(login_frame, text="")
            self.clinic_image_label.grid(row=1, column=1, padx=10, pady=10)

            # Load the login image
            self.load_login_image()

            ctk.CTkLabel(login_frame, text="Username:", font=("Helvetica", 14), text_color="#333333").grid(row=2, column=0, padx=(10, 0), pady=5, sticky="e")
            username_entry = ctk.CTkEntry(login_frame, font=("Helvetica", 14), corner_radius=15, fg_color="#ffffff", border_color="#cccccc", border_width=2)
            username_entry.grid(row=2, column=1, padx=(0, 10), pady=5, sticky="w")

            ctk.CTkLabel(login_frame, text="Password:", font=("Helvetica", 14), text_color="#333333").grid(row=3, column=0, padx=(10, 0), pady=5, sticky="e")
            password_entry = ctk.CTkEntry(login_frame, show="*", font=("Helvetica", 14), corner_radius=15, fg_color="#ffffff", border_color="#cccccc", border_width=2)
            password_entry.grid(row=3, column=1, padx=(0, 10), pady=5, sticky="w")

            def authenticate(event=None):
                try:
                    username = username_entry.get().strip()
                    password = password_entry.get().strip()

                    if username in USER_DB and USER_DB[username]["password"] == hash_password(password):
                        self.logged_in_user = username  # Store the logged-in user
                        user_info = USER_DB[username]
                        credentials = user_info.get("provider_type", "")
                        self.user_label.configure(text=f"Logged in as: {username} ({credentials})")  # Update the user label
                        self.title(f"ICD-10 and CPT Codes Reference Guide - Logged in as: {username} ({credentials})")  # Update the window title
                        login_window.destroy()
                        self.deiconify()  # Show the main window
                        self.geometry("800x600")  # Resize the main window to fit perfectly
                        self.current_tab = "ICD-10"  # Set the current tab to ICD-10
                        self.show_icd10_codes()  # Populate the tree with ICD-10 codes
                    else:
                        messagebox.showerror("Error", "Invalid username or password!")
                except Exception as e:
                    logging.error(f"Error during authentication: {e}")

            login_button = ctk.CTkButton(login_frame, text="Login", command=authenticate, corner_radius=15, fg_color="#4caf50", text_color="#ffffff", font=("Helvetica", 14), width=220, height=45)
            login_button.grid(row=4, column=0, columnspan=2, pady=5)

            create_account_button = ctk.CTkButton(login_frame, text="Create Account", command=lambda: self.create_account(login_window), corner_radius=15, fg_color="#2196f3", text_color="#ffffff", font=("Helvetica", 14), width=220, height=45)
            create_account_button.grid(row=5, column=0, columnspan=2, pady=5)

            # Admin login button at the corner of the screen
            admin_button = ctk.CTkButton(login_window, text="Admin Login", command=lambda: self.admin_login(login_window), width=140, height=45, corner_radius=15, fg_color="#ff9800", text_color="#ffffff", font=("Helvetica", 12))
            admin_button.place(relx=1.0, rely=0.0, anchor="ne", x=-20, y=20)

            # Add the text at the bottom of the login screen
            footer_label = ctk.CTkLabel(login_window, text="Created by Austin Shinaberry 2025. All rights reserved. Testing phase.", font=("Helvetica", 8), text_color="#333333")
            footer_label.place(relx=0.5, rely=1.0, anchor="s", y=-10)

            # Bind Enter key to the login button
            login_window.bind('<Return>', authenticate)

            login_window.mainloop()
        except Exception as e:
            logging.error(f"Error during login: {e}")

    def import_logo(self, logo_type="login"):
        """Import an image file to be used as the login or clinic logo."""
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif")])
        if file_path:
            user_images_dir = os.path.expanduser("~/icd10_explorer_images")
            os.makedirs(user_images_dir, exist_ok=True)
            dest_path = os.path.join(user_images_dir, os.path.basename(file_path))
            try:
                shutil.copy(file_path, dest_path)
                if logo_type == "login":
                    self.settings["bg_image_path"] = dest_path
                elif logo_type == "clinic":
                    self.settings["clinic_image_path"] = dest_path
                save_settings(self.settings)
                self.load_login_image()
            except Exception as e:
                logging.error(f"Error copying image: {e}")
                messagebox.showerror("Error", "Failed to upload image.")

    def admin_login(self, parent_window):
        try:
            parent_window.withdraw()
            admin_window = ctk.CTk()
            admin_window.title("Admin Login")
            admin_window.geometry("400x400")  # Make the window longer

            admin_frame = ctk.CTkFrame(admin_window, corner_radius=15, fg_color="#e0e0e0")
            admin_frame.place(relx=0.5, rely=0.5, anchor="center")

            ctk.CTkLabel(admin_frame, text="Admin Login", font=("Helvetica", 16)).grid(row=0, column=0, columnspan=2, padx=5, pady=10)

            ctk.CTkLabel(admin_frame, text="Username:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
            admin_username_entry = ctk.CTkEntry(admin_frame)
            admin_username_entry.grid(row=1, column=1, padx=5, pady=5)

            ctk.CTkLabel(admin_frame, text="Password:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
            admin_password_entry = ctk.CTkEntry(admin_frame, show="*")
            admin_password_entry.grid(row=2, column=1, padx=5, pady=5)

            def authenticate_admin(event=None):
                try:
                    username = admin_username_entry.get().strip()
                    password = admin_password_entry.get().strip()

                    # Assuming you have a way to verify admin credentials
                    if username == "1" and password == "1":  # Replace with actual admin credentials check
                        admin_window.destroy()
                        self.open_admin_settings(parent_window)
                    else:
                        messagebox.showerror("Error", "Invalid admin credentials!")
                except Exception as e:
                    logging.error(f"Error during admin authentication: {e}")

            admin_login_button = ctk.CTkButton(admin_frame, text="Login", command=authenticate_admin)
            admin_login_button.grid(row=3, column=0, columnspan=2, pady=10)

            back_button = ctk.CTkButton(admin_frame, text="Back", command=lambda: self.back_to_login(admin_window, parent_window))
            back_button.grid(row=4, column=0, columnspan=2, pady=10)

            # Bind Enter key to the admin login button
            admin_window.bind('<Return>', authenticate_admin)

            admin_window.mainloop()
        except Exception as e:
            logging.error(f"Error during admin login: {e}")

    def open_admin_settings(self, parent_window):
        try:
            settings_window = ctk.CTkToplevel(self)
            settings_window.title("Admin Settings")
            settings_window.geometry("400x400")  # Make the window longer

            ctk.CTkLabel(settings_window, text="Admin Settings", font=("Helvetica", 16)).pack(pady=10)

            ctk.CTkLabel(settings_window, text="Login Title:").pack(pady=5)
            title_entry = ctk.CTkEntry(settings_window)
            title_entry.insert(0, self.settings.get("login_title", ""))
            title_entry.pack(pady=5)

            def save_admin_settings():
                try:
                    new_title = title_entry.get().strip()

                    if new_title:
                        self.settings["login_title"] = new_title
                        self.login_title_label.configure(text=new_title)  # Update the login title label

                    save_settings(self.settings)
                    messagebox.showinfo("Success", "Settings saved successfully!")
                except Exception as e:
                    logging.error(f"Error saving admin settings: {e}")

            save_button = ctk.CTkButton(settings_window, text="Save", command=save_admin_settings)
            save_button.pack(pady=10)

            # Add button to import login logo
            import_image_button = ctk.CTkButton(settings_window, text="Import Logo", command=lambda: self.import_logo("login"))
            import_image_button.pack(pady=10)

            # Add button to import clinic logo
            import_clinic_logo_button = ctk.CTkButton(settings_window, text="Import Clinic Logo", command=lambda: self.import_logo("clinic"))
            import_clinic_logo_button.pack(pady=10)

            back_button = ctk.CTkButton(settings_window, text="Back", command=lambda: self.back_to_login(settings_window, parent_window))
            back_button.pack(pady=10)
        except Exception as e:
            logging.error(f"Error opening admin settings: {e}")

    def update_login_title(self):
        self.login_title_label.configure(text=self.settings["login_title"])

    def back_to_login(self, current_window, previous_window):
        current_window.destroy()
        previous_window.deiconify()

    def create_account(self, parent_window):
        try:
            parent_window.withdraw()
            create_account_window = ctk.CTkToplevel(self)
            create_account_window.title("Create Account")
            create_account_window.geometry("400x400")

            ctk.CTkLabel(create_account_window, text="First Name:").grid(row=0, column=0, padx=5, pady=5)
            first_name_entry = ctk.CTkEntry(create_account_window)
            first_name_entry.grid(row=0, column=1, padx=5, pady=5)

            ctk.CTkLabel(create_account_window, text="Last Name:").grid(row=1, column=0, padx=5, pady=5)
            last_name_entry = ctk.CTkEntry(create_account_window)
            last_name_entry.grid(row=1, column=1, padx=5, pady=5)

            ctk.CTkLabel(create_account_window, text="Provider Type:").grid(row=2, column=0, padx=5, pady=5)
            provider_type_var = ctk.StringVar(create_account_window)
            provider_type_var.set("MD")  # default value
            provider_type_menu = ctk.CTkComboBox(create_account_window, variable=provider_type_var, values=["MD", "PA", "NP"])
            provider_type_menu.grid(row=2, column=1, padx=5, pady=5)

            ctk.CTkLabel(create_account_window, text="Username:").grid(row=3, column=0, padx=5, pady=5)
            username_entry = ctk.CTkEntry(create_account_window)
            username_entry.grid(row=3, column=1, padx=5, pady=5)

            ctk.CTkLabel(create_account_window, text="Password:").grid(row=4, column=0, padx=5, pady=5)
            password_entry = ctk.CTkEntry(create_account_window, show="*")
            password_entry.grid(row=4, column=1, padx=5, pady=5)

            def save_user():
                try:
                    first_name = first_name_entry.get().strip()
                    last_name = last_name_entry.get().strip()
                    provider_type = provider_type_var.get().strip()
                    username = username_entry.get().strip()
                    password = password_entry.get().strip()

                    if not first_name or not last_name or not provider_type or not username or not password:
                        messagebox.showerror("Error", "All fields are required!")
                        return

                    if username in USER_DB:
                        messagebox.showerror("Error", "Username already exists!")
                        return

                    USER_DB[username] = {
                        "password": hash_password(password),
                        "first_name": first_name,
                        "last_name": last_name,
                        "provider_type": provider_type
                    }
                    save_user_db(USER_DB)
                    messagebox.showinfo("Success", "User added successfully!")
                    create_account_window.destroy()
                    parent_window.deiconify()
                except Exception as e:
                    logging.error(f"Error saving user: {e}")

            save_button = ctk.CTkButton(create_account_window, text="Save", command=save_user)
            save_button.grid(row=5, column=0, columnspan=2, pady=10)

            back_button = ctk.CTkButton(create_account_window, text="Back", command=lambda: self.back_to_login(create_account_window, parent_window))
            back_button.grid(row=6, column=0, columnspan=2, pady=10)
        except Exception as e:
            logging.error(f"Error creating account: {e}")

    def toggle_add_new_options(self):
        if self.add_new_frame.winfo_ismapped():
            self.add_new_frame.grid_remove()
        else:
            self.add_new_frame.grid(row=1, column=0, columnspan=3, pady=5)
            if self.current_tab == "CPT":
                self.add_new_code_button.configure(command=self.add_new_cpt_code)
                self.add_new_category_button.configure(command=self.create_new_cpt_category)
            else:
                self.add_new_code_button.configure(command=self.add_new_code)
                self.add_new_category_button.configure(command=self.create_new_category)

    def populate_tree(self, codes):
        self.tree.delete(*self.tree.get_children())  # Clear the tree before populating
        for category, codes in codes.items():
            parent = self.tree.insert('', 'end', text=category, open=False)
            if isinstance(codes, dict):
                for code, description in codes.items():
                    self.tree.insert(parent, 'end', text=f"{code}: {description}")

    def show_icd10_codes(self):
        self.populate_tree(ICD10_CODES)

    def show_cpt_codes(self):
        self.current_tab = "CPT"
        self.tree.delete(*self.tree.get_children())  # Clear the tree before populating
        for category, codes in CPT_CODES.items():
            parent = self.tree.insert('', 'end', text=category, open=False)
            for code_info in codes:
                code = code_info["code"]
                description = code_info["description"]
                self.tree.insert(parent, 'end', text=f"{code}: {description}")

    def search_codes(self):
        query = self.search_entry.get().lower()
        results_window = ctk.CTkToplevel(self)
        results_window.title("Search Results")
        results_window.geometry("600x400")

        results_tree = ttk.Treeview(results_window)
        results_tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        for category, codes in ICD10_CODES.items():
            matching_codes = {code: desc for code, desc in codes.items() if query in code.lower() or query in desc.lower()}
            if matching_codes:
                parent = results_tree.insert('', 'end', text=category, open=True)
                for code, description in matching_codes.items():
                    results_tree.insert(parent, 'end', text=f"{code}: {description}")

        results_tree.bind(EVENT_DOUBLE_CLICK, lambda event: self.display_code_info_from_results(event, results_tree))

    def display_code_info(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        item_text = self.tree.item(selected_item[0], 'text')
        if ":" in item_text:
            code, description = item_text.split(": ", 1)
            details = (
                f"ICD-10 Code: {code}\n"
                f"Description: {description}\n\n"
                "Documentation Tips:\n"
                "- Document diagnosis with specificity.\n"
                "- Include relevant medical history.\n"
                "- Link diagnosis to treatment provided."
            )
            messagebox.showinfo("ICD-10 Code Details", details)

    def display_code_info_from_results(self, event, tree):
        selected_item = tree.selection()
        if not selected_item:
            return
        item_text = tree.item(selected_item[0], 'text')
        if ":" in item_text:
            code, description = item_text.split(": ", 1)
            details = (
                f"ICD-10 Code: {code}\n"
                f"Description: {description}\n\n"
                "Documentation Tips:\n"
                "- Document diagnosis with specificity.\n"
                "- Include relevant medical history.\n"
                "- Link diagnosis to treatment provided."
            )
            messagebox.showinfo("ICD-10 Code Details", details)

    def add_new_code(self):
        add_window = ctk.CTkToplevel(self)
        add_window.title("Add New ICD-10 Code")

        ctk.CTkLabel(add_window, text="Select Category:").grid(row=0, column=0, padx=5, pady=5)
        category_var = ctk.StringVar(add_window)
        category_var.set(list(ICD10_CODES.keys())[0])

        category_menu = ctk.CTkComboBox(add_window, variable=category_var, values=list(ICD10_CODES.keys()))
        category_menu.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(add_window, text="ICD-10 Code:").grid(row=1, column=0, padx=5, pady=5)
        code_entry = ctk.CTkEntry(add_window)
        code_entry.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(add_window, text="Description:").grid(row=2, column=0, padx=5, pady=5)
        desc_entry = ctk.CTkEntry(add_window)
        desc_entry.grid(row=2, column=1, padx=5, pady=5)

        def save_code():
            try:
                category = category_var.get()
                code = code_entry.get().strip()
                description = desc_entry.get().strip()

                if not code or not description:
                    messagebox.showerror("Error", "Code and description cannot be empty!")
                    return  # Ensure the function returns here

                if category in ICD10_CODES:
                    ICD10_CODES[category][code] = description
                    save_icd10_codes(ICD10_CODES)
                    self.populate_tree(ICD10_CODES)
                    messagebox.showinfo("Success", f"Code {code} added to {category}!")
                    add_window.destroy()
                else:
                    messagebox.showerror("Error", "Selected category does not exist!")
            except Exception as e:
                logging.error(f"Error saving new code: {e}")

        save_button = ctk.CTkButton(add_window, text="Save", command=save_code)
        save_button.grid(row=3, column=0, columnspan=2, pady=10)

    def create_new_category(self):
        new_cat_window = ctk.CTkToplevel(self)
        new_cat_window.title("Create New ICD-10 Category")

        ctk.CTkLabel(new_cat_window, text="Category Name:").grid(row=0, column=0, padx=5, pady=5)
        category_entry = ctk.CTkEntry(new_cat_window)
        category_entry.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(new_cat_window, text="ICD-10 Code (optional):").grid(row=1, column=0, padx=5, pady=5)
        code_entry = ctk.CTkEntry(new_cat_window)
        code_entry.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(new_cat_window, text="Description (optional):").grid(row=2, column=0, padx=5, pady=5)
        desc_entry = ctk.CTkEntry(new_cat_window)
        desc_entry.grid(row=2, column=1, padx=5, pady=5)

        def save_category():
            try:
                category = category_entry.get().strip()
                code = code_entry.get().strip()
                description = desc_entry.get().strip()

                if not category:
                    messagebox.showerror("Error", "Category name cannot be empty!")
                    return

                if category not in ICD10_CODES:
                    ICD10_CODES[category] = {}
                    if code and description:
                        ICD10_CODES[category][code] = description
                    save_icd10_codes(ICD10_CODES)
                    self.populate_tree(ICD10_CODES)
                    messagebox.showinfo("Success", f"New category '{category}' created!")
                    new_cat_window.destroy()
                else:
                    messagebox.showerror("Error", "Category already exists!")
            except Exception as e:
                logging.error(f"Error creating new category: {e}")

        save_button = ctk.CTkButton(new_cat_window, text="Create Category", command=save_category)
        save_button.grid(row=3, column=0, columnspan=2, pady=10)

    def create_new_cpt_category(self):
        new_cat_window = ctk.CTkToplevel(self)
        new_cat_window.title("Create New CPT Category")

        ctk.CTkLabel(new_cat_window, text="Category Name:").grid(row=0, column=0, padx=5, pady=5)
        category_entry = ctk.CTkEntry(new_cat_window)
        category_entry.grid(row=0, column=1, padx=5, pady=5)

        def save_category():
            try:
                category = category_entry.get().strip()

                if not category:
                    messagebox.showerror("Error", "Category name cannot be empty!")
                    return

                if category not in CPT_CODES:
                    CPT_CODES[category] = []
                    save_cpt_codes(CPT_CODES)
                    self.populate_tree(CPT_CODES)
                    messagebox.showinfo("Success", f"New category '{category}' created!")
                    new_cat_window.destroy()
                else:
                    messagebox.showerror("Error", "Category already exists!")
            except Exception as e:
                logging.error(f"Error creating new category: {e}")

        save_button = ctk.CTkButton(new_cat_window, text="Create Category", command=save_category)
        save_button.grid(row=1, column=0, columnspan=2, pady=10)

    def show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def edit_code(self):
        try:
            selected_item = self.tree.selection()
            if not selected_item:
                messagebox.showerror("Error", "No code selected to edit!")
                return
            item_text = self.tree.item(selected_item[0], 'text')
            if ":" in item_text:
                code, description = item_text.split(": ", 1)
                self.open_edit_window(code, description)
        except Exception as e:
            logging.error(f"Error editing code: {e}")

    def open_edit_window(self, code, description):
        try:
            edit_window = ctk.CTkToplevel(self)
            edit_window.title("Edit ICD-10 Code")

            ctk.CTkLabel(edit_window, text="ICD-10 Code:").grid(row=0, column=0, padx=5, pady=5)
            code_entry = ctk.CTkEntry(edit_window)
            code_entry.insert(0, code)
            code_entry.grid(row=0, column=1, padx=5, pady=5)

            ctk.CTkLabel(edit_window, text="Description:").grid(row=1, column=0, padx=5, pady=5)
            desc_entry = ctk.CTkEntry(edit_window)
            desc_entry.insert(0, description)
            desc_entry.grid(row=1, column=1, padx=5, pady=5)

            def save_changes():
                try:
                    new_code = code_entry.get().strip()
                    new_description = desc_entry.get().strip()

                    if not new_code or not new_description:
                        messagebox.showerror("Error", "Code and description cannot be empty!")
                        return

                    for category, codes in ICD10_CODES.items():
                        if code in codes:
                            del codes[code]
                            codes[new_code] = new_description
                            save_icd10_codes(ICD10_CODES)
                            self.populate_tree(ICD10_CODES)
                            messagebox.showinfo("Success", f"Code {code} updated to {new_code}!")
                            edit_window.destroy()
                except Exception as e:
                    logging.error(f"Error saving changes: {e}")

            def delete_code():
                try:
                    for category, codes in ICD10_CODES.items():
                        if code in codes:
                            del codes[code]
                            save_icd10_codes(ICD10_CODES)
                            self.populate_tree(ICD10_CODES)
                            messagebox.showinfo("Success", f"Code {code} deleted!")
                            edit_window.destroy()
                            return
                except Exception as e:
                    logging.error(f"Error deleting code: {e}")

            save_button = ctk.CTkButton(edit_window, text="Save", command=save_changes)
            save_button.grid(row=2, column=0, pady=10)

            delete_button = ctk.CTkButton(edit_window, text="Delete", command=delete_code)
            delete_button.grid(row=2, column=1, pady=10)
        except Exception as e:
            logging.error(f"Error opening edit window: {e}")

    def delete_selected(self):
        try:
            selected_item = self.tree.selection()
            if not selected_item:
                messagebox.showerror("Error", "No item selected to delete!")
                return
            item_text = self.tree.item(selected_item[0], 'text')
            if ":" in item_text:
                code, description = item_text.split(": ", 1)
                for category, codes in ICD10_CODES.items():
                    if code in codes:
                        del codes[code]
                        save_icd10_codes(ICD10_CODES)
                        self.populate_tree(ICD10_CODES)
                        messagebox.showinfo("Success", f"Code {code} deleted!")
                        return
            else:
                category = item_text
                if category in ICD10_CODES:
                    del ICD10_CODES[category]
                    save_icd10_codes(ICD10_CODES)
                    self.populate_tree(ICD10_CODES)
                    messagebox.showinfo("Success", f"Category {category} deleted!")
        except Exception as e:
            logging.error(f"Error deleting selected item: {e}")

    def load_login_image(self):
        try:
            print("Loading login image...")
            if self.settings.get("bg_image_path"):
                try:
                    print(f"Attempting to open image: {self.settings['bg_image_path']}")
                    login_image = Image.open(self.settings["bg_image_path"])
                    print("Image opened successfully.")
                except FileNotFoundError:
                    print("File not found error. Using default login image.")
                    login_image = Image.open(os.path.join(os.path.dirname(__file__), 'images', 'login_default.png'))
                except Exception as e:
                    print(f"Failed to load image: {e}. Using default login image.")
                    login_image = Image.open(os.path.join(os.path.dirname(__file__), 'images', 'login_default.png'))
            else:
                print("No background image path set. Using default login image.")
                login_image = Image.open(os.path.join(os.path.dirname(__file__), 'images', 'login_default.png'))

            login_image = login_image.resize((150, 150), Image.LANCZOS)  # Resize the image to 150x150
            print("Image resized successfully.")
            self.login_photo = ImageTk.PhotoImage(login_image)  # Use PhotoImage instead of CTkImage
            print("PhotoImage created successfully.")
            
            # Display the image inside the label
            self.login_image_label.configure(image=self.login_photo)
            self.login_image_label.image = self.login_photo  # Keep a reference to the image
            
            print("Login image label configured successfully.")
            
            print("Loading clinic image...")
            if self.settings.get("clinic_image_path"):
                try:
                    print(f"Attempting to open image: {self.settings['clinic_image_path']}")
                    clinic_image = Image.open(self.settings["clinic_image_path"])
                    print("Image opened successfully.")
                except FileNotFoundError:
                    print("File not found error. Using default clinic image.")
                    clinic_image = Image.open(os.path.join(os.path.dirname(__file__), 'images', 'clinic_default.png'))
                except Exception as e:
                    print(f"Failed to load image: {e}. Using default clinic image.")
                    clinic_image = Image.open(os.path.join(os.path.dirname(__file__), 'images', 'clinic_default.png'))
            else:
                print("No clinic image path set. Using default clinic image.")
                clinic_image = Image.open(os.path.join(os.path.dirname(__file__), 'images', 'clinic_default.png'))

            clinic_image = clinic_image.resize((150, 150), Image.LANCZOS)  # Resize the image to 150x150
            print("Image resized successfully.")
            self.clinic_photo = ImageTk.PhotoImage(clinic_image)  # Use PhotoImage instead of CTkImage
            print("PhotoImage created successfully.")
            
            # Display the image inside the label
            self.clinic_image_label.configure(image=self.clinic_photo)
            self.clinic_image_label.image = self.clinic_photo  # Keep a reference to the image
            
            print("Clinic image label configured successfully.")
        except Exception as e:
            logging.error(f"Error loading login image: {e}")

    def open_advanced_editor(self):
        try:
            editor_window = ctk.CTkToplevel(self)
            editor_window.title("Advanced Editor")
            editor_window.geometry("800x600")

            # Create a notebook (tabbed interface)
            notebook = ttk.Notebook(editor_window)
            notebook.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

            # ICD-10 Codes Tab
            icd10_frame = ctk.CTkFrame(notebook)
            notebook.add(icd10_frame, text="ICD-10 Codes")

            icd10_tree = ttk.Treeview(icd10_frame, columns=("Code", "Description"), show="headings")
            icd10_tree.heading("Code", text="Code")
            icd10_tree.heading("Description", text="Description")
            icd10_tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

            for category, codes in ICD10_CODES.items():
                for code, description in codes.items():
                    icd10_tree.insert("", "end", values=(code, description))

            def add_icd10_code():
                add_window = ctk.CTkToplevel(editor_window)
                add_window.title("Add ICD-10 Code")

                ctk.CTkLabel(add_window, text="Category:").grid(row=0, column=0, padx=5, pady=5)
                category_var = ctk.StringVar(add_window)
                category_var.set(list(ICD10_CODES.keys())[0])
                category_menu = ctk.CTkComboBox(add_window, variable=category_var, values=list(ICD10_CODES.keys()))
                category_menu.grid(row=0, column=1, padx=5, pady=5)

                ctk.CTkLabel(add_window, text="Code:").grid(row=1, column=0, padx=5, pady=5)
                code_entry = ctk.CTkEntry(add_window)
                code_entry.grid(row=1, column=1, padx=5, pady=5)

                ctk.CTkLabel(add_window, text="Description:").grid(row=2, column=0, padx=5, pady=5)
                desc_entry = ctk.CTkEntry(add_window)
                desc_entry.grid(row=2, column=1, padx=5, pady=5)

                def save_code():
                    try:
                        category = category_var.get()
                        code = code_entry.get().strip()
                        description = desc_entry.get().strip()

                        if not code or not description:
                            messagebox.showerror("Error", "Code and description cannot be empty!")
                            return  # Ensure the function returns here

                        if category in ICD10_CODES:
                            ICD10_CODES[category][code] = description
                            save_icd10_codes(ICD10_CODES)
                            icd10_tree.insert("", "end", values=(code, description))
                            messagebox.showinfo("Success", f"Code {code} added to {category}!")
                            add_window.destroy()
                        else:
                            messagebox.showerror("Error", "Selected category does not exist!")
                    except Exception as e:
                        logging.error(f"Error saving new ICD-10 code: {e}")

                save_button = ctk.CTkButton(add_window, text="Save", command=save_code)
                save_button.grid(row=3, column=0, columnspan=2, pady=10)

            add_code_button = ctk.CTkButton(icd10_frame, text="Add Code", command=add_icd10_code)
            add_code_button.grid(row=1, column=0, pady=10)

            # CPT Codes Tab
            cpt_frame = ctk.CTkFrame(notebook)
            notebook.add(cpt_frame, text="CPT Codes")

            cpt_tree = ttk.Treeview(cpt_frame, columns=("Category", "Code", "Description"), show="headings")
            cpt_tree.heading("Category", text="Category")
            cpt_tree.heading("Code", text="Code")
            cpt_tree.heading("Description", text="Description")
            cpt_tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

            for category, codes in CPT_CODES.items():
                for code_info in codes:
                    code = code_info["code"]
                    description = code_info["description"]
                    cpt_tree.insert("", "end", values=(category, code, description))

            def add_cpt_code():
                add_window = ctk.CTkToplevel(editor_window)
                add_window.title("Add CPT Code")

                ctk.CTkLabel(add_window, text="Category:").grid(row=0, column=0, padx=5, pady=5)
                category_var = ctk.StringVar(add_window)
                category_var.set(list(CPT_CODES.keys())[0])
                category_menu = ctk.CTkComboBox(add_window, variable=category_var, values=list(CPT_CODES.keys()))
                category_menu.grid(row=0, column=1, padx=5, pady=5)

                ctk.CTkLabel(add_window, text="Code:").grid(row=1, column=0, padx=5, pady=5)
                code_entry = ctk.CTkEntry(add_window)
                code_entry.grid(row=1, column=1, padx=5, pady=5)

                ctk.CTkLabel(add_window, text="Description:").grid(row=2, column=0, padx=5, pady=5)
                desc_entry = ctk.CTkEntry(add_window)
                desc_entry.grid(row=2, column=1, padx=5, pady=5)

                def save_code():
                    try:
                        category = category_var.get()
                        code = code_entry.get().strip()
                        description = desc_entry.get().strip()

                        if not code or not description:
                            messagebox.showerror("Error", "Code and description cannot be empty!")
                            return  # Ensure the function returns here

                        if category in CPT_CODES:
                            CPT_CODES[category].append({"code": code, "description": description})
                            save_cpt_codes(CPT_CODES)
                            cpt_tree.insert("", "end", values=(category, code, description))
                            messagebox.showinfo("Success", f"Code {code} added to {category}!")
                            add_window.destroy()
                        else:
                            messagebox.showerror("Error", "Selected category does not exist!")
                    except Exception as e:
                        logging.error(f"Error saving new CPT code: {e}")

                save_button = ctk.CTkButton(add_window, text="Save", command=save_code)
                save_button.grid(row=3, column=0, columnspan=2, pady=10)

            add_code_button = ctk.CTkButton(cpt_frame, text="Add Code", command=add_cpt_code)
            add_code_button.grid(row=1, column=0, pady=10)

            # User Database Tab
            user_db_frame = ctk.CTkFrame(notebook)
            notebook.add(user_db_frame, text="User Database")

            user_tree = ttk.Treeview(user_db_frame, columns=("Username", "First Name", "Last Name", "Provider Type"), show="headings")
            user_tree.heading("Username", text="Username")
            user_tree.heading("First Name", text="First Name")
            user_tree.heading("Last Name", text="Last Name")
            user_tree.heading("Provider Type", text="Provider Type")
            user_tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

            for username, user_info in USER_DB.items():
                if isinstance(user_info, dict):
                    user_tree.insert("", "end", values=(username, user_info["first_name"], user_info["last_name"], user_info["provider_type"]))

            def add_user():
                add_user_window = ctk.CTkToplevel(editor_window)
                add_user_window.title("Add User")

                ctk.CTkLabel(add_user_window, text="Username:").grid(row=0, column=0, padx=5, pady=5)
                username_entry = ctk.CTkEntry(add_user_window)
                username_entry.grid(row=0, column=1, padx=5, pady=5)

                ctk.CTkLabel(add_user_window, text="First Name:").grid(row=1, column=0, padx=5, pady=5)
                first_name_entry = ctk.CTkEntry(add_user_window)
                first_name_entry.grid(row=1, column=1, padx=5, pady=5)

                ctk.CTkLabel(add_user_window, text="Last Name:").grid(row=2, column=0, padx=5, pady=5)
                last_name_entry = ctk.CTkEntry(add_user_window)
                last_name_entry.grid(row=2, column=1, padx=5, pady=5)

                ctk.CTkLabel(add_user_window, text="Provider Type:").grid(row=3, column=0, padx=5, pady=5)
                provider_type_var = ctk.StringVar(add_user_window)
                provider_type_var.set("MD")  # default value
                provider_type_menu = ctk.CTkComboBox(add_user_window, variable=provider_type_var, values=["MD", "PA", "NP"])
                provider_type_menu.grid(row=3, column=1, padx=5, pady=5)

                ctk.CTkLabel(add_user_window, text="Password:").grid(row=4, column=0, padx=5, pady=5)
                password_entry = ctk.CTkEntry(add_user_window, show="*")
                password_entry.grid(row=4, column=1, padx=5, pady=5)

                def save_user():
                    try:
                        username = username_entry.get().strip()
                        first_name = first_name_entry.get().strip()
                        last_name = last_name_entry.get().strip()
                        provider_type = provider_type_var.get().strip()
                        password = password_entry.get().strip()

                        if not username or not first_name or not last_name or not provider_type or not password:
                            messagebox.showerror("Error", "All fields are required!")
                            return

                        if username in USER_DB:
                            messagebox.showerror("Error", "Username already exists!")
                            return

                        USER_DB[username] = {
                            "password": hash_password(password),
                            "first_name": first_name,
                            "last_name": last_name,
                            "provider_type": provider_type
                        }
                        save_user_db(USER_DB)
                        user_tree.insert("", "end", values=(username, first_name, last_name, provider_type))
                        messagebox.showinfo("Success", "User added successfully!")
                        add_user_window.destroy()
                    except Exception as e:
                        logging.error(f"Error saving new user: {e}")

                save_button = ctk.CTkButton(add_user_window, text="Save", command=save_user)
                save_button.grid(row=5, column=0, columnspan=2, pady=10)

            add_user_button = ctk.CTkButton(user_db_frame, text="Add User", command=add_user)
            add_user_button.grid(row=1, column=0, pady=10)
        except Exception as e:
            logging.error(f"Error opening advanced editor: {e}")

    def run_tests(self):
        try:
            result = subprocess.run(['python', '-m', 'unittest', 'discover', 'tests'], capture_output=True, text=True)
            test_results_window = ctk.CTkToplevel(self)
            test_results_window.title("Test Results")
            test_results_window.geometry("600x400")

            results_text = ctk.CTkTextbox(test_results_window)
            results_text.insert("1.0", result.stdout)
            results_text.insert("end", result.stderr)
            results_text.configure(state="disabled")
            results_text.pack(expand=True, fill="both")

            close_button = ctk.CTkButton(test_results_window, text="Close", command=test_results_window.destroy)
            close_button.pack(pady=10)
        except Exception as e:
            logging.error(f"Error running tests: {e}")

    def add_new_icd10_code(self):
        add_window = ctk.CTkToplevel(self)
        add_window.title("Add New ICD-10 Code")

        ctk.CTkLabel(add_window, text="Select Category:").grid(row=0, column=0, padx=5, pady=5)
        category_var = ctk.StringVar(add_window)
        category_var.set(list(ICD10_CODES.keys())[0])

        category_menu = ctk.CTkComboBox(add_window, variable=category_var, values=list(ICD10_CODES.keys()))
        category_menu.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(add_window, text="ICD-10 Code:").grid(row=1, column=0, padx=5, pady=5)
        code_entry = ctk.CTkEntry(add_window)
        code_entry.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(add_window, text="Description:").grid(row=2, column=0, padx=5, pady=5)
        desc_entry = ctk.CTkEntry(add_window)
        desc_entry.grid(row=2, column=1, padx=5, pady=5)

        def save_code():
            try:
                category = category_var.get()
                code = code_entry.get().strip()
                description = desc_entry.get().strip()

                if not code or not description:
                    messagebox.showerror("Error", "Code and description cannot be empty!")
                    return  # Ensure the function returns here

                if category in ICD10_CODES:
                    ICD10_CODES[category][code] = description
                    save_icd10_codes(ICD10_CODES)
                    self.populate_tree(ICD10_CODES)
                    messagebox.showinfo("Success", f"Code {code} added to {category}!")
                    add_window.destroy()
                else:
                    messagebox.showerror("Error", "Selected category does not exist!")
            except Exception as e:
                logging.error(f"Error saving new code: {e}")

        save_button = ctk.CTkButton(add_window, text="Save", command=save_code)
        save_button.grid(row=3, column=0, columnspan=2, pady=10)

    def add_new_cpt_code(self):
        add_window = ctk.CTkToplevel(self)
        add_window.title("Add New CPT Code")

        ctk.CTkLabel(add_window, text="Select Category:").grid(row=0, column=0, padx=5, pady=5)
        category_var = ctk.StringVar(add_window)
        category_var.set(list(CPT_CODES.keys())[0])

        category_menu = ctk.CTkComboBox(add_window, variable=category_var, values=list(CPT_CODES.keys()))
        category_menu.grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(add_window, text="CPT Code:").grid(row=1, column=0, padx=5, pady=5)
        code_entry = ctk.CTkEntry(add_window)
        code_entry.grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(add_window, text="Description:").grid(row=2, column=0, padx=5, pady=5)
        desc_entry = ctk.CTkEntry(add_window)
        desc_entry.grid(row=2, column=1, padx=5, pady=5)

        def save_code():
            try:
                category = category_var.get()
                code = code_entry.get().strip()
                description = desc_entry.get().strip()

                if not code or not description:
                    messagebox.showerror("Error", "Code and description cannot be empty!")
                    return  # Ensure the function returns here

                if category in CPT_CODES:
                    CPT_CODES[category].append({"code": code, "description": description})
                    save_cpt_codes(CPT_CODES)
                    self.populate_tree(CPT_CODES)
                    messagebox.showinfo("Success", f"Code {code} added to {category}!")
                    add_window.destroy()
                else:
                    messagebox.showerror("Error", "Selected category does not exist!")
            except Exception as e:
                logging.error(f"Error saving new CPT code: {e}")

        save_button = ctk.CTkButton(add_window, text="Save", command=save_code)
        save_button.grid(row=3, column=0, columnspan=2, pady=10)

if __name__ == "__main__":
    app = ICD10Explorer()
    app.login()  # Prompt for login before showing the main window
    app.mainloop()

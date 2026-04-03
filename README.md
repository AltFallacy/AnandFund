# Anandvan Cost and Donation Management System

A full-stack web application built for the Anandvan non-profit organization to manage cost budgets and process donations effectively. Based on a lightweight Flask backend and SQLite database.

## Features Included

- **Roles System:**
  - **Admin**: Complete overview, handles projects and budgets. Access to comprehensive CSV exports.
  - **Staff**: Manages project expenses internally.
  - **Donor**: Makes donations, views active causes, tracks personal donation history.
- **Robust Budgeting:** Create projects, allocate budgets, track expenses vs allocations in real-time.
- **Clean Responsive UI:** Minimal CSS adapted from the provided landing design, with dynamic templates for the dashboard portals.
- **Dynamic Charts**: Interactive breakdown of overall financials via Chart.js on the dashboard.
- **Reports Export**: Generates and downloads financial reports securely.

## Getting Started Locally

1. Make sure Python 3 is installed.
2. Ensure you have activated your environment if using one (not strictly required if packages installed globally).
3. Open a terminal or Command Prompt in this folder.
4. If you have not done so, install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the application:
   - On Windows: Double-click `run.bat` or run `python app.py`

6. The app will be available at `http://127.0.0.1:5000`

### Default Login
An initial administrator account is automatically generated for you:
- **Username:** admin
- **Password:** admin123 

You can use the Register page (found on the main website login corner) to create new `Donor` or `Staff` accounts and explore all portals.

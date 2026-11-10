Smart Mess Management System

Indian Institute of Information Technology, Bhubaneswar

A web-based Smart Mess Management System designed to digitise and simplify daily mess operations, including student management, meal booking, billing, attendance, complaints and announcements.

Live Demo: https://mess-management-p4mo.onrender.com

---

1. Project Overview

The Smart Mess Management System is a full-stack web application developed to modernise traditional college mess management.

Traditional mess operations often depend on manual registers and paperwork for managing meal bookings, attendance, student information, payments and complaints.

This application provides a centralised digital platform that connects students, administrators and mess staff.

The system aims to improve operational efficiency, reduce manual work, maintain organised records and provide a better experience for students.

2. Project Objectives

- Digitise traditional mess management activities.
- Provide an online student registration and login system.
- Allow students to view weekly food menus.
- Enable students to book and cancel meals.
- Maintain meal booking and attendance records.
- Calculate monthly mess bills.
- Maintain payment records.
- Provide complaint and feedback management.
- Display important mess announcements.
- Provide QR-based student identification for meal attendance.
- Support centralised mess administration.

3. Technology Stack

Technology| Purpose
React.js| Frontend development
Vite| Frontend build tool
JavaScript| Application functionality
Tailwind CSS| UI styling
Python| Backend programming
Django| Backend framework
Django REST Framework| REST API development
SQLite / Configured Database| Data storage
Git & GitHub| Version control
Render| Cloud deployment

Note: The project contains a local SQLite database file ("db.sqlite3"). The actual production database depends on the deployed Django configuration.

4. Main Features and Modules

4.1 Student Registration and Authentication

- Student registration.
- Secure login interface.
- Student-specific portal.
- Personal account information.

4.2 Student Dashboard

The dashboard provides an overview of student mess activities.

It includes:

- Total meals booked.
- Meals attended.
- Current monthly bill.
- Pending dues.
- Open complaints.
- Upcoming meal bookings.
- Meal statistics.

4.3 Weekly Menu Management

Students can view the weekly mess menu.

Meal categories include:

- Breakfast.
- Lunch.
- Snacks.
- Dinner.

The menu displays food items, meal prices and booking deadlines.

4.4 Meal Booking Management

- Book available meals.
- View booking confirmations.
- Maintain booking history.
- Cancel meals before the applicable deadline.
- View booking status.

4.5 Bills and Payments

- Monthly mess bill calculation.
- Fixed monthly mess charges.
- Additional meal-based charges.
- Payment history.
- Pending dues information.
- Cancelled meal exclusion from billing.

4.6 Complaints and Feedback

Students can submit complaints related to:

- Food quality.
- Hygiene.
- Mess services.
- Other operational issues.

The system provides:

- Complaint categories.
- Complaint descriptions.
- Feedback ratings.
- Unique complaint ticket numbers.
- Complaint status tracking.

4.7 Announcements

The announcement module displays important notices, such as:

- Special meal announcements.
- Payment reminders.
- Menu updates.
- Important mess notifications.

4.8 Student Profile and QR Code

Students can view their personal information, including:

- Name.
- Roll number.
- Email address.
- Phone number.
- Branch.
- Academic year.
- Hostel.
- Room number.

The profile also provides a student-specific QR code intended for meal identification and attendance workflows.

5. User Roles

The application provides separate portal entry points for:

Student

- Access student dashboard.
- View menus.
- Book meals.
- View bills.
- Submit complaints.
- View announcements.
- Access profile information.

Administrator

- Administrative access to manage mess operations, subject to implemented permissions and modules.

Mess Staff

- Staff portal access for mess-related operational activities, subject to implemented permissions and modules.

6. Project Architecture

The application follows a frontend-backend architecture.

Frontend

React.js is responsible for:

- User interface.
- Navigation.
- Forms.
- Dashboard components.
- User interactions.
- API communication.

Backend

Django and Django REST Framework handle:

- Application business logic.
- API endpoints.
- Data validation.
- Authentication and permissions.
- Database operations.
- Request and response processing.

Database

The database maintains structured information related to students, bookings, menus, billing, complaints and other application records.

Application Workflow

1. The user interacts with the React frontend.
2. React sends an HTTP request to the Django backend.
3. Django processes and validates the request.
4. The backend communicates with the configured database.
5. Django returns the response.
6. React displays the updated information.

7. Project Folder Structure

The project is organised into separate frontend and backend directories.

mess-management/
│
├── backend/
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   │
│   ├── mess/
│   │   ├── management/
│   │   ├── migrations/
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── billing.py
│   │   ├── exceptions.py
│   │   ├── models.py
│   │   ├── permissions.py
│   │   ├── serializers.py
│   │   ├── tests.py
│   │   ├── urls.py
│   │   └── views.py
│   │
│   ├── staticfiles/
│   ├── venv/
│   ├── manage.py
│   ├── requirements.txt
│   ├── db.sqlite3
│   ├── build.sh
│   └── start.sh
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── dist/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── postcss.config.js
│
├── .gitignore
└── README.md

The structure above is a representative overview; some files and directories may vary in your local project.

8. Installation and Setup

Follow these steps to run the application locally.

Prerequisites

Install the following:

- Python 3.10 or later (compatible with project dependencies).
- Node.js and npm.
- Visual Studio Code.
- Git.

Step 1: Clone the Repository

git clone YOUR_GITHUB_REPOSITORY_URL

Navigate to the project directory:

cd mess-management

Step 2: Setup Backend

Navigate to the backend directory:

cd backend

Create a Python virtual environment:

python -m venv venv

Activate the virtual environment on Windows:

.\venv\Scripts\Activate.ps1

Install backend dependencies:

pip install -r requirements.txt

Apply database migrations:

python manage.py migrate

Start the Django development server:

python manage.py runserver

Backend URL:

http://127.0.0.1:8000/

Step 3: Setup Frontend

Open a second terminal.

Navigate to the frontend directory:

cd frontend

Install dependencies:

npm install

Start the Vite development server:

npm run dev

Frontend URL:

http://localhost:5173/

Step 4: Access the Application

Open your browser and visit:

http://localhost:5173/

Make sure the backend is running and the frontend API configuration points to the correct backend URL.

9. API and Backend Components

The backend uses Django REST Framework to expose application functionality through APIs.

Important backend files include:

File| Responsibility
models.py| Database models
serializers.py| Data serialization and validation
views.py| Request processing and business logic
urls.py| API URL routing
permissions.py| Access control
billing.py| Billing-related logic
admin.py| Django administration configuration
settings.py| Project configuration

10. Deployment

The application is deployed using Render.

Live Application:

https://mess-management-p4mo.onrender.com

Deployment generally involves:

1. Pushing the source code to GitHub.
2. Connecting the repository to Render.
3. Configuring the backend build and start commands.
4. Configuring environment variables.
5. Configuring the frontend build and static asset serving.
6. Connecting the production database.
7. Deploying the application.

11. Future Enhancements

The project can be further improved through:

- Online payment gateway integration.
- Live QR-code scanning for meal attendance.
- Automated SMS and email notifications.
- Advanced inventory tracking.
- Food wastage analytics.
- Automated monthly billing reports.
- Mobile application development.
- Advanced administrator analytics.
- Real-time operational monitoring.

12. Academic Project Information

Project Name: Smart Mess Management System

Institution: International Institute of Information Technology, Bhubaneswar

Project Type: Full-Stack Web Application

Frontend: React.js and Vite

Backend: Python, Django and Django REST Framework

Database: SQLite locally / configured production database

Deployment: Render

Version Control: Git and GitHub

---

13. Conclusion

The Smart Mess Management System is designed to provide a centralised digital solution for managing institutional mess operations.

By combining frontend technologies, backend development and database management, the application helps organise meal bookings, student information, billing, complaints and announcements.

The project demonstrates the practical application of full-stack web development concepts and provides a foundation for further improvements in smart campus management.

Developed as an Academic Project – IIIT Bhubaneswar.

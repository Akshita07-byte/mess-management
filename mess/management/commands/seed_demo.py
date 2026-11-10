"""
Populate the database with DEMO data (not real IIIT Bhubaneswar records).

    python manage.py seed_demo            # first time
    python manage.py seed_demo --reset    # wipe everything and re-create

Logins created
    admin   / Admin@123      (Admin)
    MS001..MS005 / Staff@123 (Mess staff)
    B5xxxxx / Student@123    (Students - roll numbers are printed at the end)
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from mess import billing
from mess.models import (
    MEAL_START,
    Announcement,
    Attendance,
    Booking,
    Complaint,
    Inventory,
    MealMenu,
    Payment,
    Staff,
    Student,
    User,
    Wastage,
)

MALE = ["Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Karthik", "Sourav", "Debasish", "Rahul", "Ankit",
        "Subham", "Pratyush", "Sambit", "Ashutosh", "Manas", "Nikhil", "Rishi", "Tanmay", "Harsh", "Siddharth"]
FEMALE = ["Ananya", "Diya", "Priya", "Sneha", "Ipsita", "Smruti", "Pooja", "Riya", "Swati", "Lipsa",
          "Anjali", "Sasmita", "Nandini", "Kavya", "Tanvi"]
SURNAMES = ["Sahoo", "Mishra", "Patra", "Nayak", "Behera", "Das", "Panda", "Mohanty", "Rout", "Jena",
            "Sharma", "Reddy", "Kumar", "Singh", "Pradhan", "Swain", "Tripathy", "Dash", "Biswal", "Mahapatra"]
BRANCHES = ["CSE", "IT", "ECE", "EEE", "CSE", "IT"]

STAFF = [
    ("MS001", "Ramesh", "Behera", "Head Cook", "FULL"),
    ("MS002", "Sunita", "Nayak", "Cook", "MORNING"),
    ("MS003", "Bikash", "Sahoo", "Store Keeper", "FULL"),
    ("MS004", "Manoj", "Das", "Serving Staff", "EVENING"),
    ("MS005", "Lakshmi", "Pradhan", "Mess Supervisor", "FULL"),
]

# Weekly rotating menu: weekday() 0 = Monday
MENU = {
    0: ("Poha, Boiled Egg / Banana, Tea", "Rice, Dal Tadka, Aloo Gobi, Salad, Curd", "Samosa, Tea", "Chapati, Paneer Butter Masala, Jeera Rice, Gulab Jamun"),
    1: ("Idli, Sambar, Coconut Chutney, Tea", "Rice, Sambar, Cabbage Poriyal, Papad", "Veg Puff, Coffee", "Chapati, Egg Curry / Mix Veg, Rice, Dal Fry"),
    2: ("Aloo Paratha, Curd, Tea", "Rice, Rajma, Bhindi Fry, Salad", "Bread Pakoda, Tea", "Veg Pulao, Raita, Chicken Curry / Paneer Masala"),
    3: ("Upma, Banana, Tea", "Rice, Dal Palak, Aloo Posto, Fish Curry (non-veg)", "Biscuits, Milk", "Chapati, Chole, Jeera Rice, Kheer"),
    4: ("Puri, Aloo Sabzi, Tea", "Rice, Dalma, Mixed Veg, Papad", "Maggi, Tea", "Veg Biryani, Raita, Egg Masala / Paneer Tikka"),
    5: ("Dosa, Sambar, Chutney, Coffee", "Rice, Dal, Kadai Paneer, Salad", "Pav Bhaji", "Chapati, Dal Makhani, Rice, Ice Cream"),
    6: ("Chole Bhature, Lassi", "Special Thali: Rice, Dal, Paneer, Chicken / Veg Kofta, Sweet", "Pakoda, Tea", "Fried Rice, Manchurian, Soup, Fruit Custard"),
}
PRICE = {"BREAKFAST": 30, "LUNCH": 60, "SNACKS": 20, "DINNER": 55}
MEAL_ORDER = ["BREAKFAST", "LUNCH", "SNACKS", "DINNER"]

INVENTORY = [
    ("Rice", "GRAINS", 420, "kg", 150), ("Wheat Flour (Atta)", "GRAINS", 180, "kg", 80),
    ("Toor Dal", "GRAINS", 60, "kg", 40), ("Rajma", "GRAINS", 18, "kg", 25),
    ("Potato", "VEGETABLES", 140, "kg", 60), ("Onion", "VEGETABLES", 95, "kg", 50),
    ("Tomato", "VEGETABLES", 22, "kg", 30), ("Cabbage", "VEGETABLES", 45, "kg", 25),
    ("Milk", "DAIRY", 90, "litre", 60), ("Paneer", "DAIRY", 12, "kg", 15),
    ("Curd", "DAIRY", 55, "kg", 30), ("Cooking Oil", "SPICES", 70, "litre", 40),
    ("Salt", "SPICES", 35, "kg", 15), ("Turmeric Powder", "SPICES", 6, "kg", 8),
    ("Eggs", "OTHER", 420, "pcs", 200), ("Tea Powder", "OTHER", 14, "kg", 10),
]

COMPLAINTS = [
    ("FOOD_QUALITY", "Dal was too watery at lunch", "The dal served at lunch yesterday was very watery and lacked taste.", 2),
    ("HYGIENE", "Dirty plates in the dining hall", "Several steel plates were not washed properly before serving.", 1),
    ("SERVICE", "Long queue during dinner", "The dinner queue took more than 30 minutes because only one counter was open.", 3),
    ("BILLING", "Wrong amount in my bill", "I cancelled 4 meals last week but they appear in my bill.", None),
    ("FOOD_QUALITY", "Rice undercooked", "The rice at dinner was undercooked and hard.", 2),
    ("OTHER", "Request for more vegetarian options", "Please add one more vegetarian option on Sundays.", 4),
    ("HYGIENE", "Flies near the serving area", "Many flies were noticed near the dessert counter.", 2),
    ("SERVICE", "Breakfast ends too early", "Breakfast closes at 9:00 which is too early for students with late classes.", 3),
    ("FOOD_QUALITY", "Stale chapatis", "Chapatis served at dinner were cold and stale.", 1),
    ("BILLING", "Payment not reflected", "I paid last month's bill but it still shows pending.", None),
    ("OTHER", "Drinking water supply", "The water cooler near the mess is not working.", None),
    ("FOOD_QUALITY", "Excess oil in curry", "The curry had too much oil; please reduce it.", 3),
    ("SERVICE", "Rude behaviour at counter", "A serving staff member was impolite when asked for a refill.", 2),
    ("HYGIENE", "Tables not cleaned", "Dining tables were sticky and not cleaned between batches.", 2),
    ("OTHER", "Menu feedback: add fruits", "Please include seasonal fruits twice a week.", 5),
]
RESPONSES = [
    "Thank you for the feedback. The mess committee has taken note and the kitchen has been instructed.",
    "We have inspected the area and corrective action has been taken.",
    "Issue resolved. Please raise a new ticket if it happens again.",
]
WASTE_REASONS = ["Excess cooking", "Lower attendance than booked", "Leftover after service", "Quality issue - discarded", ""]


def meal_start(date, meal_type):
    return timezone.make_aware(datetime.combine(date, MEAL_START[meal_type]))


class Command(BaseCommand):
    help = "Create DEMO data: 50 students, 5 staff, menus, bookings, payments, complaints, inventory."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete all existing data first.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if User.objects.filter(username="admin").exists() and not opts["reset"]:
            self.stdout.write(self.style.WARNING("Demo data already exists. Use --reset to wipe and re-create."))
            return
        if opts["reset"]:
            for model in (Attendance, Wastage, Booking, Payment, Complaint, Inventory, Announcement, MealMenu, Student, Staff):
                model.objects.all().delete()
            User.objects.all().delete()

        random.seed(42)
        now = timezone.now()
        today = timezone.localdate()

        # ---------------------------------------------------------------- users
        admin = User.objects.create_superuser("admin", "admin@demo.example", "Admin@123", first_name="Mess", last_name="Administrator")
        staff_hash = make_password("Staff@123")
        staff_users = []
        for emp_id, first, last, desig, shift in STAFF:
            u = User.objects.create(username=emp_id, first_name=first, last_name=last, role="STAFF",
                                    email=f"{emp_id.lower()}@demo.example", phone=f"90000{random.randint(10000, 99999)}",
                                    password=staff_hash)
            Staff.objects.create(user=u, employee_id=emp_id, designation=desig, shift=shift)
            staff_users.append(u)

        student_hash = make_password("Student@123")
        base = today.year if today.month >= 7 else today.year - 1
        adm_years = [base - 3, base - 2, base - 1, base]
        students = []
        used = set()
        for i in range(50):
            female = i % 10 in (3, 7, 9)
            first = random.choice(FEMALE if female else MALE)
            last = random.choice(SURNAMES)
            adm = adm_years[i % 4]
            roll = f"B5{adm % 100:02d}{(i // 4) + 1:03d}"
            while roll in used:
                roll += "x"
            used.add(roll)
            u = User.objects.create(username=roll, first_name=first, last_name=last, role="STUDENT",
                                    email=f"{first.lower()}.{roll.lower()}@demo.example",
                                    phone=f"98{random.randint(10000000, 99999999)}", password=student_hash)
            hostel = "Girls Hostel" if female else random.choice(["Boys Hostel A", "Boys Hostel B"])
            students.append(Student.objects.create(
                user=u, roll_no=roll, branch=random.choice(BRANCHES), year=base - adm + 1,
                hostel=hostel, room_no=f"{random.randint(1, 4)}{random.randint(0, 2)}{random.randint(1, 9)}",
            ))

        # ---------------------------------------------------------------- menus (7 days back, today, 6 ahead)
        menus = []
        for offset in range(-7, 7):
            d = today + timedelta(days=offset)
            items = MENU[d.weekday()]
            for meal_type, text in zip(MEAL_ORDER, items):
                start = meal_start(d, meal_type)
                if d < today or now > start + timedelta(minutes=90):
                    prep = "SERVED"
                elif d > today or now < start - timedelta(hours=2):
                    prep = "PLANNED"
                elif now < start - timedelta(minutes=15):
                    prep = "PREPARING"
                else:
                    prep = "READY"
                menus.append(MealMenu.objects.create(date=d, meal_type=meal_type, items=text,
                                                     price=PRICE[meal_type], prep_status=prep))

        # ---------------------------------------------------------------- bookings + attendance
        bookings = []
        for s in students:
            appetite = random.uniform(0.6, 0.95)
            for m in menus:
                r = random.random()
                if r < appetite:
                    status = "BOOKED"
                elif r < appetite + 0.05:
                    status = "CANCELLED"
                else:
                    continue
                bookings.append(Booking(student=s, menu=m, status=status,
                                        cancelled_at=now if status == "CANCELLED" else None))
        Booking.objects.bulk_create(bookings)

        attendance = []
        for b in bookings:
            start = meal_start(b.menu.date, b.menu.meal_type)
            if b.status == "BOOKED" and start < now and random.random() < 0.9:
                attendance.append(Attendance(student=b.student, menu=b.menu,
                                             scanned_at=start + timedelta(minutes=random.randint(0, 75)),
                                             marked_by=random.choice(staff_users)))
        Attendance.objects.bulk_create(attendance)

        # ---------------------------------------------------------------- wastage
        for m in menus:
            if m.prep_status == "SERVED":
                kg = Decimal(str(round(random.uniform(1.5, 11.0), 1)))
                Wastage.objects.create(menu=m, quantity_kg=kg, reason=random.choice(WASTE_REASONS),
                                       recorded_by=random.choice(staff_users))

        # ---------------------------------------------------------------- payments
        cur = today.replace(day=1)
        prev1 = (cur - timedelta(days=1)).replace(day=1)
        prev2 = (prev1 - timedelta(days=1)).replace(day=1)
        for month_start, paid_prob in ((prev2, 0.9), (prev1, 0.7)):
            month = month_start.strftime("%Y-%m")
            for s in students:
                meals = random.randint(55, 90)
                charges = Decimal(meals * random.randint(38, 46))
                paid = random.random() < paid_prob
                due = billing.due_date_for(month)
                Payment.objects.create(
                    student=s, month=month, meals_count=meals, meal_charges=charges, fixed_charge=500,
                    amount=charges + 500, status="PAID" if paid else "PENDING", due_date=due,
                    paid_on=timezone.make_aware(datetime.combine(due - timedelta(days=random.randint(1, 9)), datetime.min.time())) if paid else None,
                    txn_ref=f"SIM{random.randint(10**9, 10**10 - 1)}" if paid else "",
                )
        billing.generate_bills(cur.strftime("%Y-%m"))

        # ---------------------------------------------------------------- complaints
        statuses = ["OPEN", "IN_PROGRESS", "RESOLVED"]
        for idx, (cat, subject, desc, rating) in enumerate(COMPLAINTS):
            status = statuses[idx % 3] if idx % 4 else "RESOLVED"
            c = Complaint.objects.create(
                student=random.choice(students), category=cat, subject=subject, description=desc,
                rating=rating, status=status,
                admin_response=random.choice(RESPONSES) if status != "OPEN" else "",
            )
            Complaint.objects.filter(pk=c.pk).update(created_at=now - timedelta(days=random.randint(0, 25), hours=random.randint(0, 20)))

        # ---------------------------------------------------------------- inventory
        for name, cat, qty, unit, reorder in INVENTORY:
            Inventory.objects.create(item_name=name, category=cat, quantity=qty, unit=unit, reorder_level=reorder,
                                     updated_by=random.choice(staff_users))
        Inventory.objects.filter(item_name="Turmeric Powder").update(low_stock_reported=True)

        # ---------------------------------------------------------------- announcements
        for title, msg, prio in [
            ("Welcome to the Smart Mess Portal (DEMO)", "Book your meals online before the deadline. Bookings close 3 hours before each meal.", "INFO"),
            ("Special Dinner on Sunday", "A special dinner with sweets will be served this Sunday. Book in advance.", "IMPORTANT"),
            ("Mess Fee Due Date", "Please clear your pending mess dues before the due date to avoid late fees.", "URGENT"),
            ("Menu Feedback Drive", "Share your feedback through the Complaints & Feedback section. Your ratings help us improve.", "INFO"),
        ]:
            Announcement.objects.create(title=title, message=msg, priority=prio, created_by=admin)

        self.stdout.write(self.style.SUCCESS("DEMO data created (NOT real IIIT Bhubaneswar records)."))
        self.stdout.write("  Admin   : admin / Admin@123")
        self.stdout.write("  Staff   : MS001 ... MS005 / Staff@123")
        self.stdout.write(f"  Students: {students[0].roll_no}, {students[1].roll_no}, ... / Student@123 (50 students)")

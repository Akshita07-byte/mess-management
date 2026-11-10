"""Automatic monthly mess bill calculation.

Bill = fixed monthly charge + sum of prices of all NON-cancelled meal bookings in the month.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Sum

from .models import Booking, Payment, Student


def parse_month(month):
    year, mon = month.split("-")
    return int(year), int(mon)


def compute_bill(student, month, fixed_charge=None):
    year, mon = parse_month(month)
    fixed = Decimal(str(fixed_charge if fixed_charge is not None else settings.MESS_FIXED_CHARGE))
    qs = Booking.objects.filter(
        student=student, status="BOOKED", menu__date__year=year, menu__date__month=mon
    )
    totals = qs.aggregate(meals=Count("id"), charges=Sum("menu__price"))
    breakdown = list(
        qs.values("menu__meal_type").annotate(count=Count("id"), amount=Sum("menu__price")).order_by("menu__meal_type")
    )
    charges = totals["charges"] or Decimal("0")
    return {
        "month": month,
        "meals_count": totals["meals"] or 0,
        "meal_charges": charges,
        "fixed_charge": fixed,
        "total": charges + fixed,
        "breakdown": [
            {"meal_type": b["menu__meal_type"], "count": b["count"], "amount": b["amount"] or 0} for b in breakdown
        ],
    }


def due_date_for(month):
    year, mon = parse_month(month)
    last_day = date(year, mon, calendar.monthrange(year, mon)[1])
    return last_day + timedelta(days=10)


def generate_bills(month, fixed_charge=None):
    """Create/refresh bills for all active students. Paid bills are never changed."""
    created = updated = 0
    for student in Student.objects.filter(user__is_active=True).select_related("user"):
        bill = compute_bill(student, month, fixed_charge)
        payment, was_created = Payment.objects.get_or_create(
            student=student,
            month=month,
            defaults={
                "meals_count": bill["meals_count"],
                "meal_charges": bill["meal_charges"],
                "fixed_charge": bill["fixed_charge"],
                "amount": bill["total"],
                "due_date": due_date_for(month),
            },
        )
        if was_created:
            created += 1
        elif payment.status != "PAID":
            payment.meals_count = bill["meals_count"]
            payment.meal_charges = bill["meal_charges"]
            payment.fixed_charge = bill["fixed_charge"]
            payment.amount = bill["total"]
            payment.save()
            updated += 1
    return {"created": created, "updated": updated}

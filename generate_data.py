
from datetime import date, timedelta
import random
import database as db

PRODUCTS = [
    # Demo placeholders only. Replace/import exact authorized product catalogue from Excel.
    "ITC Product A", "ITC Product B", "ITC Product C", "ITC Product D"
]

OUTLETS = [
    ("Demo General Store","Jaipur","Vaishali Nagar","General Store","DS Demo A","Area Executive Demo",42000),
    ("Demo Paan Corner","Jaipur","Mansarovar","Pan Shop","DS Demo B","Area Executive Demo",30000),
    ("Demo Kirana","Jaipur","Jagatpura","Kirana","DS Demo A","Area Executive Demo",28000),
    ("Demo Market Shop","Jaipur","MI Road","General Store","DS Demo C","Area Executive Demo",50000),
]

def seed():
    db.init_db()
    if db.list_outlets():
        print("Database already contains data. Skipping seed.")
        return

    for p in PRODUCTS:
        db.upsert_product(p)

    for name,city,area,otype,ds,ae,potential in OUTLETS:
        db.upsert_outlet({
            "outlet_name":name,"city":city,"area":area,"outlet_type":otype,
            "ds_name":ds,"area_executive":ae,"monthly_potential":potential
        })
    print(f"Seeded {len(OUTLETS)} demo outlets and {len(PRODUCTS)} placeholder products.")
    print("For your real presentation dataset, import the authorized Excel instead.")

if __name__=="__main__":
    seed()

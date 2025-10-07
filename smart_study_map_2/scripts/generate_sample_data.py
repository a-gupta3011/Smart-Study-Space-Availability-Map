import csv, random, argparse, os

UB_COORD = (12.8233083, 80.0424496)
TP_COORD = (12.8250106, 80.0450886)
TP2_COORD = (12.8247474, 80.0465691)

DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
COURSES = ['CS101','MATH201','ENG101','PHY102','-']

def jitter(lat, lon, seed_key, span=0.0006):
    rnd = random.Random(seed_key)
    return lat + rnd.uniform(-span, span), lon + rnd.uniform(-span, span)

def write_structured(out_rooms='backend/rooms.csv', out_tt='backend/timetable.csv', seed=1):
    random.seed(seed)
    os.makedirs(os.path.dirname(out_rooms), exist_ok=True)

    rows = []

    # 1) UB — 15 floors, 20 classrooms/floor, cap=60
    lat0, lon0 = UB_COORD
    for floor in range(1, 16):
        for rn in range(1, 21):
            room_id = f"UB-{floor:02d}{rn:02d}"
            lat, lon = jitter(lat0, lon0, f"UB-{floor}-{rn}-{seed}")
            rows.append([room_id, 'UB', 60, 'lecture', 'Yes', f'{lat:.6f}', f'{lon:.6f}', 'projector,whiteboard'])

    # 2) TP — 15 floors, rooms 1–4 and 9–12; plus 4 labs total
    lat1, lon1 = TP_COORD
    allowed = [1,2,3,4,9,10,11,12]
    for floor in range(1, 16):
        for rn in allowed:
            room_id = f"TP-{floor:02d}{rn:02d}"
            lat, lon = jitter(lat1, lon1, f"TP-{floor}-{rn}-{seed}")
            rows.append([room_id, 'TP', 60, 'lecture', 'Yes', f'{lat:.6f}', f'{lon:.6f}', 'projector,whiteboard'])
    # 4 labs total (distribute on distinct floors)
    lab_floors = [2, 5, 8, 11]
    lab_nums = [21, 22, 23, 24]
    for lf, rn in zip(lab_floors, lab_nums):
        room_id = f"TP-{lf:02d}{rn:02d}"
        lat, lon = jitter(lat1, lon1, f"TP-LAB-{lf}-{rn}-{seed}")
        rows.append([room_id, 'TP', 60, 'lab', 'Yes', f'{lat:.6f}', f'{lon:.6f}', 'projector,whiteboard'])

    # 3) TP2 — classrooms on G,1,2,6,8–15 (20/floor); labs on 3,4,5 (15/floor); auditoriums on 7 (12 rooms)
    lat2, lon2 = TP2_COORD
    classroom_floors = ['G', 1, 2, 6, 8, 9, 10, 11, 12, 13, 14, 15]
    for fl in classroom_floors:
        for rn in range(1, 21):
            fl_str = '00' if fl == 'G' else f'{int(fl):02d}'
            room_id = f"TP2-{fl_str}{rn:02d}"
            lat, lon = jitter(lat2, lon2, f"TP2-C-{fl}-{rn}-{seed}")
            rows.append([room_id, 'TP2', 60, 'lecture', 'Yes', f'{lat:.6f}', f'{lon:.6f}', 'projector,whiteboard'])
    # labs floors 3,4,5 => 15 per floor
    for fl in [3,4,5]:
        for rn in range(1, 16):
            room_id = f"TP2-{fl:02d}{rn:02d}"
            lat, lon = jitter(lat2, lon2, f"TP2-L-{fl}-{rn}-{seed}")
            rows.append([room_id, 'TP2', 60, 'lab', 'Yes', f'{lat:.6f}', f'{lon:.6f}', 'projector,whiteboard'])
    # auditoriums on floor 7: 12 rooms with total ~1330 capacity
    aud_caps = [120,120,120,110,110,110,110,110,110,110,100,100]  # sums to 1330
    for idx, cap in enumerate(aud_caps, start=1):
        room_id = f"TP2-07{idx:02d}"
        lat, lon = jitter(lat2, lon2, f"TP2-AUD-7-{idx}-{seed}")
        rows.append([room_id, 'TP2', cap, 'auditorium', 'Yes', f'{lat:.6f}', f'{lon:.6f}', 'projector'])

    # Write rooms.csv
    with open(out_rooms, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['room_id','block','capacity','type','AC','lat','lon','amenities'])
        w.writerows(rows)

# Write a larger timetable.csv ensuring >=50% of classrooms booked per day/slot
    with open(out_tt, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['room_id','day','slot','course'])
        rng = random.Random(seed)
        lecture_rooms = [r[0] for r in rows if r[2] and str(r[3]).lower() == 'lecture']
        n = len(lecture_rooms)
        target_frac = 0.6  # book 60% to exceed the 50% requirement
        per_slot = max(1, int(n * target_frac))
        for day in DAYS:
            for slot in range(10):
                # deterministic shuffle per (day,slot)
                rng.shuffle(lecture_rooms)
                selected = lecture_rooms[:per_slot]
                for rid in selected:
                    course = rng.choice([c for c in COURSES if c != '-'])
                    w.writerow([rid, day, slot, course])

# Back-compat wrapper keeping CLI signature (rooms arg is ignored)
def generate(rooms_n=0, out_rooms='backend/rooms.csv', out_tt='backend/timetable.csv', seed=1):
    write_structured(out_rooms, out_tt, seed)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--rooms', type=int, default=0, help='Ignored: structured generator outputs fixed campus design')
    p.add_argument('--seed', type=int, default=1)
    args = p.parse_args()
    generate(args.rooms, seed=args.seed)

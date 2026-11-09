# -*- coding: utf-8 -*-
"""Подготовка GeoJSON населённых пунктов Краснодарского края из CSV Росстата."""
import csv
import glob
import json
import os
import sys

# Консоль Windows может быть в cp1251/cp1252 — не падаем на кириллице в выводе.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
# Имя файла может отличаться нормализацией Unicode — ищем по маске
CSV_PATH = glob.glob(os.path.join(HERE, "*транспорт_2025.csv"))[0]
OUT_DIR = os.path.join(HERE, "data")
OUT_PATH = os.path.join(OUT_DIR, "points.geojson")


def num(value):
    """Число или None, если значение пустое."""
    value = (value or "").strip().replace(",", ".")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def main():
    with open(CSV_PATH, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    features = []
    for r in rows:
        lat = num(r["Широта"])
        lon = num(r["Долгота"])
        if lat is None or lon is None:
            continue

        pop = num(r["Население"])
        buses = num(r["Автобусы, шт."])
        # Автобусов на 1 000 жителей — считаем от численности населения
        buses_1000 = round(buses * 1000.0 / pop, 1) if (buses is not None and pop) else None

        props = {
            "Название": (r["Название в омонимах"] or r["НП"]).strip(),
            "Тип": (r["НП"] or "").split()[0].strip(),  # г / с / ст-ца / х / п / пгт
            "Население": round(pop) if pop else None,
            "Поездки на человека в год": round(num(r["Поездок на человека в год"]), 1)
            if num(r["Поездок на человека в год"]) is not None
            else None,
            "Пассажирооборот на человека, пасс-км": round(num(r["Пассажирооборот на человека, пасс-км"]), 0)
            if num(r["Пассажирооборот на человека, пасс-км"]) is not None
            else None,
            "Автобусов на 1 000 человек": buses_1000,
        }
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props})

    os.makedirs(OUT_DIR, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": features}
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(fc, fh, ensure_ascii=False)

    trips = [f["properties"]["Поездки на человека в год"] for f in features if f["properties"]["Поездки на человека в год"] is not None]
    print(f"Точек: {len(features)}; с данными о поездках: {len(trips)}")


if __name__ == "__main__":
    main()

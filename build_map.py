# -*- coding: utf-8 -*-
"""Интерактивная карта «До Краснодара доеду?» — LLMaps, стиль design.hse.ru."""
import base64
import io
import json
import os

from PIL import Image
from llmaps import Map
from llmaps.layers import CircleLayer
from llmaps.sources import FileSource
from llmaps.components import Popup, Controls

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data", "points.geojson")
OUT_PATH = os.path.join(HERE, "map.html")
CURSOR_SRC = r"C:\Users\fedor\.zcode\cli\image-cache\sess_86ff2eb3-33f2-48b7-b414-9ef3a0ee10d3\image-6d3c44ababbd260d386326ab4b0dcea1.png"

CURSOR_DATA_URI = None


def make_cursor_data_uri():
    """Автобус из PNG -> курсор 44px с прозрачностью, data URI."""
    global CURSOR_DATA_URI
    im = Image.open(CURSOR_SRC).convert("RGBA")
    im = im.crop(im.getbbox())
    target_w = 44
    target_h = max(1, round(im.height * target_w / im.width))
    im = im.resize((target_w, target_h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    CURSOR_DATA_URI = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return target_w, target_h


# ---------- данные ----------
with open(DATA_PATH, encoding="utf-8") as fh:
    fc = json.load(fh)

# Числовые свойства для paint-выражений (латинские ключи) +
# готовые строки для попапа (русская локаль: пробел-разделитель тысяч, запятая)
def ru_int(x):
    return f"{x:,.0f}".replace(",", " ")


def ru_num1(x):
    return f"{x:,.1f}".replace(",", " ").replace(".", ",")


for f in fc["features"]:
    p = f["properties"]
    f["properties"] = {
        "Название": p["Название"],
        "Тип": p["Тип"],
        "population": p["Население"],
        "trips": p["Поездки на человека в год"],
        "Население, чел.": ru_int(p["Население"]) if p["Население"] else "нет данных",
        "Поездок в год на человека": ru_num1(p["Поездки на человека в год"])
        if p["Поездки на человека в год"] is not None
        else "нет данных",
        "Пассажирооборот на человека, пасс-км": ru_int(p["Пассажирооборот на человека, пасс-км"])
        if p["Пассажирооборот на человека, пасс-км"] is not None
        else "нет данных",
        "Автобусов на 1 000 человек": ru_num1(p["Автобусов на 1 000 человек"])
        if p["Автобусов на 1 000 человек"] is not None
        else "нет данных",
    }

TMP_DATA_PATH = os.path.join(HERE, "data", "points_display.geojson")
with open(TMP_DATA_PATH, "w", encoding="utf-8") as fh:
    json.dump(fc, fh, ensure_ascii=False)

# ---------- шкалы ----------
# Радиус: площадь круга ~ населению (r ~ sqrt(pop)), зажим сверху
RADIUS_EXPR = [
    "min", 20.0,
    ["+", 2.6, ["*", 0.019, ["sqrt", ["to-number", ["get", "population"], 500]]]],
]

# Цвет: квантильная шкала белое -> красное; без данных — серый
QUANTILES = [4.5, 22.0, 28.8, 67.4, 773.7]
RAMP = ["#FFFFFF", "#FFD2C9", "#FF8A73", "#EE3F2D", "#9C1008"]
NO_DATA_COLOR = "#B9C0C7"

interpolate_stops = []
for q, c in zip(QUANTILES, RAMP):
    interpolate_stops += [q, c]
COLOR_EXPR = [
    "case",
    ["==", ["typeof", ["get", "trips"]], "null"], NO_DATA_COLOR,
    ["interpolate", ["linear"], ["get", "trips"], *interpolate_stops],
]

# ---------- карта ----------
source = FileSource(id="settlements", path=TMP_DATA_PATH)
layer = CircleLayer(
    id="settlements-layer",
    source=source,
    radius=RADIUS_EXPR,
    color=COLOR_EXPR,
    opacity=0.88,
    stroke_width=0.8,
    stroke_color="#2B2B2B",
    stroke_opacity=0.45,
)

popup = Popup(
    fields=[
        "Название",
        "Население, чел.",
        "Поездок в год на человека",
        "Пассажирооборот на человека, пасс-км",
        "Автобусов на 1 000 человек",
    ],
    field_labels={
        "Название": "Название",
        "Население, чел.": "Население, чел.",
        "Поездок в год на человека": "Поездок в год на человека",
        "Пассажирооборот на человека, пасс-км": "Пассажирооборот, пасс-км",
        "Автобусов на 1 000 человек": "Автобусов на 1 000 чел.",
    },
    trigger="click",
)

m = Map(
    center=[39.0, 45.2],
    zoom=7,
    title="До Краснодара доеду?",
    tiles="carto-light",
    style_url="https://tiles.openfreemap.org/styles/positron",
    locale="ru-RU",
    use_compression=False,  # geobuf требует pbf/pako с CDN; для 102 точек встраиваем GeoJSON напрямую
)
m.add_layer(layer)
m.add_component(popup)
m.add_component(Controls(zoom=True, scale=True, fullscreen=True))
m.auto_extent()

# ---------- курсор-автобус ----------
cw, ch = make_cursor_data_uri()

# ---------- HSE-шапка и легенда ----------
HEADER_HTML = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@700;800;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<div class="hse-left">
  <header class="hse-header">
    <div class="hse-kicker"><span class="hse-square"></span>Росстат · 2025</div>
    <h1>До Краснодара доеду?</h1>
    <p>Населённые пункты Краснодарского края по числу поездок в год на человека в 2025 году по данным Росстата</p>
  </header>
  <aside class="hse-legend" id="hse-legend">
    <div class="hse-legend-head">
      <div class="hse-legend-title">Размер круга — население</div>
      <button class="hse-legend-toggle" id="hse-legend-toggle" aria-label="Свернуть легенду">−</button>
    </div>
    <div class="hse-legend-body">
      <svg class="hse-size-legend" width="210" height="64" viewBox="0 0 210 64">
        <g fill="none" stroke="#2B2B2B" stroke-opacity="0.55" stroke-width="1">
          <circle cx="30" cy="52" r="20"/>
          <circle cx="30" cy="52" r="8.6"/>
          <circle cx="30" cy="52" r="4.5"/>
          <circle cx="30" cy="52" r="3.2"/>
        </g>
        <g font-family="Inter, Arial, sans-serif" font-size="10.5" fill="#1A1A1A">
          <text x="58" y="35">918 тыс. — Краснодар</text>
          <text x="58" y="48">100 тыс.</text>
          <text x="58" y="58">10 тыс.</text>
        </g>
      </svg>
      <div class="hse-legend-note">площадь круга пропорциональна числу жителей</div>

      <div class="hse-legend-title" style="margin-top:14px">Цвет — поездок в год на человека</div>
      <div class="hse-gradient"></div>
      <div class="hse-gradient-labels"><span>4,5</span><span>22</span><span>29</span><span>67</span><span>774</span></div>
      <div class="hse-nodata"><span class="hse-swatch"></span>нет данных</div>
    </div>
  </aside>
</div>
"""

CSS = f"""
:root {{
  --hse-red: #EE3F2D;
  --hse-dark: #1A1A1A;
}}
html, body {{ font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif; color: var(--hse-dark); }}
* {{ cursor: url('{CURSOR_DATA_URI}') {cw // 2 - 2} {ch // 2}, auto !important; }}

/* ---------- левая колонка: шапка + легенда ---------- */
.hse-left {{
  position: absolute; top: 16px; left: 16px; z-index: 50;
  width: 415px; max-width: calc(100vw - 32px);
  display: flex; flex-direction: column; gap: 16px; pointer-events: none;
}}
.hse-left > * {{ pointer-events: auto; }}

/* ---------- шапка (карточка) ---------- */
.hse-header {{
  max-width: 415px; padding: 20px 24px 18px;
  background: #FFFFFF; border: 2px solid var(--hse-dark);
  box-shadow: 6px 6px 0 var(--hse-red);
}}
.hse-header h1 {{
  margin: 6px 0 8px; font-family: 'Inter Tight', 'Inter', Arial, sans-serif;
  font-weight: 900; font-size: 32px; line-height: 1.02; letter-spacing: -0.02em;
  text-transform: uppercase; color: var(--hse-dark);
}}
.hse-header p {{ margin: 0; font-size: 13px; line-height: 1.45; color: #3D3D3D; }}
.hse-kicker {{
  display: flex; align-items: center; gap: 8px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--hse-dark);
}}
.hse-square {{ width: 12px; height: 12px; background: var(--hse-red); display: inline-block; }}

/* ---------- легенда (карточка) ---------- */
.hse-legend {{
  max-width: 300px; padding: 14px 16px 12px;
  background: #FFFFFF; border: 2px solid var(--hse-dark);
  box-shadow: 6px 6px 0 var(--hse-dark);
}}
.hse-legend-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }}
.hse-legend-body {{ margin-top: 4px; }}
.hse-legend-title {{ font-weight: 700; font-size: 12.5px; margin-bottom: 6px; }}
.hse-legend-note {{ font-size: 10.5px; color: #6B6B6B; margin-top: 2px; }}
.hse-legend-toggle {{
  width: 22px; height: 22px; padding: 0;
  border: none; background: transparent; color: var(--hse-dark);
  font-weight: 700; font-size: 15px; line-height: 1;
}}
.hse-legend.collapsed .hse-legend-body {{ display: none; }}
.hse-size-legend {{ overflow: visible; }}
.hse-gradient {{
  height: 14px; border: 1px solid var(--hse-dark);
  background: linear-gradient(to right, #FFFFFF, #FFD2C9, #FF8A73, #EE3F2D, #9C1008);
}}
.hse-gradient-labels {{
  display: flex; justify-content: space-between; font-size: 10.5px; color: #3D3D3D; margin-top: 3px;
}}
.hse-nodata {{ display: flex; align-items: center; gap: 7px; margin-top: 9px; font-size: 11.5px; color: #3D3D3D; }}
.hse-swatch {{
  width: 13px; height: 13px; border-radius: 50%; background: {NO_DATA_COLOR};
  border: 1px solid var(--hse-dark); display: inline-block;
}}

/* ---------- попап ---------- */
.maplibregl-popup-content {{
  font-family: 'Inter', Arial, sans-serif !important;
  padding: 12px 14px !important; border-radius: 0 !important;
  border: 2px solid var(--hse-dark) !important; box-shadow: 5px 5px 0 var(--hse-red) !important;
  min-width: 230px;
}}
.maplibregl-popup-content table {{ width: 100%; border-collapse: collapse; }}
.maplibregl-popup-content td {{ padding: 3px 0; font-size: 12px; vertical-align: top; }}
.maplibregl-popup-content td:first-child {{ color: #6B6B6B; padding-right: 12px; white-space: nowrap; }}
.maplibregl-popup-content td:last-child {{ font-weight: 600; text-align: right; }}
.maplibregl-popup-content tr:first-child td {{ font-weight: 700; font-size: 13px; color: var(--hse-dark); }}
.maplibregl-popup-content tr:first-child td:first-child {{ color: var(--hse-dark); }}
.maplibregl-popup-tip {{ border-top-color: #1A1A1A !important; }}
"""

m.add_custom_html(HEADER_HTML)
m.add_custom_css(CSS)
m.add_custom_js(
    """
document.getElementById('hse-legend-toggle').addEventListener('click', function () {
  var lg = document.getElementById('hse-legend');
  lg.classList.toggle('collapsed');
  this.textContent = lg.classList.contains('collapsed') ? '+' : '−';
});
"""
)

m.save(OUT_PATH)
os.remove(TMP_DATA_PATH)
print("OK:", OUT_PATH)

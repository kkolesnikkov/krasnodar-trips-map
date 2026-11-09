# -*- coding: utf-8 -*-
"""Интерактивная карта «До Краснодара доеду?» — LLMaps, стиль design.hse.ru."""
import base64
import io
import json
import os
import sys

from PIL import Image
from llmaps import Map
from llmaps.layers import CircleLayer
from llmaps.sources import FileSource
from llmaps.components import Popup, Controls

# Консоль Windows может быть в cp1251/cp1252 — не падаем на кириллице в пути.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data", "points.geojson")
OUT_PATH = os.path.join(HERE, "map.html")
# Картинка курсора лежит в репозитории: сборка не зависит от локальных путей.
CURSOR_SRC = os.path.join(HERE, "assets", "bus.png")

# Необязательный ключ CARTO. Без него используется растровая подложка OSM;
# с ключом — векторный стиль Voyager. Ключ не коммитится, а передаётся
# переменной окружения: CARTO_API_KEY=... python build_map.py
CARTO_API_KEY = os.environ.get("CARTO_API_KEY", "").strip()
CARTO_STYLE_URL = (
    "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json?key=" + CARTO_API_KEY
    if CARTO_API_KEY
    else None
)

CURSOR_DATA_URI = None
CURSOR_SIZE = None


def make_cursor_data_uri():
    """Автобус из PNG -> курсор 44px с прозрачностью, data URI.

    Если картинки нет, возвращает None: карта собирается с обычным курсором.
    """
    global CURSOR_DATA_URI, CURSOR_SIZE
    if not os.path.exists(CURSOR_SRC):
        print("WARN: нет assets/bus.png — собираю без курсора-автобуса")
        return None
    im = Image.open(CURSOR_SRC).convert("RGBA")
    im = im.crop(im.getbbox())
    target_w = 44
    target_h = max(1, round(im.height * target_w / im.width))
    im = im.resize((target_w, target_h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    CURSOR_DATA_URI = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    CURSOR_SIZE = (target_w, target_h)
    return CURSOR_SIZE


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

# Границы данных: нужны для центра карты и для точной подгонки в браузере.
lons = [f["geometry"]["coordinates"][0] for f in fc["features"]]
lats = [f["geometry"]["coordinates"][1] for f in fc["features"]]
MIN_LON, MAX_LON = min(lons), max(lons)
MIN_LAT, MAX_LAT = min(lats), max(lats)
CENTER = [round((MIN_LON + MAX_LON) / 2, 6), round((MIN_LAT + MAX_LAT) / 2, 6)]

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
    center=CENTER,
    zoom=7,
    title="До Краснодара доеду?",
    # По умолчанию растровая подложка OSM: она открывается из России без ключа.
    # OpenFreeMap недоступен, CARTO без ключа отдаёт водяные знаки.
    # Если задан CARTO_API_KEY, используется векторный Voyager.
    style_url=CARTO_STYLE_URL,
    tiles="osm",
    locale="ru-RU",
    use_compression=False,  # geobuf требует pbf/pako с CDN; для 102 точек встраиваем GeoJSON напрямую
)
m.add_layer(layer)
m.add_component(popup)
m.add_component(Controls(zoom=True, scale=True, fullscreen=True))
# auto_extent() не используем: LLMaps 2.0 считает zoom как log2(360 / span) - 1
# без учёта размера экрана и для края выдаёт zoom 5 (точки — крошечное пятно).
# Центр задан выше, точную подгонку под экран делает fitBounds в браузере.

# ---------- курсор-автобус ----------
CURSOR_SIZE = make_cursor_data_uri()
cursor_rule = ""
if CURSOR_DATA_URI:
    cw, ch = CURSOR_SIZE
    cursor_rule = (
        f"* {{ cursor: url('{CURSOR_DATA_URI}') {max(0, cw // 2 - 2)} {ch // 2}, auto !important; }}"
    )

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
{cursor_rule}

/* ---------- левая колонка: шапка + легенда ---------- */
.hse-left, .hse-header, .hse-legend {{ box-sizing: border-box; }}
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

/* ---------- мобильная вёрстка ---------- */
@media (max-width: 760px) {{
  .hse-left {{ top: 12px; left: 12px; width: calc(100vw - 24px); gap: 10px; }}
  .hse-header {{ padding: 14px 16px 12px; box-shadow: 4px 4px 0 var(--hse-red); }}
  .hse-header h1 {{ font-size: 26px; margin: 4px 0 6px; }}
  .hse-header p {{ font-size: 12px; }}
  .hse-legend {{ max-width: none; padding: 12px 14px; }}
}}
"""

m.add_custom_html(HEADER_HTML)
m.add_custom_css(CSS)
m.add_custom_js(
    """
(function () {
  var toggle = document.getElementById('hse-legend-toggle');
  var lg = document.getElementById('hse-legend');
  if (!toggle || !lg) return;
  // На телефоне легенда по умолчанию свёрнута, иначе она закрывает карту.
  if (window.innerWidth < 760) {
    lg.classList.add('collapsed');
    toggle.textContent = '+';
  }
  toggle.addEventListener('click', function () {
    lg.classList.toggle('collapsed');
    toggle.textContent = lg.classList.contains('collapsed') ? '+' : '−';
  });
})();
"""
)

# Приглушаем пёструю растровую подложку OSM под светлый стиль карты.
BASE_STYLE_JS = """
(function () {
  var PAINT = {
    'raster-saturation': -0.82,
    'raster-contrast': 0.08,
    'raster-brightness-min': 0.42,
    'raster-brightness-max': 1.0
  };
  function soften() {
    var map = window.llmaps_map;
    if (!map || !map.getLayer('llmaps-base')) return;
    Object.keys(PAINT).forEach(function (key) {
      try { map.setPaintProperty('llmaps-base', key, PAINT[key]); } catch (e) {}
    });
  }
  function boot() {
    var map = window.llmaps_map;
    if (!map) { document.addEventListener('DOMContentLoaded', boot); return; }
    soften();
    map.on('style.load', soften);
  }
  boot();
})();
"""
m.add_custom_js(BASE_STYLE_JS)

# Точная подгонка границ под экран с учётом карточки-шапки слева.
FIT_JS = """
(function () {
  var BOUNDS = [[__MIN_LON__, __MIN_LAT__], [__MAX_LON__, __MAX_LAT__]];

  function fitKrai() {
    var map = window.llmaps_map;
    if (!map || !map.fitBounds) return;
    // Не перебиваем позицию, сохранённую в ссылке (#7/45.2/39.0).
    if (/^#\\d/.test(window.location.hash)) return;

    var panel = document.querySelector('.hse-left');
    var rect = panel ? panel.getBoundingClientRect() : null;
    var pad;
    if (rect && window.innerWidth < 760) {
      pad = {
        top: Math.min(rect.bottom + 12, window.innerHeight * 0.55),
        bottom: 24, left: 16, right: 16
      };
    } else if (rect) {
      pad = { top: 24, bottom: 40, left: rect.right + 16, right: 60 };
    } else {
      pad = { top: 24, bottom: 40, left: 60, right: 60 };
    }
    map.fitBounds(BOUNDS, { padding: pad, duration: 0, maxZoom: 10 });
  }

  if (window.llmaps_map) fitKrai();
  else document.addEventListener('DOMContentLoaded', fitKrai);
  window.addEventListener('load', fitKrai);
})();
"""
FIT_JS = (
    FIT_JS.replace("__MIN_LON__", repr(MIN_LON))
    .replace("__MIN_LAT__", repr(MIN_LAT))
    .replace("__MAX_LON__", repr(MAX_LON))
    .replace("__MAX_LAT__", repr(MAX_LAT))
)
m.add_custom_js(FIT_JS)

m.save(OUT_PATH)
os.remove(TMP_DATA_PATH)
print("OK:", OUT_PATH)

#!/usr/bin/env python3.12
"""
render_map.py — 정제 CSV(code,sido,sido_eng,값들) + 시도 경계로 단계구분 분석지도를 그린다.
(QGIS 바인딩이 있는 python3.12 로 실행)

사용:
  python3.12 render_map.py --matched matched.csv --value-cols 2020 2025 \
       [--mode auto|value|change|both] [--title-prefix "17개 시도 인구"] \
       [--unit 명] [--source "자료: ..."] [--out outdir]

모드:
  value  : 값 컬럼마다 순차색 단계구분도
  change : 값 2개의 증감률(%) 발산색 지도 (적=감소, 청=증가)
  both   : change + 마지막 값 컬럼 지도
  auto   : 값 2개면 both, 1개면 value (기본)

출력: <out>/*.png  +  <out>/merged.gpkg
"""
import argparse
import csv
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp/runtime-root")
Path(os.environ["XDG_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)

from qgis.core import (
    QgsApplication, QgsVectorLayer, QgsField, QgsProject, QgsFeature,
    QgsCoordinateReferenceSystem, QgsVectorFileWriter, QgsCoordinateTransformContext,
    QgsCoordinateTransform, QgsGraduatedSymbolRenderer, QgsRendererRange, QgsFillSymbol,
    QgsClassificationCustom, QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLegend,
    QgsLayoutItemLabel, QgsLayoutPoint, QgsLayoutSize, QgsUnitTypes, QgsLayoutExporter,
    QgsTextFormat, QgsTextBufferSettings, QgsPalLayerSettings, QgsVectorLayerSimpleLabeling,
    QgsLayoutItemScaleBar, Qgis, QgsLegendStyle,
)
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import QVariant

KOREA_CRS = "EPSG:5179"
BOUNDARY_URL = ("https://raw.githubusercontent.com/southkorea/southkorea-maps/"
                "master/kostat/2018/json/skorea-provinces-2018-geo.json")
SEQ = ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"]            # 순차(파랑)
DIV = ["#b2182b", "#ef8a62", "#fddbc7", "#d1e5f0", "#2166ac"]            # 발산(적-백-청)


def ensure_boundary(path):
    if path.exists():
        return
    import subprocess
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["curl", "-sSf", "--max-time", "60", "-o", str(path), BOUNDARY_URL], check=True)


def fmt(v, unit=""):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    s = f"{int(round(f)):,}" if abs(f) >= 1000 else f"{f:g}"
    return s + unit


def quantile_breaks(vals, k=5):
    s = sorted(vals)
    if len(set(s)) <= k:
        uniq = sorted(set(s))
        return [(uniq[i], uniq[i]) for i in range(len(uniq))] or [(min(s), max(s))]
    breaks = [s[0]]
    for i in range(1, k):
        breaks.append(s[int(i * len(s) / k)])
    breaks.append(s[-1])
    # (lo,hi) 쌍
    return [(breaks[i], breaks[i + 1]) for i in range(len(breaks) - 1)]


def diverging_breaks(vals):
    m = max(abs(min(vals)), abs(max(vals))) or 1.0
    # 0 기준 대칭 5구간
    return [(-m, -m / 2), (-m / 2, -1e-9), (-1e-9, 1e-9), (1e-9, m / 2), (m / 2, m)]


def graduated(field, ranges, labels, colors):
    rr = []
    for (lo, hi), lab, c in zip(ranges, labels, colors):
        sym = QgsFillSymbol.createSimple({"color": c, "outline_color": "70,70,70,255",
                                          "outline_width": "0.25"})
        rr.append(QgsRendererRange(lo, hi, sym, lab))
    r = QgsGraduatedSymbolRenderer(field, rr)
    r.setClassificationMethod(QgsClassificationCustom())
    return r


def add_labels(layer, expr, size=8):
    s = QgsPalLayerSettings(); s.fieldName = expr; s.isExpression = True
    tf = QgsTextFormat(); f = QFont("Sans"); f.setBold(True); tf.setFont(f); tf.setSize(size)
    buf = QgsTextBufferSettings(); buf.setEnabled(True); buf.setSize(1.0); buf.setColor(QColor("white"))
    tf.setBuffer(buf); s.setFormat(tf)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(s)); layer.setLabelsEnabled(True)


def _label(layout, text, x, y, w, pt, bold=False, color=None):
    it = QgsLayoutItemLabel(layout); it.setText(text)
    f = QFont("Sans"); f.setBold(bold); f.setPointSize(pt); it.setFont(f)
    if color:
        it.setFontColor(color)
    it.attemptResize(QgsLayoutSize(w, pt * 0.6 + 4, QgsUnitTypes.LayoutMillimeters))
    it.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(it)


def render(layer, title, subtitle, source, out_png, legend_title):
    project = QgsProject.instance()
    layer.setName(legend_title)   # 범례 헤딩 = 레이어명 (중복 방지)
    root = project.layerTreeRoot(); root.removeAllChildren(); root.addLayer(layer)
    layout = QgsPrintLayout(project); layout.initializeDefaults()
    layout.setUnits(QgsUnitTypes.LayoutMillimeters)
    m = QgsLayoutItemMap(layout)
    m.attemptMove(QgsLayoutPoint(8, 24, QgsUnitTypes.LayoutMillimeters))
    m.attemptResize(QgsLayoutSize(198, 165, QgsUnitTypes.LayoutMillimeters))
    m.setCrs(QgsCoordinateReferenceSystem(KOREA_CRS))
    ext = layer.extent(); ext.scale(1.08)
    m.setExtent(ext); m.setLayers([layer]); m.setBackgroundColor(QColor("white"))
    layout.addLayoutItem(m)
    _label(layout, title, 8, 6, 280, 17, bold=True)
    _label(layout, subtitle, 8, 16, 280, 10)
    lg = QgsLayoutItemLegend(layout); lg.setTitle(""); lg.setLinkedMap(m)
    lg.setLegendFilterByMapEnabled(False); lg.setAutoUpdateModel(True)
    lg.setStyleFont(QgsLegendStyle.Title, QFont("Sans", 11, QFont.Bold))
    lg.setStyleFont(QgsLegendStyle.SymbolLabel, QFont("Sans", 9))
    lg.attemptMove(QgsLayoutPoint(210, 28, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(lg)
    sb = QgsLayoutItemScaleBar(layout); sb.setStyle("Single Box"); sb.setLinkedMap(m)
    sb.setUnits(QgsUnitTypes.DistanceKilometers)
    sb.applyDefaultSize(QgsUnitTypes.DistanceKilometers); sb.setNumberOfSegmentsLeft(0)
    sb.attemptMove(QgsLayoutPoint(8, 190, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(sb)
    _label(layout, source, 110, 196, 180, 7, color=QColor(90, 90, 90))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    exporter = QgsLayoutExporter(layout)
    st = QgsLayoutExporter.ImageExportSettings(); st.dpi = 200
    ok = exporter.exportToImage(str(out_png), st) == QgsLayoutExporter.Success
    print(f"{'✔' if ok else '✖'} 지도 저장: {out_png}")
    return ok


def build_layer(matched_csv, value_cols, boundary, gpkg):
    ensure_boundary(boundary)
    data = {}
    with open(matched_csv, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            data[str(r["code"])] = r
    src = QgsVectorLayer(str(boundary), "src", "ogr")
    if not src.isValid():
        raise SystemExit(f"경계 로드 실패: {boundary}")

    fields = [QgsField("code", QVariant.String), QgsField("sido", QVariant.String),
              QgsField("sido_eng", QVariant.String)]
    for vc in value_cols:
        fields.append(QgsField(_safe(vc), QVariant.Double))
    if len(value_cols) == 2:
        fields.append(QgsField("chg_pct", QVariant.Double))

    mem = QgsVectorLayer(f"MultiPolygon?crs={KOREA_CRS}", "sido", "memory")
    dp = mem.dataProvider(); dp.addAttributes(fields); mem.updateFields()
    xform = QgsCoordinateTransform(src.crs(), QgsCoordinateReferenceSystem(KOREA_CRS),
                                   QgsProject.instance())
    for f in src.getFeatures():
        code = str(f["code"])
        if code not in data:
            continue
        row = data[code]
        vals = []
        for vc in value_cols:
            try:
                vals.append(float(row[vc]))
            except (ValueError, KeyError):
                vals.append(None)
        g = f.geometry(); g.transform(xform)
        nf = QgsFeature(mem.fields()); nf.setGeometry(g)
        attrs = [code, row["sido"], row["sido_eng"], *vals]
        if len(value_cols) == 2 and vals[0]:
            attrs.append(round((vals[1] - vals[0]) / vals[0] * 100, 2))
        elif len(value_cols) == 2:
            attrs.append(None)
        nf.setAttributes(attrs); dp.addFeature(nf)
    mem.updateExtents()
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"; opts.layerName = "sido_map"
    gpkg.parent.mkdir(parents=True, exist_ok=True)
    if gpkg.exists():
        gpkg.unlink()
    QgsVectorFileWriter.writeAsVectorFormatV3(mem, str(gpkg), QgsCoordinateTransformContext(), opts)
    print(f"✔ 병합 레이어 저장: {gpkg} (피처 {mem.featureCount()})", file=sys.stderr)
    return str(gpkg)


def _safe(name):
    import re
    s = re.sub(r"\W+", "_", str(name)).strip("_")
    return ("v_" + s) if (s[:1].isdigit() or not s) else s


def value_map(gpkg, field, raw_name, title_prefix, unit, source, out, outdir):
    lyr = QgsVectorLayer(f"{gpkg}|layername=sido_map", raw_name, "ogr")
    QgsProject.instance().addMapLayer(lyr, False)
    vals = [f[field] for f in lyr.getFeatures() if f[field] is not None]
    if not vals:
        print(f"  ⚠ '{raw_name}' 값 없음, 건너뜀", file=sys.stderr); return
    ranges = quantile_breaks(vals, 5)
    labels = [f"{fmt(lo, unit)} ~ {fmt(hi, unit)}" for lo, hi in ranges]
    colors = SEQ[:len(ranges)]
    lyr.setRenderer(graduated(field, ranges, labels, colors))
    add_labels(lyr, f"\"sido_eng\" || '\\n' || format_number(\"{field}\",0)")
    render(lyr, f"{title_prefix} ({raw_name})", f"시도별 {raw_name} · 단계구분도",
           source, out, raw_name)


def change_map(gpkg, value_cols, title_prefix, source, out):
    lyr = QgsVectorLayer(f"{gpkg}|layername=sido_map", "change", "ogr")
    QgsProject.instance().addMapLayer(lyr, False)
    vals = [f["chg_pct"] for f in lyr.getFeatures() if f["chg_pct"] is not None]
    if not vals:
        print("  ⚠ 증감률 계산 불가", file=sys.stderr); return
    ranges = diverging_breaks(vals)
    labels = ["큰 감소", "감소", "0 부근", "증가", "큰 증가"]
    lyr.setRenderer(graduated("chg_pct", ranges, labels, DIV))
    add_labels(lyr, "\"sido_eng\" || '\\n' || format_number(\"chg_pct\",1) || '%'")
    render(lyr, f"{title_prefix} 증감 ({value_cols[0]} → {value_cols[1]})",
           "증감률(%) · 청색=증가, 적색=감소", source, out, "증감률 (%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matched", required=True)
    ap.add_argument("--value-cols", nargs="+", required=True)
    ap.add_argument("--mode", default="auto", choices=["auto", "value", "change", "both"])
    ap.add_argument("--title-prefix", default="17개 시도 분석")
    ap.add_argument("--unit", default="")
    ap.add_argument("--source", default="경계: southkorea-maps(2018) · 좌표계 EPSG:5179")
    ap.add_argument("--out", default="outputs/maps")
    ap.add_argument("--boundary", default="data/external/skorea-provinces-2018-geo.json")
    a = ap.parse_args()

    outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)
    boundary = Path(a.boundary); gpkg = outdir / "merged.gpkg"

    QgsApplication.setPrefixPath("/usr", True)
    qgs = QgsApplication([], False); qgs.initQgis()
    try:
        build_layer(a.matched, a.value_cols, boundary, gpkg)
        g = str(gpkg)
        mode = a.mode
        if mode == "auto":
            mode = "both" if len(a.value_cols) == 2 else "value"
        made = []
        if mode in ("change", "both") and len(a.value_cols) == 2:
            out = outdir / f"change_{_safe(a.value_cols[0])}_{_safe(a.value_cols[1])}.png"
            change_map(g, a.value_cols, a.title_prefix, a.source, out); made.append(out)
        if mode == "value":
            for vc in a.value_cols:
                out = outdir / f"value_{_safe(vc)}.png"
                value_map(g, _safe(vc), vc, a.title_prefix, a.unit, a.source, out, outdir); made.append(out)
        if mode == "both":
            vc = a.value_cols[-1]
            out = outdir / f"value_{_safe(vc)}.png"
            value_map(g, _safe(vc), vc, a.title_prefix, a.unit, a.source, out, outdir); made.append(out)
        print("MADE:" + ";".join(str(p) for p in made))
    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    main()

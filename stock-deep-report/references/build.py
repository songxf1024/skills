#!/usr/bin/env python3
"""
build.py — 读取 /tmp/stock_data.json，生成个股三维深度分析报告 HTML
用法: python3 build.py <input_json> <output_html>

JSON 格式（嵌套结构，由 AI 采集后写入）：
{
  "stock": {"name":"安凯微","code":"688620","market":"A股科创板","secid":"1.688620","badge":"科创板·半导体·AI芯片","company":"芜湖安凯微电子技术股份有限公司"},
  "quote": {"price":15.67,"change_pct":1.88,"change_amt":0.29,"mktcap_y":31.0e8,"ps":11.5,"pb":4.82,"low_52w":10.00,"high_52w":17.45,"ytd_pct":25.63,"rsi":78.71},
  "fin_items": [
    {"label":"营业收入 (2026Q1)","val":"1.50亿","sub":"同比 +47.2%","note":"2025年报：5.08亿（同比 +20.3%）","color":"blue"},
    ...（6个，color: blue/red/purple/amber/green）
  ],
  "fin_table": {"headers":["年度","营收(亿)","同比","净利润(亿)","同比","毛利率","ROE","EPS(元)"],"rows":[...],"note":"趋势说明文字","trend":[{"icon":"📈","title":"营收趋势","color":"green","text":"..."},{"icon":"📉","title":"净利润趋势","color":"red","text":"..."}]},
  "news": [{"date":"2026-07-02","title":"...","sentiment":"neutral","tag":"中性"}],
  "news_summary": "近30天无负面舆情；...",
  "score": {"total":4.8,"label":"观望等待","advice":"基本面修复中...","items":[{"label":"基本面","score":5.0,"color":"amber"},...]},
  "flow": {"today_net":-1203,"today_ratio":-5.35,"bars":[{"label":"今日主力净额","val":-1203,"unit":"万","sign":"流出"},...],"detail":"📊 近5日主力净流入：..."},
  "tech": {"rsi":78.71,"rsi_note":"超买区 (>70)，警惕回调","macd":"0.897 金叉","macd_note":"DIF>DEA，多头信号","kdj":"K=82 D=71 J=95","kdj_note":"K,D已进入高位","boll":{"u":16.82,"m":14.31,"l":11.80,"note":"当前价 15.67，接近上轨"},"ma":{"ma5":15.12,"ma20":13.29,"note":"价格站上所有均线，多头排列"},"vol_ratio":1.32,"vol_note":"今日成交量略高于近5日均量","alpha":[{"days":3,"stock":8.2,"index":3.1,"alpha":5.1},...]},
  "products": [{"name":"AI SoC芯片","pct":55,"color":"blue"},...],
  "products_note": "* 收入占比根据2025年报估算",
  "survey": {"date":"2026-06-25","orgs":"中信证券、华夏基金等38家","qas":[{"q":"Q1：...","a":"A：..."},...]},
  "valuation": {"ps":11.5,"ps_pct":85,"pb":4.82,"pb_pct":72,"note":"PS=11.5x 处于近1年85%高分位..."},
  "index_alpha": {"rows":[{"label":"近5日 Alpha","val":7.6},{"label":"近10日 Alpha","val":12.7},...],"warning":"近20日相对科创指超额收益达24.2%..."},
  "peers": {"headers":["公司","代码","PE(TTM)","PB","PS(TTM)","营收(最近)","净利润(最近)"],"rows":[{"name":"安凯微","code":"688620","pe":"亏损","pb":"4.82x","ps":"11.5x","revenue":"5.08亿","profit":"-0.50亿","highlight":true},...],"note":"💡 安凯微PS(11.5x)高于同行..."},
  "holders": [{"rank":1,"name":"安凯技术","note":"控股股东","pct":"15.66%","pct_color":"blue","chg":"不变","chg_color":"muted"},...],
  "holders_note": "* 数据来源：2026年一季报",
  "risks": ["公司尚未盈利...",...],
  "sources": [{"dim":"...","source":"...","note":"..."}],
  "margin": {"trend":[{"date":"2026-07-01","balance":1234567890,"balance_chg":12345678}], "summary":"近5日融资余额增加1.2亿"},
  "north_south": {"holdings":[{"date":"2026-07-01","holder":"香港中央结算","shares":12345678,"pct":2.5,"chg":123456}], "summary":"北向资金近5日净流入1.2亿"},
  "analyst": {"ratings":[{"org":"中信证券","rating":"买入","target":25.0,"date":"2026-07-01"}], "distribution":{"买入":5,"增持":3,"中性":2}, "consensus_target":24.5, "summary":"5家券商评级..."},
  "lock_up": {"upcoming":[{"date":"2026-08-15","shares":12345678,"pct":5.0,"type":"首发原股东限售"}], "summary":"未来3个月解禁..."},
  "dividend": {"history":[{"year":2025,"dividend":0.5,"yield":1.2,"date":"2026-06-30"}], "summary":"近3年累计分红..."},
  "repo": {"records":[{"date":"2026-07-01","shares":123456,"price":15.0,"amount":1851840}], "summary":"近30天回购..."},
  "block_trade": {"records":[{"date":"2026-07-01","price":15.0,"shares":50000,"discount":-2.5,"buyer":"中信证券北京营业部"}], "summary":"近30天大宗交易..."},
  "billboard": {"records":[{"date":"2026-07-01","reason":"涨幅偏离值达7%","buy_amt":12345678,"sell_amt":9876543,"net":2469135}], "summary":"近30天上榜..."},
  "pledge": {"records":[{"holder":"安凯技术","shares":12345678,"pct":15.0,"warning_line":10.0,"status":"正常"}], "summary":"控股股东质押..."},
  "report_date": "2026-07-03"
}
"""

import json
import sys
import re

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def gen_hero(d):
    s = d["stock"]
    q = d["quote"]
    chg_cls = "up" if q["change_pct"] >= 0 else "down"
    chg_sign = "+" if q["change_pct"] >= 0 else ""
    ytd_cls = "up" if q.get("ytd_pct", 0) >= 0 else "down"
    ytd_sign = "+" if q.get("ytd_pct", 0) >= 0 else ""
    rsic = "var(--red)" if q.get("rsi", 50) > 70 else ("var(--amber)" if q.get("rsi", 50) > 50 else "var(--green)")
    rsnote = "超买" if q.get("rsi", 50) > 70 else ("中性" if q.get("rsi", 50) > 30 else "超卖")
    mktcap = q.get("mktcap_y", 0) / 1e8
    return """<div class="hero">
  <div class="hero-top">
    <div>
      <div class="badge">{badge}</div>
      <h1>{name} ({code})</h1>
      <div class="sub">{company} &nbsp;|&nbsp; {date}</div>
    </div>
    <div class="hero-right">
      <div class="price">{price:.2f}</div>
      <div class="chg {chg_cls}">{arrow} {chg_sign}{chg_pct:.2f}% &nbsp; {chg_sign}{chg_amt:.2f}</div>
    </div>
  </div>
  <div class="hero-meta">
    <div class="m"><span class="ml">总市值</span><span class="mv">{mktcap:.1f}亿</span></div>
    <div class="m"><span class="ml">PS(TTM)</span><span class="mv">{ps}x</span></div>
    <div class="m"><span class="ml">PB</span><span class="mv">{pb}x</span></div>
    <div class="m"><span class="ml">52周区间</span><span class="mv">{low:.2f} ~ {high:.2f}</span></div>
    <div class="m"><span class="ml">年初至今</span><span class="mv {ytd_cls}">{ytd_sign}{ytd_pct:.2f}%</span></div>
    <div class="m"><span class="ml">RSI(14)</span><span class="mv" style="color:{rsic}">{rsi} {rsnote}</span></div>
  </div>
</div>""".format(
        badge=s.get("badge", ""),
        name=s["name"],
        code=s["code"],
        company=s.get("company", ""),
        date=d.get("report_date", ""),
        price=q["price"],
        chg_cls=chg_cls,
        arrow="▲" if q["change_pct"] >= 0 else "▼",
        chg_sign=chg_sign,
        chg_pct=q["change_pct"],
        chg_amt=q.get("change_amt", 0),
        mktcap=mktcap,
        ps=q.get("ps", "--"),
        pb=q.get("pb", "--"),
        low=q.get("low_52w", 0),
        high=q.get("high_52w", 0),
        ytd_cls=ytd_cls,
        ytd_sign=ytd_sign,
        ytd_pct=q.get("ytd_pct", 0),
        rsic=rsic,
        rsi=q.get("rsi", "--"),
        rsnote=rsnote
    )

def gen_sec01(d):
    items = d.get("fin_items", [])
    html = """<div class="sec-div">SEC 01 &nbsp; 基本面分析</div>
<div class="card">
  <h2><span class="icon">📊</span> 核心财务指标</h2>
  <div class="fin-grid">
"""
    color_map = {"blue":"var(--blue)","red":"var(--red)","purple":"var(--purple)","amber":"var(--amber)","green":"var(--green)"}
    for it in items:
        c = color_map.get(it.get("color","blue"),"var(--blue)")
        sub_color = "var(--red)" if "+" in it.get("sub","") else ("var(--muted)" if "-" not in it.get("sub","") else "var(--muted)")
        html += f"""    <div class="fin-item" style="border-left:3px solid {c}">
      <div class="fin-label">{it["label"]}</div>
      <div class="fin-val">{it["val"]} <span style="font-size:12px;color:var(--red);font-weight:600">{it.get("sub","").strip()}</span></div>
      <div class="fin-sub">{it.get("note","")}</div>
    </div>
"""
    html += """  </div>
</div>
"""
    return html

def gen_sec01b(d):
    ft = d.get("fin_table", {})
    headers = ft.get("headers", [])
    rows = ft.get("rows", [])
    html = """<div class="sec-div">SEC 01B &nbsp; 历年财务指标</div>
<div class="card">
  <h2><span class="icon">📈</span> 历年营收与净利润</h2>
  <table>
    <thead><tr>"""
    for h in headers:
        html += f"<th>{h}</th>"
    html += "</tr></thead><tbody>"
    for i, row in enumerate(rows):
        cls = " highlight" if row.get("highlight") else ""
        html += f"<tr class=\"{cls}\">"
        for cell in row["cells"]:
            align = "right" if isinstance(cell, (int, float)) or (isinstance(cell, str) and cell.replace(".","").replace("-","").replace("+","").isdigit()) else "left"
            color = ""
            if isinstance(cell, str):
                if "+" in cell and "%" in cell:
                    color = 'style="color:var(--red);font-weight:700"'
                elif "-" in cell and "%" in cell and cell.count("-") == 1:
                    color = 'style="color:var(--green);font-weight:700"'
                elif cell.startswith("<b>"):
                    color = ""
            html += f"<td {color}>{cell}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    if ft.get("note"):
        html += f'<div style="margin-top:14px;font-size:12.5px;color:var(--muted);line-height:1.7">📊 <b>趋势说明：</b>{ft["note"]}</div>'
    if ft.get("trend"):
        html += '<div style="margin-top:12px;display:flex;gap:18px;flex-wrap:wrap">'
        for t in ft["trend"]:
            bg = "#f0fdf4" if t["color"] == "green" else ("#fef2f2" if t["color"] == "red" else "#f0f9ff")
            border = "#22c55e" if t["color"] == "green" else ("#ef4444" if t["color"] == "red" else "#3b82f6")
            html += f'<div style="flex:1;min-width:200px;padding:12px 16px;background:{bg};border-radius:10px;border-left:3px solid {border}"><div style="font-size:12px;color:{border};font-weight:700;margin-bottom:4px">{t["icon"]} {t["title"]}</div><div style="font-size:13px;color:#1e293b;line-height:1.7">{t["text"]}</div></div>'
        html += "</div>"
    html += "</div>"
    return html

def gen_sec02(d):
    news = d.get("news", [])
    html = """<div class="sec-div">SEC 02 &nbsp; 新闻面（近30天）</div>
<div class="card">
  <h2><span class="icon">📰</span> 近30天重要新闻/公告（情绪标注）</h2>"""
    for n in news:
        tag_color = {"positive":"#dcfce7;color:#166534","neutral":"#fef3c7;color:#92400e","negative":"#fecaca;color:#991b1b"}
        tc = tag_color.get(n.get("sentiment","neutral"), tag_color["neutral"])
        tag = n.get("tag", n.get("sentiment","中性"))
        html += f"""
  <div class="news-item">
    <span class="news-date">{n["date"]}</span>
    <span class="news-title">{n["title"]}</span>
    <span class="news-tag" style="background:{tc}">{tag}</span>
  </div>"""
    if d.get("news_summary"):
        html += f'<div style="margin-top:12px;font-size:12.5px;color:var(--muted)">📝 情绪总结：{d["news_summary"]}</div>'
    html += "</div>"
    return html

def gen_sec03(d):
    sc = d.get("score", {})
    total = sc.get("total", 0)
    label = sc.get("label", "")
    advice = sc.get("advice", "")
    items = sc.get("items", [])
    color_map = {"red":"var(--red)","amber":"var(--amber)","green":"var(--green)","blue":"var(--blue)"}
    html = """<div class="sec-div">SEC 03 &nbsp; 综合评分</div>
<div class="card">
  <div style="display:flex;align-items:flex-start;gap:28px;flex-wrap:wrap">
    <div style="flex:1;min-width:200px">
      <div style="font-size:42px;font-weight:900;color:var(--amber);line-height:1">{total}</div>
      <div style="font-size:14px;color:var(--muted);margin-bottom:8px">综合评分 / 10</div>
      <div style="padding:10px 14px;background:#fef3c7;border-radius:10px;font-size:13px;color:#92400e;line-height:1.6">
        ⚠️ <b>评级：{label}</b><br>{advice}
      </div>
    </div>
    <div style="flex:2;min-width:260px;display:flex;flex-direction:column;gap:10px">""".format(total=total, label=label, advice=advice)
    for it in items:
        c = color_map.get(it.get("color","amber"),"var(--amber)")
        w = int(it["score"] * 10)
        html += f'<div class="score-row"><span class="score-label">{it["label"]}</span><div class="score-track"><div class="score-fill" style="width:{w}%;background:{c}"></div></div><span class="score-num" style="color:{c}">{it["score"]}</span></div>'
    html += """
    </div>
  </div>
</div>"""
    return html

def gen_sec04(d):
    fl = d.get("flow", {})
    html = """<div class="sec-div">SEC 04 &nbsp; 资金面分析</div>
<div class="card">
  <h2><span class="icon">💰</span> 主力资金流向</h2>"""
    for bar in fl.get("bars", []):
        val = bar["val"]
        unit = bar.get("unit", "")
        sign = "up" if val >= 0 else "down"
        sign_char = "+" if val >= 0 else ""
        # Flow bar: red = outflow (negative), green = inflow (positive)
        # Bar width: use abs(val) normalized
        abs_v = abs(val)
        # Simple bar: just show text, no visual bar for simplicity
        html += f"""
  <div class="flow-row">
    <span class="flow-label">{bar["label"]}</span>
    <div class="flow-bar-wrap">
      <div class="flow-bar-n" style="width:{'0' if val >= 0 else '100'}%;background:var(--green);border-radius:7px 0 0 7px"></div>
      <div class="flow-bar-p" style="width:{'100' if val >= 0 else '0'}%;background:var(--red);border-radius:0 7px 7px 0"></div>
    </div>
    <span class="flow-val {sign}">{sign_char}{abs_v}{unit}</span>
  </div>"""
    if fl.get("detail"):
        html += f'<div style="margin-top:14px;font-size:12.5px;color:var(--muted);line-height:1.7">{fl["detail"]}</div>'
    html += "</div>"
    return html

def gen_sec05(d):
    tech = d.get("tech", {})
    alpha = tech.get("alpha", [])
    html = """<div class="sec-div">SEC 05 &nbsp; 技术面（完整指标）</div>
<div class="card">
  <h2><span class="icon">📈</span> 技术指标全景</h2>
  """
    # 第一行：核心指标 RSI + MACD (2列)
    html += '<div class="ind-row-2col">'
    # RSI
    rsi = tech.get("rsi", 50)
    rsi_c = "var(--red)" if rsi > 70 else ("var(--amber)" if rsi > 50 else "var(--green)")
    html += f'<div class="ind-box"><div class="ind-name">RSI(14)</div><div class="ind-val" style="color:{rsi_c}">{rsi:.2f}</div><div class="ind-sub">{tech.get("rsi_note","")}</div></div>'
    # MACD
    macd_c = "var(--red)" if "金叉" in tech.get("macd","") else "var(--green)"
    html += f'<div class="ind-box"><div class="ind-name">MACD(12,26,9)</div><div class="ind-val" style="color:{macd_c}">{tech.get("macd","")}</div><div class="ind-sub">{tech.get("macd_note","")}</div></div>'
    html += '</div>'
    # 第二行：次要指标 2×2
    html += '<div class="ind-row-2col" style="margin-top:14px">'
    # KDJ
    kdj = tech.get("kdj","K=50 D=50 J=50")
    kdj_c = "var(--amber)" if "高位" in tech.get("kdj_note","") or "超买" in tech.get("kdj_note","") else "var(--green)"
    html += f'<div class="ind-box"><div class="ind-name">KDJ(K,D,J)</div><div class="ind-val" style="color:{kdj_c}">{kdj}</div><div class="ind-sub">{tech.get("kdj_note","")}</div></div>'
    # BOLL
    boll = tech.get("boll", {})
    html += f'<div class="ind-box"><div class="ind-name">布林带(BOLL)</div><div class="ind-val">U={boll.get("u","--")} M={boll.get("m","--")} L={boll.get("l","--")}</div><div class="ind-sub">{boll.get("note","")}</div></div>'
    # MA
    ma = tech.get("ma", {})
    html += f'<div class="ind-box"><div class="ind-name">均线 MA</div><div class="ind-val">MA5={ma.get("ma5","--")} MA20={ma.get("ma20","--")}</div><div class="ind-sub">{ma.get("note","")}</div></div>'
    # Vol
    vol = tech.get("vol_ratio", 1)
    vol_c = "var(--red)" if vol > 1.5 else ("var(--amber)" if vol > 1 else "var(--muted)")
    html += f'<div class="ind-box"><div class="ind-name">量比</div><div class="ind-val" style="color:{vol_c}">{vol:.2f}x</div><div class="ind-sub">{tech.get("vol_note","")}</div></div>'
    html += '</div>'
    # 第三行：近N日涨跌幅（含 Alpha） — 单卡片
    if alpha:
        html += '<div class="ind-box" style="margin-top:14px">'
        html += '<div class="ind-name">📉 近N日涨跌幅（Alpha）</div>'
        html += '<div style="margin-top:8px">'
        for a in alpha:
            stock_ret = a.get("stock", 0)
            idx_ret = a.get("index", 0)
            alpha_ret = a.get("alpha", 0)
            alpha_c = "var(--red)" if alpha_ret > 0 else "var(--green)"
            html += (
                f'<div style="display:flex;align-items:center;gap:6px;padding:6px 0;font-size:14px;line-height:1.7">'
                f'<span style="color:var(--muted);min-width:40px">{a["days"]}日：</span>'
                f'<span>股价 <b>{stock_ret:+.1f}%</b></span>'
                f'<span style="color:var(--muted);margin:0 4px">|</span>'
                f'<span>基准 <b>{idx_ret:+.1f}%</b></span>'
                f'<span style="color:var(--muted);margin:0 6px">→</span>'
                f'<span style="font-weight:800;color:{alpha_c}">Alpha {alpha_ret:+.1f}%</span>'
                f'</div>'
            )
        html += '</div></div>'
    html += "</div>"
    return html

def gen_sec06(d):
    # Products
    products = d.get("products", [])
    html = """<div class="sec-div">SEC 06 &nbsp; 业务与机构调研</div>"""
    if products:
        html += """
<div class="card">
  <h2><span class="icon">🔬</span> 产品收入拆分</h2>"""
        color_map = {"blue":"var(--blue)","purple":"var(--purple)","amber":"var(--amber)","green":"var(--green)","red":"var(--red)"}
        for p in products:
            c = color_map.get(p.get("color","blue"),"var(--blue)")
            html += f'<div class="prod-row"><span class="prod-name" style="border-left:3px solid {c};padding-left:8px">{p["name"]}</span><div class="prod-bar-wrap"><div class="prod-bar" style="width:{p["pct"]}%;background:{c}"></div></div><span class="prod-pct">~{p["pct"]}%</span></div>'
        if d.get("products_note"):
            html += f'<div style="margin-top:10px;font-size:12px;color:var(--muted)">{d["products_note"]}</div>'
        html += "</div>"
    # Survey
    survey = d.get("survey", {})
    qas = survey.get("qas", [])
    if qas:
        html += f"""
<div class="card">
  <h2><span class="icon">🎤</span> 机构调研详情（{survey.get("date","")}）</h2>
  <div style="font-size:12.5px;color:var(--muted);margin-bottom:12px">参与机构：{survey.get("orgs","")}</div>"""
        for qa in qas:
            html += f'<div class="qa-item"><div class="qa-q">{qa["q"]}</div><div class="qa-a">{qa["a"]}</div></div>'
        html += "</div>"
    return html

def gen_sec07(d):
    val = d.get("valuation", {})
    ia = d.get("index_alpha", {})
    html = """<div class="sec-div">SEC 07 &nbsp; 估值与相对表现</div>"""
    # Valuation channel
    if val:
        ps_pct = val.get("ps_pct", 50)
        pb_pct = val.get("pb_pct", 50)
        ps_c = "var(--red)" if ps_pct > 70 else ("var(--amber)" if ps_pct > 50 else "var(--green)")
        pb_c = "var(--red)" if pb_pct > 70 else ("var(--amber)" if pb_pct > 50 else "var(--green)")
        html += f"""
<div class="card">
  <h2><span class="icon">📐</span> 历史估值通道（近1年）</h2>
  <div class="val-channel">
    <div class="vc-row"><span class="vc-label">PS(TTM)</span><div class="vc-track" style="background:linear-gradient(90deg,#22c55e,#fbbf24,#ef4444);border-radius:6px"><div class="vc-dot" style="left:{ps_pct}%;background:{ps_c}"></div></div><span style="font-size:12.5px;width:80px;text-align:right;font-weight:700;color:{ps_c}">{val.get("ps","--")}x ({ps_pct}%分位)</span></div>
    <div class="vc-row"><span class="vc-label">PB</span><div class="vc-track" style="background:linear-gradient(90deg,#22c55e,#fbbf24,#ef4444);border-radius:6px"><div class="vc-dot" style="left:{pb_pct}%;background:{pb_c}"></div></div><span style="font-size:12.5px;width:80px;text-align:right;font-weight:700;color:{pb_c}">{val.get("pb","--")}x ({pb_pct}%分位)</span></div>
  </div>
  <div style="margin-top:10px;font-size:12.5px;color:var(--muted);line-height:1.7">{val.get("note","")}</div>
</div>"""
    # Index alpha
    if ia.get("rows"):
        html += """
<div class="card">
  <h2><span class="icon">📡</span> 基准指数对比（Alpha）</h2>
  <div style="font-size:13.5px;line-height:2">"""
        for row in ia["rows"]:
            cls = "var(--red)" if row.get("val", 0) > 0 else "var(--green)"
            html += f'<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--line)"><span>{row["label"]}</span><span style="font-weight:700;color:{cls}">{"+" if row["val"] > 0 else ""}{row["val"]:.1f}%</span></div>'
        html += "</div>"
        if ia.get("warning"):
            html += f'<div style="margin-top:12px;padding:10px 14px;background:#fef2f2;border-radius:10px;font-size:12.5px;color:#991b1b;line-height:1.6">⚠️ {ia["warning"]}</div>'
        html += "</div>"
    return html

def gen_sec08(d):
    peers = d.get("peers", {})
    headers = peers.get("headers", [])
    rows = peers.get("rows", [])
    stock_name = d.get("stock", {}).get("name", "该股")
    html = """<div class="sec-div">SEC 08 &nbsp; 同行对比</div>
<div class="card">
  <h2><span class="icon">🏭</span> 同行估值与业绩对比</h2>
  <table>
    <thead><tr>"""
    for h in headers:
        html += f"<th>{h}</th>"
    html += "</tr></thead><tbody>"
    # 命名字段 -> 表头 headers 的映射（当 rows 未提供 cells 数组时使用）
    field_map = {
        "公司": "name", "代码": "code",
        "PE(TTM)": "pe", "PE": "pe",
        "PB": "pb",
        "PS(TTM)": "ps", "PS": "ps",
        "营收(最近)": "revenue", "营收": "revenue",
        "净利润(最近)": "profit", "净利润": "profit",
        "毛利率": "gross_margin", "ROE": "roe",
    }
    for row in rows:
        cls = "highlight" if row.get("highlight") else ""
        html += f'<tr class="{cls}">'
        cells = row.get("cells")
        if cells:
            # 兼容旧格式：cells 数组
            for cell in cells:
                html += f"<td>{cell}</td>"
        else:
            # 新格式：根据 headers 从命名字段读取
            for h in headers:
                key = field_map.get(h, h.lower())
                html += f'<td>{row.get(key, "--")}</td>'
        html += "</tr>"
    html += "</tbody></table>"
    if peers.get("note"):
        html += f'<div style="margin-top:10px;font-size:12px;color:var(--muted);line-height:1.6">{peers["note"]}</div>'
    html += "</div>"
    return html

def gen_sec09(d):
    holders = d.get("holders", [])
    html = """<div class="sec-div">SEC 09 &nbsp; 股东结构</div>
<div class="card">
  <h2><span class="icon">👥</span> 前十大股东</h2>"""
    chg_color_map = {"green":"var(--red)","red":"var(--green)","muted":"var(--muted)","blue":"var(--blue)"}
    for h in holders:
        pct_c = chg_color_map.get(h.get("pct_color","muted"),"var(--muted)")
        chg_c = chg_color_map.get(h.get("chg_color","muted"),"var(--muted)")
        note = f' <span style="font-size:12px;color:var(--muted)">{h.get("note","")}</span>' if h.get("note") else ""
        html += f'<div class="holder-row"><span class="holder-rank">{h["rank"]}</span><span class="holder-name">{h["name"]}{note}</span><span class="holder-pct" style="color:{pct_c}">{h["pct"]}</span><span class="holder-chg" style="color:{chg_c}">{h.get("chg","")}</span></div>'
    if d.get("holders_note"):
        html += f'<div style="margin-top:10px;font-size:12px;color:var(--muted)">* {d["holders_note"]}</div>'
    html += "</div>"
    return html

def gen_sec10(d):
    risks = d.get("risks", [])
    html = """<div class="sec-div">SEC 10 &nbsp; 风险提示</div>
<div class="card" style="border-left:4px solid var(--amber);border-radius:0 14px 14px 0">"""
    for r in risks:
        html += f'<div class="risk-item"><div class="risk-dot"></div><div>{r}</div></div>'
    html += """<div style="margin-top:16px;padding:12px 16px;background:#fef2f2;border-radius:10px;font-size:13px;color:#991b1b;line-height:1.7">
    ⚠️ <b>非投资建议声明</b><br>
    本报告数据来源于东方财富、同花顺等公开信息，力求准确但不保证完整性。报告中的评分、价格区间、投资建议等内容仅供参考，不构成任何证券投资建议或投资决策依据。股市有风险，投资需谨慎。
  </div>"""
    html += "</div>"
    return html

def gen_sec11(d):
    sources = d.get("sources", [])
    html = """<div class="sec-div">SEC 11 &nbsp; 数据来源</div>
<div class="card" style="font-size:13px;line-height:1.9;color:var(--muted)">
  <h2 style="font-size:15px;margin:0 0 10px;color:var(--ink)">📊 数据来源说明</h2>
  <table style="width:100%;border-collapse:collapse;font-size:13px">"""
    if sources:
        html += '<tr style="background:var(--bg);font-weight:700;color:var(--ink)"><th style="padding:7px 12px;text-align:left;border:1px solid var(--line)">数据维度</th><th style="padding:7px 12px;text-align:left;border:1px solid var(--line)">来源</th><th style="padding:7px 12px;text-align:left;border:1px solid var(--line)">说明</th></tr>'
        for i, s in enumerate(sources):
            bg = "#fafbfc" if i % 2 == 1 else "transparent"
            html += f'<tr style="background:{bg}"><td style="padding:6px 12px;border:1px solid var(--line)">{s.get("dim","")}</td><td style="padding:6px 12px;border:1px solid var(--line)">{s.get("source","")}</td><td style="padding:6px 12px;border:1px solid var(--line)">{s.get("note","")}</td></tr>'
    html += """</table>
  <div style="margin-top:12px;font-size:12px;color:#9ca3af;border-top:1px solid var(--line);padding-top:10px">
    ⚠️ 数据截止 """ + d.get("report_date","") + """ 盘中（实时行情有延迟）。财务数据以公司正式公告为准，本报告中数据如有偏差，以交易所/公司公告为准。
  </div>
</div>"""
    return html

def gen_sec12(d):
    """SEC 12 — 融资融券与北向资金"""
    html = '<div class="sec-div">SEC 12 &nbsp; 融资融券与北向资金</div>'
    # 融资融券
    margin = d.get("margin", {})
    html += '<div class="card" style="margin-bottom:18px">\n  <h2><span class="icon">💹</span> 融资融券明细</h2>'
    trend = margin.get("trend", [])
    if trend:
        html += '<table><thead><tr><th>日期</th><th>融资余额(万)</th><th>较前日(万)</th><tr></thead><tbody>'
        for i, row in enumerate(trend):
            bg = "#fafbfc" if i % 2 == 1 else "transparent"
            chg_cls = "up" if row.get("balance_chg", 0) >= 0 else "down"
            chg_sign = "+" if row.get("balance_chg", 0) >= 0 else ""
            html += f'<tr style="background:{bg}"><td>{row.get("date","")}</td><td>{row.get("balance",0)/1e4:.1f}</td><td class="{chg_cls}">{chg_sign}{row.get("balance_chg",0)/1e4:.1f}</td></tr>'
        html += "</tbody></table>"
    else:
        html += '<div style="color:var(--muted);font-size:13px;padding:12px 0">暂无融资融券数据</div>'
    if margin.get("summary"):
        html += f'<div style="margin-top:12px;font-size:12.5px;color:var(--muted);line-height:1.7">📊 {margin["summary"]}</div>'
    html += '</div>'

    # 北向/南向资金
    ns = d.get("north_south", {})
    html += '<div class="card">\n  <h2><span class="icon">🌏</span> 北向/南向资金持仓</h2>'
    holdings = ns.get("holdings", [])
    if holdings:
        html += '<table><thead><tr><th>日期</th><th>持股方</th><th>持股数(万股)</th><th>占流通比%</th><th>变动(万股)</th></tr></thead><tbody>'
        for i, row in enumerate(holdings):
            bg = "#fafbfc" if i % 2 == 1 else "transparent"
            chg_cls = "up" if row.get("chg", 0) >= 0 else "down"
            chg_sign = "+" if row.get("chg", 0) >= 0 else ""
            html += f'<tr style="background:{bg}"><td>{row.get("date","")}</td><td>{row.get("holder","")}</td><td>{row.get("shares",0)/1e4:.1f}</td><td>{row.get("pct",0):.2f}%</td><td class="{chg_cls}">{chg_sign}{row.get("chg",0)/1e4:.1f}</td></tr>'
        html += "</tbody></table>"
    else:
        html += '<div style="color:var(--muted);font-size:13px;padding:12px 0">暂无北向/南向资金数据</div>'
    if ns.get("summary"):
        html += f'<div style="margin-top:12px;font-size:12.5px;color:var(--muted);line-height:1.7">📊 {ns["summary"]}</div>'
    html += '</div>'
    return html

def gen_sec13(d):
    """SEC 13 — 分析师评级与一致预期"""
    html = '<div class="sec-div">SEC 13 &nbsp; 分析师评级与一致预期</div><div class="card">'
    html += '\n  <h2><span class="icon">📝</span> 分析师评级汇总</h2>'
    analyst = d.get("analyst", {})
    ratings = analyst.get("ratings", [])
    dist = analyst.get("distribution", {})

    # 评级分布条
    if dist:
        total_r = sum(dist.values()) or 1
        html += '<div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap">'
        colors = {"买入":"var(--red)","增持":"var(--amber)","中性":"var(--blue)","减持":"var(--green)","卖出":"var(--purple)"}
        for k, v in dist.items():
            c = colors.get(k, "var(--muted)")
            pct = v / total_r * 100
            html += f'<div style="flex:1;min-width:90px;text-align:center;padding:10px 8px;background:#f8fafc;border-radius:10px"><div style="font-size:11px;color:var(--muted);margin-bottom:4px">{k}</div><div style="font-size:22px;font-weight:800;color:{c}">{v}</div><div style="font-size:11px;color:var(--muted)">{pct:.0f}%</div></div>'
        html += '</div>'

    # 评级明细表
    if ratings:
        html += '<table><thead><tr><th>机构</th><th>评级</th><th>目标价(元)</th><th>日期</th></tr></thead><tbody>'
        for i, r in enumerate(ratings):
            bg = "#fafbfc" if i % 2 == 1 else "transparent"
            rc = "var(--red)" if r.get("rating","") in ["买入","强推"] else ("var(--green)" if r.get("rating","") in ["减持","卖出"] else "var(--amber)")
            html += f'<tr style="background:{bg}"><td>{r.get("org","")}</td><td style="color:{rc};font-weight:700">{r.get("rating","")}</td><td>{r.get("target","--")}</td><td>{r.get("date","")}</td></tr>'
        html += "</tbody></table>"
    else:
        html += '<div style="color:var(--muted);font-size:13px;padding:12px 0">暂无分析师评级数据</div>'

    if analyst.get("consensus_target"):
        html += f'<div style="margin-top:12px;padding:10px 14px;background:#f0fdf4;border-radius:10px;font-size:13px;color:#166534">🎯 一致目标价：<b>{analyst["consensus_target"]}</b> 元 &nbsp;|&nbsp; {analyst.get("summary","")}</div>'
    html += '</div>'
    return html

def gen_sec14(d):
    """SEC 14 — 解禁日历与分红回购"""
    html = '<div class="sec-div">SEC 14 &nbsp; 解禁日历与分红回购</div>'

    # 解禁日历
    lock_up = d.get("lock_up", {})
    html += '<div class="card" style="margin-bottom:18px">\n  <h2><span class="icon">📅</span> 限售股解禁日历</h2>'
    upcoming = lock_up.get("upcoming", [])
    if upcoming:
        html += '<table><thead><tr><th>解禁日期</th><th>解禁股数(万股)</th><th>占总股本%</th><th>类型</th></tr></thead><tbody>'
        for i, row in enumerate(upcoming):
            bg = "#fafbfc" if i % 2 == 1 else "transparent"
            # 安全获取数据，处理类型错误
            date_str = row.get("date", "--")
            shares = row.get("shares", 0)
            pct = row.get("pct", 0)
            type_str = row.get("type", "--")
            # 确保 shares 和 pct 是数字类型
            try:
                shares_val = float(shares) / 1e4
            except (ValueError, TypeError):
                shares_val = 0
            try:
                pct_val = float(pct)
            except (ValueError, TypeError):
                pct_val = 0
            html += f'<tr style="background:{bg}"><td>{date_str}</td><td>{shares_val:.1f}</td><td>{pct_val:.2f}%</td><td>{type_str}</td></tr>'
        html += "</tbody></table>"
    else:
        html += '<div style="color:var(--muted);font-size:13px;padding:12px 0">未来3个月无大宗解禁计划</div>'
    if lock_up.get("summary"):
        html += f'<div style="margin-top:12px;font-size:12.5px;color:var(--muted);line-height:1.7">📊 {lock_up["summary"]}</div>'
    html += '</div>'

    # 分红历史
    divd = d.get("dividend", {})
    html += '<div class="card" style="margin-bottom:18px">\n  <h2><span class="icon">💰</span> 历史分红配送</h2>'
    history = divd.get("history", [])
    if history:
        html += '<table><thead><tr><th>年度</th><th>分红(元/股)</th><th>股息率%</th><th>除权日期</th></tr></thead><tbody>'
        for i, row in enumerate(history):
            bg = "#fafbfc" if i % 2 == 1 else "transparent"
            html += f'<tr style="background:{bg}"><td>{row.get("year","--")}</td><td>{row.get("dividend","--")}</td><td>{row.get("yield","--")}</td><td>{row.get("date","--")}</td></tr>'
        html += "</tbody></table>"
    else:
        html += '<div style="color:var(--muted);font-size:13px;padding:12px 0">暂无分红历史数据</div>'
    if divd.get("summary"):
        html += f'<div style="margin-top:12px;font-size:12.5px;color:var(--muted);line-height:1.7">📊 {divd["summary"]}</div>'
    html += '</div>'

    # 回购进展
    repo = d.get("repo", {})
    html += '<div class="card">\n  <h2><span class="icon">🔄</span> 回购进展</h2>'
    records = repo.get("records", [])
    if records:
        html += '<table><thead><tr><th>公告日期</th><th>回购股数(万股)</th><th>回购均价(元)</th><th>回购金额(万元)</th></tr></thead><tbody>'
        for i, row in enumerate(records):
            bg = "#fafbfc" if i % 2 == 1 else "transparent"
            # 安全获取数据
            date_str = row.get("date", "--")
            shares = row.get("shares", 0)
            price = row.get("price", "--")
            amount = row.get("amount", 0)
            # 确保是数字类型
            try:
                shares_val = float(shares) / 1e4
            except (ValueError, TypeError):
                shares_val = 0
            try:
                amount_val = float(amount) / 1e4
            except (ValueError, TypeError):
                amount_val = 0
            html += f'<tr style="background:{bg}"><td>{date_str}</td><td>{shares_val:.1f}</td><td>{price}</td><td>{amount_val:.1f}</td></tr>'
        html += "</tbody></table>"
    else:
        html += '<div style="color:var(--muted);font-size:13px;padding:12px 0">暂无回购记录</div>'
    if repo.get("summary"):
        html += f'<div style="margin-top:12px;font-size:12.5px;color:var(--muted);line-height:1.7">📊 {repo["summary"]}</div>'
    html += '</div>'
    return html

def gen_sec15(d):
    """SEC 15 — 大宗交易、龙虎榜、股权质押"""
    html = '<div class="sec-div">SEC 15 &nbsp; 大宗交易、龙虎榜与股权质押</div>'

    # 大宗交易
    bt = d.get("block_trade", {})
    html += '<div class="card" style="margin-bottom:18px">\n  <h2><span class="icon">🏷️</span> 大宗交易记录（近30天）</h2>'
    records = bt.get("records", [])
    if records:
        html += '<table><thead><tr><th>日期</th><th>成交价(元)</th><th>成交量(万股)</th><th>折价率%</th><th>买方营业部</th></tr></thead><tbody>'
        for i, row in enumerate(records):
            bg = "#fafbfc" if i % 2 == 1 else "transparent"
            discount_cls = "down" if row.get("discount", 0) < 0 else "up"
            html += f'<tr style="background:{bg}"><td>{row.get("date","")}</td><td>{row.get("price","--")}</td><td>{row.get("shares",0)/1e4:.1f}</td><td class="{discount_cls}">{row.get("discount","--")}%</td><td>{row.get("buyer","--")}</td></tr>'
        html += "</tbody></table>"
    else:
        html += '<div style="color:var(--muted);font-size:13px;padding:12px 0">近30天无大宗交易记录</div>'
    if bt.get("summary"):
        html += f'<div style="margin-top:12px;font-size:12.5px;color:var(--muted);line-height:1.7">📊 {bt["summary"]}</div>'
    html += '</div>'

    # 龙虎榜
    bb = d.get("billboard", {})
    html += '<div class="card" style="margin-bottom:18px">\n  <h2><span class="icon">🐯</span> 龙虎榜记录（近30天）</h2>'
    bb_records = bb.get("records", [])
    if bb_records:
        html += '<table><thead><tr><th>日期</th><th>上榜原因</th><th>买入额(万)</th><th>卖出额(万)</th><th>净买入(万)</th></tr></thead><tbody>'
        for i, row in enumerate(bb_records):
            bg = "#fafbfc" if i % 2 == 1 else "transparent"
            net = row.get("net", 0)
            net_cls = "up" if net >= 0 else "down"
            net_sign = "+" if net >= 0 else ""
            html += f'<tr style="background:{bg}"><td>{row.get("date","")}</td><td>{row.get("reason","")}</td><td>{row.get("buy_amt",0)/1e4:.1f}</td><td>{row.get("sell_amt",0)/1e4:.1f}</td><td class="{net_cls}">{net_sign}{net/1e4:.1f}</td></tr>'
        html += "</tbody></table>"
    else:
        html += '<div style="color:var(--muted);font-size:13px;padding:12px 0">近30天未上龙虎榜</div>'
    if bb.get("summary"):
        html += f'<div style="margin-top:12px;font-size:12.5px;color:var(--muted);line-height:1.7">📊 {bb["summary"]}</div>'
    html += '</div>'

    # 股权质押
    pl = d.get("pledge", {})
    html += '<div class="card">\n  <h2><span class="icon">🔗</span> 股权质押情况</h2>'
    pl_records = pl.get("records", [])
    if pl_records:
        html += '<table><thead><tr><th>股东</th><th>质押股数(万股)</th><th>占持股比%</th><th>预警线</th><th>状态</th></tr></thead><tbody>'
        for i, row in enumerate(pl_records):
            bg = "#fafbfc" if i % 2 == 1 else "transparent"
            status_color = "#16a34a" if row.get("status","") == "正常" else "#dc2626"
            html += f'<tr style="background:{bg}"><td>{row.get("holder","")}</td><td>{row.get("shares",0)/1e4:.1f}</td><td>{row.get("pct",0):.2f}%</td><td>{row.get("warning_line","--")}</td><td style="color:{status_color};font-weight:700">{row.get("status","")}</td></tr>'
        html += "</tbody></table>"
    else:
        html += '<div style="color:var(--muted);font-size:13px;padding:12px 0">无股权质押记录</div>'
    if pl.get("summary"):
        html += f'<div style="margin-top:12px;font-size:12.5px;color:var(--muted);line-height:1.7">📊 {pl["summary"]}</div>'
    html += '</div>'
    return html

CSS = """\
:root{
  --red:#dc2626;--green:#16a34a;--blue:#2563eb;--ink:#1e293b;
  --muted:#64748b;--bg:#f1f5f9;--card:#fff;--line:#e2e8f0;
  --amber:#d97706;--purple:#7c3aed;--rose:#e11d48;
  --down:#16a34a;--up:#dc2626;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font:14.5px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",Arial,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:32px 24px}

/* Hero */
.hero{background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 50%,#1d4ed8 100%);color:#fff;border-radius:20px;padding:32px 36px;margin-bottom:28px;position:relative;overflow:hidden}
.hero::before{content:"";position:absolute;width:320px;height:320px;border-radius:50%;background:rgba(255,255,255,.06);top:-100px;right:-80px}
.hero::after{content:"";position:absolute;width:200px;height:200px;border-radius:50%;background:rgba(255,255,255,.04);bottom:-60px;left:10%}
.hero-top{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;position:relative;z-index:1}
.badge{display:inline-block;padding:4px 12px;border-radius:999px;background:rgba(255,255,255,.18);color:#e0e7ff;font-size:12.5px;font-weight:600;margin-bottom:10px}
.hero h1{font-size:30px;font-weight:800;margin:6px 0 4px;letter-spacing:-.5px}
.hero .sub{color:#c7d2fe;font-size:13.5px}
.hero-right{text-align:right}
.hero-right .price{font-size:40px;font-weight:800;letter-spacing:-1px}
.hero-right .chg{font-size:15.5px;font-weight:700;margin-top:2px}
.hero-right .up{color:#86efac}
.hero-right .down{color:#fca5a5}
.hero-meta{display:flex;gap:24px;margin-top:22px;flex-wrap:wrap;position:relative;z-index:1}
.hero-meta .m{display:flex;flex-direction:column;gap:2px}
.hero-meta .ml{color:#a5b4fc;font-size:11.5px}
.hero-meta .mv{color:#fff;font-size:14.5px;font-weight:700}
.up{color:var(--up)}
.down{color:var(--down)}

/* Section divider */
.sec-div{font-size:11.5px;font-weight:800;color:var(--muted);letter-spacing:2.5px;text-transform:uppercase;padding:18px 0 14px;border-bottom:2px solid var(--line);margin-bottom:18px}

/* Cards */
.card{background:var(--card);border-radius:14px;padding:22px 26px;margin-bottom:18px;border:1px solid var(--line);box-shadow:0 2px 8px rgba(0,0,0,.04);transition:box-shadow .2s}
.card:hover{box-shadow:0 6px 20px rgba(0,0,0,.08)}
.card h2{font-size:16px;font-weight:800;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.card h2 .icon{font-size:20px}

/* 基本面 grid */
.fin-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:4px}
.fin-item{background:#f8fafc;border-radius:10px;padding:14px 16px}
.fin-label{font-size:11.5px;color:var(--muted);margin-bottom:3px}
.fin-val{font-size:16px;font-weight:800;margin-bottom:2px}
.fin-sub{font-size:12px;color:var(--muted)}

/* 新闻面 */
.news-item{display:flex;gap:12px;align-items:flex-start;padding:13px 0;border-bottom:1px solid #f1f5f9}
.news-item:last-child{border-bottom:none}
.news-date{font-size:12px;color:var(--muted);white-space:nowrap;min-width:72px}
.news-title{font-size:13.5px;font-weight:600;flex:1}
.news-tag{font-size:11px;padding:2px 8px;border-radius:999px;font-weight:700;white-space:nowrap}

/* 综合评分 */
.score-row{display:flex;align-items:center;gap:12px;margin-bottom:10px}
.score-label{font-size:13px;width:70px}
.score-track{flex:1;height:10px;background:var(--line);border-radius:5px;overflow:hidden}
.score-fill{height:100%;border-radius:5px;transition:width .8s}
.score-num{font-size:13.5px;font-weight:800;width:36px;text-align:right}

/* 资金面 */
.flow-row{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.flow-label{font-size:13px;width:90px}
.flow-bar-wrap{flex:1;height:14px;background:var(--line);border-radius:7px;overflow:hidden;display:flex}
.flow-val{font-size:13px;font-weight:700;width:90px;text-align:right}

/* 技术面 — 统一 ind-box 风格，与 fin-item 一致 */
.ind-row{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:4px}
.ind-row-2col{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
.ind-box{background:#f8fafc;border-radius:10px;padding:16px 18px;box-sizing:border-box}
.ind-name{font-size:11.5px;color:var(--muted);margin-bottom:4px;font-weight:600}
.ind-val{font-size:17px;font-weight:800;line-height:1.35}
.ind-sub{font-size:12px;color:var(--muted);margin-top:3px;line-height:1.45}

/* 同行对比 table */
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13.5px}
th{background:#f8fafc;padding:10px 12px;text-align:left;font-weight:700;color:var(--ink);border-bottom:2px solid var(--line);font-size:12.5px}
td{padding:10px 12px;border-bottom:1px solid var(--line)}
tr:hover td{background:#f8fafc}
.highlight{background:#eff6ff;font-weight:700}

/* 前十大股东 */
.holder-row{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #f1f5f9}
.holder-rank{font-size:13px;font-weight:800;color:var(--muted);width:22px}
.holder-name{flex:1;font-size:13.5px;font-weight:600}
.holder-pct{font-size:13px;font-weight:700;width:65px;text-align:right}
.holder-chg{font-size:12px;width:55px;text-align:right}

/* 产品拆分 */
.prod-row{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #f1f5f9}
.prod-name{flex:1;font-size:13.5px;font-weight:600}
.prod-bar-wrap{width:40%;height:10px;background:var(--line);border-radius:5px;overflow:hidden}
.prod-bar{height:100%;border-radius:5px}
.prod-pct{font-size:13px;font-weight:700;width:48px;text-align:right}

/* 估值通道 */
.val-channel{margin-top:10px}
.vc-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.vc-label{font-size:12.5px;width:80px}
.vc-track{flex:1;height:12px;border-radius:6px;position:relative;overflow:visible}
.vc-dot{width:12px;height:12px;border-radius:50%;position:absolute;top:0;transform:translateX(-50%);border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.2)}

/* 调研详情 */
.qa-item{padding:12px 0;border-bottom:1px solid #f1f5f9}
.qa-q{font-size:13px;font-weight:700;color:var(--blue);margin-bottom:4px}
.qa-a{font-size:13px;color:#334155;line-height:1.65}

/* 风险提示 */
.risk-item{display:flex;gap:8px;padding:7px 0;align-items:flex-start}
.risk-dot{width:6px;height:6px;border-radius:50%;background:var(--amber);margin-top:7px;flex-shrink:0}

/* 页脚 */
.footer{text-align:center;padding:22px 0 10px;color:var(--muted);font-size:12.5px;border-top:1px solid var(--line);margin-top:10px}

@media(max-width:700px){
  .hero{padding:22px 18px}
  .hero h1{font-size:22px}
  .hero-right .price{font-size:28px}
  .fin-grid{grid-template-columns:1fr}
  .ind-row,.ind-row-2col{grid-template-columns:1fr}
  .hero-meta{gap:14px}
}
"""

def main():
    if len(sys.argv) < 3:
        print("用法: python3 build.py <input_json> <output_html>")
        sys.exit(1)

    data = load_json(sys.argv[1])
    report_date = data.get("report_date", "")
    name = data["stock"]["name"]
    code = data["stock"]["code"]

    # 章节渲染器按顺序调用
    sections = [
        gen_hero, gen_sec01, gen_sec01b, gen_sec02, gen_sec03, gen_sec04,
        gen_sec05, gen_sec06, gen_sec07, gen_sec08, gen_sec09, gen_sec10, gen_sec11,
        gen_sec12, gen_sec13, gen_sec14, gen_sec15,
    ]
    body = "\n".join(fn(data) for fn in sections)

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}({code}) 个股三维深度分析报告</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="wrap">
{body}
<div class="footer">
  {name}({code}) 个股三维深度分析报告 &nbsp;|&nbsp; 数据截止：{report_date} &nbsp;|&nbsp; 由 WorkBuddy AI 生成 &nbsp;|&nbsp; 非投资建议
</div>
</div>
</body>
</html>"""

    # 简单排版：在 </div>、</tr>、独立 </td> 后加换行，便于查看
    html = html.replace("</div>", "</div>\n").replace("</tr>", "</tr>\n")
    html = re.sub(r'(</td>)(?!\s*<)', r'\1\n', html)

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成：{sys.argv[2]}（{len(html)} 字符，约 {len(html.splitlines())} 行）")

if __name__ == "__main__":
    main()

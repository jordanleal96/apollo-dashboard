"""
dashboard_generator.py
Dashboard focado em métricas de cadência de e-mail:
funil de engajamento, taxas com barras coloridas, tabela de sequências e insights Claude.
"""

import re
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _md_to_html(text: str) -> str:
    lines = text.split("\n")
    html_lines = []
    in_list = False
    for line in lines:
        s = line.strip()
        if not s:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        if s.startswith(("- ", "• ", "* ")):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{s[2:]}</li>")
        elif re.match(r"^\d+\.", s):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{s.split('.', 1)[1].strip()}</li>")
        elif s.startswith("#"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            lvl = min(len(s) - len(s.lstrip("#")) + 2, 6)
            html_lines.append(f"<h{lvl}>{s.lstrip('#').strip()}</h{lvl}>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{s}</p>")
    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines)


def _color(value: float, good: float, warn: float, inverse: bool = False) -> str:
    if inverse:
        if value <= good:   return "#22c55e"
        if value <= warn:   return "#f59e0b"
        return "#ef4444"
    else:
        if value >= good:   return "#22c55e"
        if value >= warn:   return "#f59e0b"
        return "#ef4444"


def _bar(pct: float, color: str, max_pct: float = 100) -> str:
    w = min(round(pct / max_pct * 100), 100)
    return (
        f'<div style="background:#1e2535;border-radius:6px;height:10px;margin-top:6px;">'
        f'<div style="width:{w}%;background:{color};height:10px;border-radius:6px;'
        f'transition:width .4s ease;"></div></div>'
    )


def _fmt(n) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "0"


# ── Seções ───────────────────────────────────────────────────────────────────

def _funnel(t: dict) -> str:
    sch  = int(t.get("unique_scheduled", 0) or 0)
    del_ = int(t.get("unique_delivered", 0) or 0)
    opn  = int(t.get("unique_opened", 0) or 0)
    rep  = int(t.get("unique_replied", 0) or 0)

    def conv(a, b):
        return f"{round(a/b*100,1)}%" if b else "—"

    steps = [
        ("Disparados",  sch,  "#6366f1", "100%"),
        ("Entregues",   del_, "#818cf8", conv(del_, sch)),
        ("Abertos",     opn,  "#a78bfa", conv(opn, del_)),
        ("Respondidos", rep,  "#c4b5fd", conv(rep, opn)),
    ]

    items = ""
    for i, (label, val, color, rate) in enumerate(steps):
        w = max(100 - i * 14, 44)
        arrow = (
            f'<div style="text-align:center;color:#334155;font-size:1.1rem;line-height:1;">'
            f'▼ <span style="font-size:.7rem;color:#475569">{steps[i][3] if i > 0 else ""}</span></div>'
            if i > 0 else ""
        )
        items += f"""
        {arrow}
        <div style="width:{w}%;margin:0 auto;background:{color}18;border:1px solid {color}44;
                    border-radius:10px;padding:14px 20px;display:flex;
                    justify-content:space-between;align-items:center;">
          <span style="font-size:.9rem;color:#cbd5e1;font-weight:600">{label}</span>
          <span style="font-size:1.6rem;font-weight:800;color:{color}">{_fmt(val)}</span>
        </div>"""

    return f"""
  <section class="card" style="margin-bottom:24px">
    <h2 class="section-title">📬 Funil de Cadência</h2>
    <div style="display:flex;flex-direction:column;gap:6px;padding:8px 0">
      {items}
    </div>
  </section>"""


def _rates(t: dict) -> str:
    metrics = [
        ("Taxa de Entrega",       t.get("delivery_rate_pct", 0),      95, 90,  False, "Bom ≥95%  ·  Atenção <90%",       100),
        ("Taxa de Abertura",      t.get("open_rate_pct", 0),          30, 20,  False, "Bom ≥30%  ·  Atenção <20%",       100),
        ("Taxa de Resposta",      t.get("reply_rate_pct", 0),          5,  2,  False, "Bom ≥5%   ·  Atenção <2%",         20),
        ("Hard Bounce",           t.get("hard_bounce_rate_pct", 0),    1,  2,  True,  "Bom ≤1%   ·  Crítico >2%",         10),
        ("Spam Bloqueado",        t.get("spam_blocked_rate_pct", 0),   0.5,1,  True,  "Bom ≤0.5% ·  Crítico >1%",         5),
        ("Descadastros",          t.get("unsubscribe_rate_pct", 0),    0.3,0.5,True,  "Bom ≤0.3% ·  Atenção >0.5%",       3),
    ]

    items = ""
    for label, val, good, warn, inv, hint, mx in metrics:
        c = _color(val, good, warn, inv)
        items += f"""
      <div>
        <div style="display:flex;justify-content:space-between;align-items:baseline">
          <span style="font-size:.875rem;color:#94a3b8">{label}</span>
          <span style="font-size:1.25rem;font-weight:800;color:{c}">{val}%</span>
        </div>
        {_bar(val, c, mx)}
        <div style="font-size:.7rem;color:#475569;margin-top:3px">{hint}</div>
      </div>"""

    return f"""
  <section class="card" style="margin-bottom:24px">
    <h2 class="section-title">📊 Taxas de Engajamento</h2>
    <div style="display:flex;flex-direction:column;gap:18px">
      {items}
    </div>
  </section>"""


def _kpis(t: dict) -> str:
    bounce   = int(t.get("unique_bounced", 0) or 0)
    hard_b   = int(t.get("unique_hard_bounced", 0) or 0)
    soft_b   = int(t.get("unique_soft_bounced", 0) or 0)
    spam_b   = int(t.get("unique_spam_blocked", 0) or 0)
    unsub    = int(t.get("unique_unsubscribed", 0) or 0)
    demoed   = int(t.get("unique_demoed", 0) or 0)

    cards = [
        ("🗓️ Reuniões",       demoed,  "#22c55e"),
        ("↩️ Total Bounces",  bounce,  "#f59e0b"),
        ("❌ Hard Bounce",    hard_b,  "#ef4444"),
        ("⏳ Soft Bounce",    soft_b,  "#f97316"),
        ("🚫 Spam Bloq.",     spam_b,  "#ec4899"),
        ("🔕 Descadastros",   unsub,   "#64748b"),
    ]

    items = "".join(f"""
      <div style="background:#0f1117;border:1px solid #1e2535;border-radius:10px;
                  padding:16px;text-align:center;">
        <div style="font-size:1.6rem;font-weight:800;color:{c}">{_fmt(v)}</div>
        <div style="font-size:.75rem;color:#64748b;margin-top:4px;text-transform:uppercase;
                    letter-spacing:.05em">{lbl}</div>
      </div>""" for lbl, v, c in cards)

    return f"""
  <section class="card" style="margin-bottom:24px">
    <h2 class="section-title">📌 Indicadores de Entregabilidade</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px">
      {items}
    </div>
    <p style="font-size:.72rem;color:#334155;margin-top:14px;font-style:italic">
      ⚠️ "Spam Bloqueado" = e-mails rejeitados pelo servidor antes da entrega.
      Se o e-mail caiu na pasta spam do destinatário não é rastreável via API.
    </p>
  </section>"""


def _seq_table(per_sequence: list) -> str:
    if not per_sequence:
        return ""

    rows = ""
    for s in per_sequence:
        name   = s.get("name", "—")
        active = '<span style="color:#22c55e">●</span> Ativa' if s.get("active") else '<span style="color:#475569">● </span>Inativa'
        sch    = _fmt(s.get("unique_scheduled", 0))
        del_   = _fmt(s.get("unique_delivered", 0))
        opn    = _fmt(s.get("unique_opened", 0))
        rep    = _fmt(s.get("unique_replied", 0))
        hb     = s.get("hard_bounce_rate_pct", 0)
        sp     = s.get("spam_blocked_rate_pct", 0)
        orr    = s.get("open_rate_pct", 0)
        rr     = s.get("reply_rate_pct", 0)

        c_or = _color(orr, 30, 20)
        c_rr = _color(rr, 5, 2)
        c_hb = _color(hb, 1, 2, inverse=True)
        c_sp = _color(sp, 0.5, 1, inverse=True)

        rows += f"""
        <tr>
          <td style="padding:10px 12px;color:#cbd5e1;font-weight:500">{name}</td>
          <td style="padding:10px 12px;font-size:.8rem">{active}</td>
          <td style="padding:10px 12px;text-align:right">{sch}</td>
          <td style="padding:10px 12px;text-align:right">{del_}</td>
          <td style="padding:10px 12px;text-align:right">{opn}
            <div style="font-size:.75rem;color:{c_or};font-weight:700">{orr}%</div></td>
          <td style="padding:10px 12px;text-align:right">{rep}
            <div style="font-size:.75rem;color:{c_rr};font-weight:700">{rr}%</div></td>
          <td style="padding:10px 12px;text-align:right;color:{c_hb};font-weight:700">{hb}%</td>
          <td style="padding:10px 12px;text-align:right;color:{c_sp};font-weight:700">{sp}%</td>
        </tr>"""

    return f"""
  <section class="card" style="margin-bottom:24px">
    <h2 class="section-title">📋 Sequências</h2>
    <div style="overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:.83rem">
        <thead>
          <tr style="border-bottom:1px solid #1e2535;color:#475569;font-size:.75rem;
                     text-transform:uppercase;letter-spacing:.06em">
            <th style="padding:8px 12px;text-align:left">Sequência</th>
            <th style="padding:8px 12px;text-align:left">Status</th>
            <th style="padding:8px 12px;text-align:right">Disparados</th>
            <th style="padding:8px 12px;text-align:right">Entregues</th>
            <th style="padding:8px 12px;text-align:right">Abertos</th>
            <th style="padding:8px 12px;text-align:right">Respondidos</th>
            <th style="padding:8px 12px;text-align:right">Hard Bounce</th>
            <th style="padding:8px 12px;text-align:right">Spam Bloq.</th>
          </tr>
        </thead>
        <tbody style="color:#94a3b8">
          {rows}
        </tbody>
      </table>
    </div>
  </section>"""


def _insights(seq_html: str, deliv_html: str, exec_html: str) -> str:
    return f"""
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:20px;margin-bottom:24px">
    <section class="card">
      <h2 class="section-title">🧠 Resumo Executivo</h2>
      <div class="insight-body">{exec_html}</div>
    </section>
    <section class="card">
      <h2 class="section-title">📧 Análise de Sequências</h2>
      <div class="insight-body">{seq_html}</div>
    </section>
    <section class="card">
      <h2 class="section-title">🛡️ Entregabilidade</h2>
      <div class="insight-body">{deliv_html}</div>
    </section>
  </div>"""


# ── Gerador principal ─────────────────────────────────────────────────────────

def generate_dashboard(analysis_result: dict, output_path: str | None = None) -> str:
    OUTPUT_DIR.mkdir(exist_ok=True)
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(OUTPUT_DIR / f"dashboard_{ts}.html")

    email_metrics = analysis_result.get("email_metrics", {})
    totals        = email_metrics.get("totals", {})
    per_sequence  = email_metrics.get("per_sequence", [])
    insights      = analysis_result.get("insights", {})
    generated_at  = datetime.now().strftime("%d/%m/%Y às %H:%M")

    seq_html   = _md_to_html(insights.get("sequences", ""))
    deliv_html = _md_to_html(insights.get("deliverability", ""))
    exec_html  = _md_to_html(insights.get("executive_summary", ""))

    funnel_html  = _funnel(totals)
    rates_html   = _rates(totals)
    kpis_html    = _kpis(totals)
    table_html   = _seq_table(per_sequence)
    insight_html = _insights(seq_html, deliv_html, exec_html)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Apollo — Cadência Dashboard</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #080c14;
      color: #e2e8f0;
      min-height: 100vh;
      padding: 28px 32px;
    }}

    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 32px;
      padding-bottom: 20px;
      border-bottom: 1px solid #1e2535;
    }}

    header h1 {{
      font-size: 1.4rem;
      font-weight: 800;
      background: linear-gradient(135deg, #6366f1 0%, #a78bfa 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      letter-spacing: -.02em;
    }}

    header span {{
      font-size: .78rem;
      color: #334155;
    }}

    .layout {{
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 20px;
      align-items: start;
    }}

    .card {{
      background: #0d1117;
      border: 1px solid #1e2535;
      border-radius: 14px;
      padding: 22px;
    }}

    .section-title {{
      font-size: .78rem;
      font-weight: 700;
      color: #475569;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin-bottom: 18px;
    }}

    .insight-body h3, .insight-body h4, .insight-body h5 {{
      color: #c7d2fe;
      font-size: .9rem;
      margin: 12px 0 4px;
    }}
    .insight-body p {{
      color: #64748b;
      font-size: .82rem;
      line-height: 1.65;
      margin-bottom: 6px;
    }}
    .insight-body ul {{
      padding-left: 16px;
      margin: 4px 0 8px;
    }}
    .insight-body li {{
      color: #64748b;
      font-size: .82rem;
      line-height: 1.7;
    }}
    .insight-body strong {{ color: #a5b4fc; }}

    tbody tr:hover {{ background: #111827; }}

    footer {{
      margin-top: 32px;
      text-align: center;
      font-size: .72rem;
      color: #1e293b;
    }}

    @media (max-width: 800px) {{
      .layout {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>

  <header>
    <h1>Apollo · Cadência Dashboard</h1>
    <span>Gerado em {generated_at} · Powered by Claude</span>
  </header>

  <div class="layout">
    <!-- Coluna esquerda: funil + taxas + KPIs -->
    <div>
      {funnel_html}
      {rates_html}
      {kpis_html}
    </div>

    <!-- Coluna direita: tabela + insights -->
    <div>
      {table_html}
      {insight_html}
    </div>
  </div>

  <footer>Apollo Cadência Dashboard · Claude (Anthropic) · {generated_at}</footer>

</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[Dashboard] Arquivo gerado: {output_path}")
    return output_path


# ── Pipeline completo ─────────────────────────────────────────────────────────

def run(apollo_summary: dict | None = None) -> str:
    if apollo_summary is None:
        from apollo_collector import collect_summary
        apollo_summary = collect_summary()

    from analyzer import run_full_analysis
    analysis = run_full_analysis(apollo_summary)
    return generate_dashboard(analysis)


if __name__ == "__main__":
    # Teste com dados mockados
    email_metrics = {
        "totals": {
            "unique_scheduled": 1500, "unique_delivered": 1410,
            "unique_opened": 480,     "unique_replied": 72,
            "unique_bounced": 75,     "unique_hard_bounced": 30,
            "unique_soft_bounced": 45,"unique_spam_blocked": 15,
            "unique_unsubscribed": 8, "unique_demoed": 12,
            "delivery_rate_pct": 94.0,"open_rate_pct": 34.0,
            "reply_rate_pct": 5.1,    "bounce_rate_pct": 5.0,
            "hard_bounce_rate_pct": 2.0,"soft_bounce_rate_pct": 3.0,
            "spam_blocked_rate_pct": 1.0,"unsubscribe_rate_pct": 0.6,
        },
        "per_sequence": [
            {"name": "Prospecção Fria Q1", "active": True,
             "unique_scheduled": 800, "unique_delivered": 768,
             "unique_opened": 307, "unique_replied": 46,
             "hard_bounce_rate_pct": 1.0, "spam_blocked_rate_pct": 0.6,
             "open_rate_pct": 40.0, "reply_rate_pct": 6.0},
            {"name": "Reativação Inativos", "active": True,
             "unique_scheduled": 400, "unique_delivered": 356,
             "unique_opened": 71, "unique_replied": 14,
             "hard_bounce_rate_pct": 4.5, "spam_blocked_rate_pct": 2.0,
             "open_rate_pct": 20.0, "reply_rate_pct": 3.9},
            {"name": "Nurturing Mid-Market", "active": False,
             "unique_scheduled": 300, "unique_delivered": 286,
             "unique_opened": 102, "unique_replied": 12,
             "hard_bounce_rate_pct": 1.3, "spam_blocked_rate_pct": 0.7,
             "open_rate_pct": 35.7, "reply_rate_pct": 4.2},
        ],
    }

    mock = {
        "email_metrics": email_metrics,
        "insights": {
            "sequences": "**Prospecção Fria Q1** performando acima do benchmark com 40% de abertura.\n- ⚠️ Reativação com hard bounce crítico de 4.5% — lista desatualizada\n- Nurturing com boa abertura mas resposta abaixo do ideal",
            "deliverability": "**Diagnóstico:** ⚠️ Atenção necessária\n- Hard bounce global de 2% — no limite crítico\n- Spam bloqueado em 1% — limiar atingido\n- **Ação imediata:** limpar lista da sequência Reativação",
            "executive_summary": "**Situação atual**\nProspecção fria saudável, porém Reativação apresenta riscos críticos de entregabilidade que podem comprometer a reputação do domínio.\n\n**Top ações**\n- Pausar e limpar lista da Reativação\n- Auditar domínio no Google Postmaster Tools\n- Escalar estrutura do Q1 para novos segmentos",
        },
    }

    path = generate_dashboard(mock)
    print(f"\nfile://{path}")

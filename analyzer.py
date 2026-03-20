"""
analyzer.py
Usa Claude (Anthropic) para analisar os dados coletados do Apollo.io
e gerar insights estratégicos de vendas e prospecção.
"""

import os
import json
import anthropic
from pathlib import Path

# Carrega .env se existir
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-6"

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


SYSTEM_PROMPT = """Você é um especialista em inteligência de vendas B2B e estratégia de prospecção.
Analisa dados do Apollo.io e fornece insights acionáveis, claros e objetivos.
Responda sempre em português brasileiro.
Suas análises devem incluir: padrões identificados, oportunidades, riscos e recomendações práticas."""


def analyze_people(people_sample: list[dict]) -> str:
    """Analisa o perfil dos contatos e identifica padrões de ICP."""
    if not people_sample:
        return "Nenhum contato disponível para análise."

    prompt = f"""Analise os seguintes contatos do Apollo.io e forneça insights sobre:
1. Perfil predominante (cargo, senioridade, setor)
2. Distribuição geográfica
3. Qualidade dos dados (status de e-mail)
4. Recomendações para segmentação e abordagem

Dados dos contatos:
{json.dumps(people_sample, indent=2, ensure_ascii=False)}

Seja direto e objetivo. Use bullet points."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def analyze_organizations(organizations_sample: list[dict]) -> str:
    """Analisa as organizações e identifica segmentos de mercado."""
    if not organizations_sample:
        return "Nenhuma organização disponível para análise."

    prompt = f"""Analise as seguintes organizações do Apollo.io e forneça insights sobre:
1. Segmentos de mercado predominantes
2. Porte das empresas (número de funcionários e receita)
3. Tecnologias utilizadas e o que isso revela sobre o perfil
4. Oportunidades de mercado identificadas
5. Recomendações de priorização

Dados das organizações:
{json.dumps(organizations_sample, indent=2, ensure_ascii=False)}

Seja direto e objetivo. Use bullet points."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def analyze_sequences(sequences_sample: list[dict]) -> str:
    """Analisa o desempenho das sequências de e-mail."""
    if not sequences_sample:
        return "Nenhuma sequência disponível para análise."

    prompt = f"""Analise o desempenho das seguintes sequências de e-mail do Apollo.io.
Os dados já incluem taxas calculadas (_pct).

Benchmarks de referência:
- Entrega (delivery_rate_pct): bom >95%, atenção <90%
- Abertura (open_rate_pct): bom >30%, atenção <20%
- Resposta (reply_rate_pct): bom >5%, atenção <2%
- Bounce total (bounce_rate_pct): bom <3%, crítico >5%
- Hard bounce (hard_bounce_rate_pct): crítico >2% (risco de blacklist)
- Spam bloqueado (spam_blocked_rate_pct): crítico >1%
- Descadastro (unsubscribe_rate_pct): atenção >0.5%

Forneça insights sobre:
1. Sequências com melhor e pior desempenho (destaque nome e métrica principal)
2. Problemas de entregabilidade identificados (bounces, spam bloqueado)
3. Risco de reputação do domínio (baseado em hard bounces e spam)
4. Recomendações específicas por sequência com problema
5. Próximos passos priorizados

Dados:
{json.dumps(sequences_sample, indent=2, ensure_ascii=False)}

Seja direto. Use bullet points. Marque itens críticos com ⚠️."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def analyze_deliverability(email_metrics: dict) -> str:
    """Analisa a saúde geral de entregabilidade com foco em spam e bounces."""
    totals = email_metrics.get("totals", {})
    if not totals.get("unique_scheduled"):
        return "Nenhum e-mail disparado encontrado."

    prompt = f"""Analise a saúde de entregabilidade de e-mails do Apollo.io com base nos dados abaixo.

DADOS GLOBAIS (todas as sequências agregadas):
{json.dumps(totals, indent=2, ensure_ascii=False)}

Responda com:
1. **Diagnóstico geral** — saúde atual em uma frase (saudável / atenção / crítico)
2. **Análise de bounces** — hard bounce indica e-mails inválidos (limpar lista); soft bounce pode ser temporário
3. **Análise de spam bloqueado** — e-mails rejeitados antes da entrega; acima de 1% é sinal de alerta
4. **Risco de reputação** — avalie se o domínio/IP pode estar em blacklist
5. **O que NÃO é possível medir via API** — seja transparente sobre limitações (ex: e-mail na pasta spam do destinatário não é rastreável sem acesso à caixa)
6. **Ações corretivas recomendadas** — priorizadas por impacto

Use bullet points. Marque itens críticos com ⚠️ e itens saudáveis com ✅."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def generate_executive_summary(
    totals: dict,
    people_insight: str,
    org_insight: str,
    seq_insight: str,
    deliverability_insight: str,
) -> str:
    """Gera um resumo executivo consolidando todos os insights."""
    email_totals = totals.get("email_totals", {})
    prompt = f"""Com base nas análises do Apollo.io abaixo, crie um resumo executivo de vendas:

TOTAIS:
- Contatos: {totals.get('people', 0):,}
- Organizações: {totals.get('organizations', 0):,}
- E-mails disparados: {email_totals.get('unique_scheduled', 0):,}
- Taxa de entrega: {email_totals.get('delivery_rate_pct', 0)}%
- Taxa de abertura: {email_totals.get('open_rate_pct', 0)}%
- Taxa de resposta: {email_totals.get('reply_rate_pct', 0)}%
- Bounce rate: {email_totals.get('bounce_rate_pct', 0)}%
- Spam bloqueado: {email_totals.get('spam_blocked_rate_pct', 0)}%

ANÁLISE DE CONTATOS:
{people_insight}

ANÁLISE DE ORGANIZAÇÕES:
{org_insight}

ANÁLISE DE SEQUÊNCIAS:
{seq_insight}

ANÁLISE DE ENTREGABILIDADE:
{deliverability_insight}

O resumo executivo deve ter:
1. Situação atual (2-3 frases incluindo saúde de e-mail)
2. Top 3 oportunidades imediatas
3. Top 3 riscos ou pontos de atenção (inclua riscos de entregabilidade se existirem)
4. Plano de ação para os próximos 30 dias (5 ações priorizadas)

Formato: use títulos e bullet points. Tom: executivo e direto."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def run_full_analysis(apollo_summary: dict) -> dict:
    """
    Executa análise completa sobre o resumo coletado pelo apollo_collector.
    Retorna dicionário com todos os insights prontos para o dashboard.
    """
    totals = apollo_summary.get("totals", {})
    people = apollo_summary.get("people_sample", [])
    orgs = apollo_summary.get("organizations_sample", [])
    seqs = apollo_summary.get("sequences_sample", [])
    email_metrics = apollo_summary.get("email_metrics", {})

    print("[Analyzer] Analisando contatos com Claude...")
    people_insight = analyze_people(people)

    print("[Analyzer] Analisando organizações com Claude...")
    org_insight = analyze_organizations(orgs)

    print("[Analyzer] Analisando sequências com Claude...")
    seq_insight = analyze_sequences(seqs)

    print("[Analyzer] Analisando entregabilidade com Claude...")
    deliverability_insight = analyze_deliverability(email_metrics)

    # Adiciona totais de e-mail ao dicionário de totais para o executive summary
    enriched_totals = {**totals, "email_totals": email_metrics.get("totals", {})}

    print("[Analyzer] Gerando resumo executivo com Claude...")
    exec_summary = generate_executive_summary(
        enriched_totals, people_insight, org_insight, seq_insight, deliverability_insight
    )

    result = {
        "totals": enriched_totals,
        "email_metrics": email_metrics,
        "insights": {
            "people": people_insight,
            "organizations": org_insight,
            "sequences": seq_insight,
            "deliverability": deliverability_insight,
            "executive_summary": exec_summary,
        },
    }

    print("[Analyzer] Análise concluída.")
    return result


if __name__ == "__main__":
    mock_summary = {
        "totals": {"people": 1200, "organizations": 340, "sequences": 3},
        "people_sample": [
            {"name": "Ana Silva", "title": "CTO", "organization": "TechBR", "seniority": "c_suite",
             "city": "São Paulo", "country": "Brazil", "email_status": "verified"},
            {"name": "João Costa", "title": "VP de Vendas", "organization": "FinTech SA", "seniority": "vp",
             "city": "Rio de Janeiro", "country": "Brazil", "email_status": "verified"},
        ],
        "organizations_sample": [
            {"name": "TechBR", "industry": "Software", "employee_count": 250,
             "country": "Brazil", "annual_revenue": "$10M", "technology_names": ["AWS", "Salesforce"]},
        ],
        "email_metrics": {
            "totals": {
                "unique_scheduled": 1500, "unique_delivered": 1410,
                "unique_opened": 480, "unique_replied": 72,
                "unique_bounced": 75, "unique_hard_bounced": 30,
                "unique_soft_bounced": 45, "unique_spam_blocked": 15,
                "unique_unsubscribed": 8,
                "delivery_rate_pct": 94.0, "open_rate_pct": 34.0,
                "reply_rate_pct": 5.1, "bounce_rate_pct": 5.0,
                "hard_bounce_rate_pct": 2.0, "soft_bounce_rate_pct": 3.0,
                "spam_blocked_rate_pct": 1.0, "unsubscribe_rate_pct": 0.6,
            },
            "per_sequence": [
                {"name": "Prospecção Fria Q1", "active": True,
                 "unique_scheduled": 800, "unique_delivered": 768,
                 "unique_opened": 307, "unique_replied": 46,
                 "unique_bounced": 20, "unique_hard_bounced": 8,
                 "unique_soft_bounced": 12, "unique_spam_blocked": 5,
                 "unique_unsubscribed": 3,
                 "delivery_rate_pct": 96.0, "open_rate_pct": 40.0,
                 "reply_rate_pct": 6.0, "bounce_rate_pct": 2.5,
                 "hard_bounce_rate_pct": 1.0, "soft_bounce_rate_pct": 1.5,
                 "spam_blocked_rate_pct": 0.6, "unsubscribe_rate_pct": 0.4},
                {"name": "Reativação Inativos", "active": True,
                 "unique_scheduled": 400, "unique_delivered": 356,
                 "unique_opened": 71, "unique_replied": 14,
                 "unique_bounced": 38, "unique_hard_bounced": 18,
                 "unique_soft_bounced": 20, "unique_spam_blocked": 8,
                 "unique_unsubscribed": 4,
                 "delivery_rate_pct": 89.0, "open_rate_pct": 20.0,
                 "reply_rate_pct": 3.9, "bounce_rate_pct": 9.5,
                 "hard_bounce_rate_pct": 4.5, "soft_bounce_rate_pct": 5.0,
                 "spam_blocked_rate_pct": 2.0, "unsubscribe_rate_pct": 1.1},
                {"name": "Nurturing Mid-Market", "active": False,
                 "unique_scheduled": 300, "unique_delivered": 286,
                 "unique_opened": 102, "unique_replied": 12,
                 "unique_bounced": 17, "unique_hard_bounced": 4,
                 "unique_soft_bounced": 13, "unique_spam_blocked": 2,
                 "unique_unsubscribed": 1,
                 "delivery_rate_pct": 95.3, "open_rate_pct": 35.7,
                 "reply_rate_pct": 4.2, "bounce_rate_pct": 5.7,
                 "hard_bounce_rate_pct": 1.3, "soft_bounce_rate_pct": 4.3,
                 "spam_blocked_rate_pct": 0.7, "unsubscribe_rate_pct": 0.3},
            ],
        },
        "sequences_sample": [],  # preenchido automaticamente pelo collect_summary real
    }
    # Alinha sequences_sample com per_sequence para o analyzer
    mock_summary["sequences_sample"] = mock_summary["email_metrics"]["per_sequence"]

    result = run_full_analysis(mock_summary)
    print(json.dumps(result, indent=2, ensure_ascii=False))

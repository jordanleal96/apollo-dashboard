"""
apollo_collector.py
Coleta dados da API do Apollo.io: pessoas, organizações, sequências e métricas de e-mail.

Campos de entregabilidade disponíveis na API do Apollo:
  - unique_scheduled      : e-mails agendados/disparados
  - unique_delivered      : chegaram ao servidor do destinatário (não bounced)
  - unique_opened         : abertos (rastreado por pixel)
  - unique_replied        : respondidos
  - unique_hard_bounced   : endereço inválido / domínio inexistente
  - unique_soft_bounced   : caixa cheia / servidor temporariamente indisponível
  - unique_bounced        : total de bounces (hard + soft)
  - unique_unsubscribed   : descadastros via link
  - unique_spam_blocked   : bloqueados por filtro antes da entrega (reportado pelo servidor receptor)

NOTA sobre spam: a API informa e-mails BLOQUEADOS antes da entrega (spam_blocked),
não se o e-mail caiu na pasta spam do destinatário — isso exigiria acesso à caixa do
destinatário, o que nenhuma ESP disponibiliza. Alta bounce rate e baixa open rate são
os melhores sinais indiretos de problemas de entregabilidade.
"""

import os
import requests
from pathlib import Path

# Carrega .env se existir
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")
BASE_URL = "https://api.apollo.io/v1"

HEADERS = {
    "Content-Type": "application/json",
    "X-Api-Key": APOLLO_API_KEY,
}


def _post(endpoint: str, payload: dict) -> dict:
    headers = {**HEADERS, "X-Api-Key": APOLLO_API_KEY}
    response = requests.post(f"{BASE_URL}/{endpoint}", json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def get_people(page: int = 1, per_page: int = 25, **filters) -> dict:
    """Busca contatos no Apollo com filtros opcionais."""
    payload = {"page": page, "per_page": per_page, **filters}
    return _post("mixed_people/api_search", payload)


def get_organizations(page: int = 1, per_page: int = 25, **filters) -> dict:
    """Busca organizações no Apollo com filtros opcionais."""
    payload = {"page": page, "per_page": per_page, **filters}
    return _post("mixed_companies/search", payload)


def get_email_accounts() -> dict:
    """Lista as contas de e-mail conectadas."""
    return _post("email_accounts", {})


def get_sequences(page: int = 1, per_page: int = 25) -> dict:
    """Lista as sequências com todos os campos de entregabilidade."""
    payload = {"page": page, "per_page": per_page}
    return _post("emailer_campaigns/search", payload)


def get_email_messages(
    page: int = 1,
    per_page: int = 100,
    status: list[str] | None = None,
    emailer_campaign_id: str | None = None,
) -> dict:
    """
    Busca mensagens de e-mail individuais com status detalhado.
    status pode ser: ["sent", "delivered", "opened", "replied",
                      "bounced", "hard_bounced", "soft_bounced",
                      "unsubscribed", "spam_blocked"]
    """
    payload: dict = {"page": page, "per_page": per_page}
    if status:
        payload["status"] = status
    if emailer_campaign_id:
        payload["emailer_campaign_id"] = emailer_campaign_id
    return _post("emailer_messages/search", payload)


def _calc_rates(s: dict) -> dict:
    """
    Calcula todas as taxas percentuais de uma sequência.
    Usa campos reais da API Apollo: unique_soft_bounced = unique_bounced - unique_hard_bounced
    (a API não retorna unique_soft_bounced diretamente).
    Usa também as taxas pré-calculadas pela Apollo quando disponíveis.
    """
    def _int(v):
        try:
            return int(v) if v is not None else 0
        except (TypeError, ValueError):
            return 0

    scheduled = _int(s.get("unique_scheduled"))
    delivered = _int(s.get("unique_delivered"))
    opened    = _int(s.get("unique_opened"))
    replied   = _int(s.get("unique_replied"))
    bounced   = _int(s.get("unique_bounced"))
    hard_b    = _int(s.get("unique_hard_bounced"))
    soft_b    = max(bounced - hard_b, 0)   # API não retorna soft bounce diretamente
    spam_b    = _int(s.get("unique_spam_blocked"))
    unsub     = _int(s.get("unique_unsubscribed"))

    def pct(num, den):
        return round(num / den * 100, 1) if den else 0.0

    return {
        "unique_scheduled":      scheduled,
        "unique_delivered":      delivered,
        "unique_opened":         opened,
        "unique_replied":        replied,
        "unique_bounced":        bounced,
        "unique_hard_bounced":   hard_b,
        "unique_soft_bounced":   soft_b,
        "unique_spam_blocked":   spam_b,
        "unique_unsubscribed":   unsub,
        # Taxas calculadas
        "delivery_rate_pct":     pct(delivered, scheduled),
        "open_rate_pct":         pct(opened, delivered),
        "reply_rate_pct":        pct(replied, delivered),
        "bounce_rate_pct":       pct(bounced, scheduled),
        "hard_bounce_rate_pct":  pct(hard_b, scheduled),
        "soft_bounce_rate_pct":  pct(soft_b, scheduled),
        "spam_blocked_rate_pct": pct(spam_b, scheduled),
        "unsubscribe_rate_pct":  pct(unsub, delivered),
    }


def get_email_deliverability_report(per_page: int = 50) -> dict:
    """
    Agrega métricas de entregabilidade de todas as sequências.
    Retorna totais globais + detalhamento por sequência.
    """
    seq_data = get_sequences(per_page=per_page)
    sequences = seq_data.get("emailer_campaigns", [])

    totals = {
        "unique_scheduled": 0,
        "unique_delivered": 0,
        "unique_opened": 0,
        "unique_replied": 0,
        "unique_bounced": 0,
        "unique_hard_bounced": 0,
        "unique_soft_bounced": 0,
        "unique_spam_blocked": 0,
        "unique_unsubscribed": 0,
    }

    per_sequence = []
    for s in sequences:
        rates = _calc_rates(s)
        for key in totals:
            totals[key] += rates.get(key, 0)
        per_sequence.append({
            "id":     s.get("id"),
            "name":   s.get("name"),
            "active": s.get("active"),
            **rates,
        })

    # Taxas globais
    sch = totals["unique_scheduled"]
    del_ = totals["unique_delivered"]

    def pct(n, d):
        return round(n / d * 100, 1) if d else 0.0

    global_rates = {
        "delivery_rate_pct":     pct(del_, sch),
        "open_rate_pct":         pct(totals["unique_opened"], del_),
        "reply_rate_pct":        pct(totals["unique_replied"], del_),
        "bounce_rate_pct":       pct(totals["unique_bounced"], sch),
        "hard_bounce_rate_pct":  pct(totals["unique_hard_bounced"], sch),
        "soft_bounce_rate_pct":  pct(totals["unique_soft_bounced"], sch),
        "spam_blocked_rate_pct": pct(totals["unique_spam_blocked"], sch),
        "unsubscribe_rate_pct":  pct(totals["unique_unsubscribed"], del_),
    }

    return {
        "totals": {**totals, **global_rates},
        "per_sequence": per_sequence,
    }


def collect_summary(
    people_filters: dict | None = None,
    org_filters: dict | None = None,
    per_page: int = 25,
) -> dict:
    """
    Coleta resumo completo: pessoas, organizações, sequências e métricas de e-mail.
    """
    people_filters = people_filters or {}
    org_filters = org_filters or {}

    print("[Apollo] Coletando contatos...")
    people_data = get_people(per_page=per_page, **people_filters)

    print("[Apollo] Coletando organizações...")
    org_data = get_organizations(per_page=per_page, **org_filters)

    print("[Apollo] Coletando métricas de e-mail...")
    email_report = get_email_deliverability_report(per_page=per_page)

    people = people_data.get("people", [])
    organizations = org_data.get("organizations", [])

    summary = {
        "totals": {
            # mixed_people/api_search retorna total_entries direto (sem pagination)
            "people": people_data.get("total_entries", len(people)),
            # mixed_companies/search retorna dentro de pagination
            "organizations": org_data.get("pagination", {}).get("total_entries", len(organizations)),
            "sequences": len(email_report["per_sequence"]),
        },
        "people_sample": [
            {
                "name": p.get("name"),
                "title": p.get("title"),
                "organization": p.get("organization", {}).get("name") if p.get("organization") else None,
                "seniority": p.get("seniority"),
                "city": p.get("city"),
                "state": p.get("state"),
                "country": p.get("country"),
                "email_status": p.get("email_status"),
                "linkedin_url": p.get("linkedin_url"),
            }
            for p in people
        ],
        "organizations_sample": [
            {
                "name": o.get("name"),
                "industry": o.get("industry"),
                "employee_count": o.get("estimated_num_employees"),
                "city": o.get("city"),
                "country": o.get("country"),
                "annual_revenue": o.get("annual_revenue_printed"),
                "technology_names": o.get("technology_names", [])[:5],
            }
            for o in organizations
        ],
        "email_metrics": email_report,
        # Mantido para compatibilidade com analyzer
        "sequences_sample": email_report["per_sequence"],
    }

    print(f"[Apollo] Coleta concluída: {summary['totals']}")
    return summary


if __name__ == "__main__":
    import json

    print("=== Relatório de entregabilidade ===")
    report = get_email_deliverability_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))


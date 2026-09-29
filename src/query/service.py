"""Small framework-free service facade for frontend integration."""

from __future__ import annotations

from src.query.queries import (
    QueryResponse,
    get_loan_profile,
    get_loan_timeline,
    get_model_diagnostics,
    get_pd_results,
    get_portfolio_summary,
    get_risk_driver_results,
    get_survival_results,
    get_vintage_results,
)
from src.results.manifest import PathSource


class FrontendService:
    def __init__(self, repository_root: PathSource = ".") -> None:
        self.repository_root = repository_root

    def get_portfolio_summary(self) -> QueryResponse:
        return get_portfolio_summary(self.repository_root)

    def get_pd_results(self) -> QueryResponse:
        return get_pd_results(self.repository_root)

    def get_survival_results(self) -> QueryResponse:
        return get_survival_results(self.repository_root)

    def get_risk_driver_results(self) -> QueryResponse:
        return get_risk_driver_results(self.repository_root)

    def get_vintage_results(self) -> QueryResponse:
        return get_vintage_results(self.repository_root)

    def get_model_diagnostics(self) -> QueryResponse:
        return get_model_diagnostics(self.repository_root)

    def get_loan_profile(self, loan_id: str) -> QueryResponse:
        return get_loan_profile(loan_id, self.repository_root)

    def get_loan_timeline(self, loan_id: str) -> QueryResponse:
        return get_loan_timeline(loan_id, self.repository_root)


__all__ = ["FrontendService"]
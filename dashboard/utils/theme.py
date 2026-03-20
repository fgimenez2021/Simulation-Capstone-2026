"""Shared visual constants for the dashboard."""

TRADFI_COLOR = "#60a5fa"
TOKENIZED_COLOR = "#fb923c"

ROUTE_COLORS = {"TRADFI": TRADFI_COLOR, "TOKENIZED": TOKENIZED_COLOR}
ROUTE_LABELS = {"TRADFI": "TradFi", "TOKENIZED": "Tokenized"}

SCENARIO_LABELS = {"BASELINE": "Baseline", "STRESS": "Stress"}
ASSET_LABELS = {
    "TBILL_MMF": "T-Bill / MMF",
    "PRIVATE_CREDIT": "Private Credit",
}

CATEGORY_COLORS = {
    "onboarding": "#3b82f6",
    "compliance": "#f59e0b",
    "execution": "#10b981",
    "settlement": "#06b6d4",
    "custody": "#8b5cf6",
    "servicing": "#6366f1",
    "transfer": "#f97316",
    "exit": "#ef4444",
    "exception": "#9ca3af",
}

STAGE_META = {
    "ONBOARDING":           {"label": "Onboarding",           "category": "onboarding"},
    "KYC_REVIEW":           {"label": "KYC Review",           "category": "compliance"},
    "ELIGIBILITY_GATE":     {"label": "Eligibility Gate",     "category": "compliance"},
    "ORDER_PLACEMENT":      {"label": "Order Placement",      "category": "execution"},
    "EXECUTION":            {"label": "Execution",            "category": "execution"},
    "CLEARING_SETTLEMENT":  {"label": "Clearing & Settlement","category": "settlement"},
    "CUSTODY_RECORDING":    {"label": "Custody / Recording",  "category": "custody"},
    "SERVICING_REPORTING":  {"label": "Servicing & Reporting","category": "servicing"},
    "TRANSFERABILITY":      {"label": "Transferability",      "category": "transfer"},
    "EXIT_INITIATION":      {"label": "Exit Initiation",      "category": "exit"},
    "REDEMPTION_PROCESSING":{"label": "Redemption Processing","category": "exit"},
    "EXCEPTION_HANDLING":   {"label": "Exception Handling",   "category": "exception"},
}

STAGE_ORDER = list(STAGE_META.keys())

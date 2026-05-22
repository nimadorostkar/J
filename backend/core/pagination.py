# === FILE: backend/core/pagination.py ===
from rest_framework.pagination import CursorPagination as DRFCursor


class CursorPagination(DRFCursor):
    page_size = 20
    page_size_query_param = "limit"
    max_page_size = 100
    ordering = "-created_at"

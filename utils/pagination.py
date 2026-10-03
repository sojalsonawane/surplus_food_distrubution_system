"""
Pagination helper for database queries.
Provides clean page calculation, offset management, and Jinja-friendly page iteration.
"""

import math


class Pagination:
    def __init__(self, page, per_page, total_items):
        self.page = max(1, int(page))
        self.per_page = max(1, int(per_page))
        self.total_items = max(0, int(total_items))
        self.total_pages = max(1, math.ceil(self.total_items / self.per_page))

        # Adjust page if out of bounds
        if self.page > self.total_pages and self.total_items > 0:
            self.page = self.total_pages

        self.offset = (self.page - 1) * self.per_page
        self.has_prev = self.page > 1
        self.has_next = self.page < self.total_pages
        self.prev_page = self.page - 1 if self.has_prev else None
        self.next_page = self.page + 1 if self.has_next else None

    def iter_pages(self, left_edge=1, left_current=2, right_current=2, right_edge=1):
        """Yield page numbers with ellipsis markers for rendering navigation bars."""
        last = 0
        for num in range(1, self.total_pages + 1):
            if (
                num <= left_edge
                or (self.page - left_current <= num <= self.page + right_current)
                or num > self.total_pages - right_edge
            ):
                if last + 1 != num:
                    yield None  # Render ellipsis '...'
                yield num
                last = num

from __future__ import annotations

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import TextClause


class _NormalizedLowerTrim(TextClause):
    inherit_cache = True

    def __init__(self, column_name: str) -> None:
        self.column_name = column_name
        super().__init__(f"lower(trim({column_name}))")


@compiles(_NormalizedLowerTrim, "postgresql")
def _compile_postgresql_index_expression(
    element: _NormalizedLowerTrim, _compiler: object, **_kwargs: object
) -> str:
    return f"lower(TRIM(BOTH FROM {element.column_name}))"


def normalized_lower_trim(column_name: str) -> TextClause:
    return _NormalizedLowerTrim(column_name)
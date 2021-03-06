import decimal

import pandas as pd
import pytest

import ibis
from ibis import literal as L


@pytest.mark.parametrize(
    ('expr', 'expected'),
    [
        (ibis.NA.fillna(5), 5),
        (L(5).fillna(10), 5),
        (L(5).nullif(5), None),
        (L(10).nullif(5), 10),
    ],
)
@pytest.mark.xfail_unsupported
def test_fillna_nullif(backend, con, expr, expected):
    if expected is None:
        # The exact kind of null value used differs per backend (and version).
        # Example 1: Pandas returns np.nan while BigQuery returns None.
        # Example 2: PySpark returns np.nan if pyspark==3.0.0, but returns None
        # if pyspark <=3.0.0.
        # TODO: Make this behavior consistent (#2365)
        assert pd.isna(con.execute(expr))
    else:
        assert con.execute(expr) == expected


@pytest.mark.parametrize(
    ('expr', 'expected'),
    [
        (ibis.coalesce(5, None, 4), 5),
        (ibis.coalesce(ibis.NA, 4, ibis.NA), 4),
        (ibis.coalesce(ibis.NA, ibis.NA, 3.14), 3.14),
    ],
)
@pytest.mark.xfail_unsupported
def test_coalesce(backend, con, expr, expected):
    result = con.execute(expr)

    if isinstance(result, decimal.Decimal):
        # in case of Impala the result is decimal
        # >>> decimal.Decimal('5.56') == 5.56
        # False
        assert result == decimal.Decimal(str(expected))
    else:
        assert result == expected


@pytest.mark.skip_backends(['dask'])  # TODO - identicalTo - #2553
@pytest.mark.xfail_unsupported
def test_identical_to(backend, alltypes, con, sorted_df):
    sorted_alltypes = alltypes.sort_by('id')
    df = sorted_df
    dt = df[['tinyint_col', 'double_col']]

    ident = sorted_alltypes.tinyint_col.identical_to(
        sorted_alltypes.double_col
    )
    expr = sorted_alltypes['id', ident.name('tmp')].sort_by('id')
    result = expr.execute().tmp

    expected = (dt.tinyint_col.isnull() & dt.double_col.isnull()) | (
        dt.tinyint_col == dt.double_col
    )

    expected = backend.default_series_rename(expected)
    backend.assert_series_equal(result, expected)


@pytest.mark.parametrize(
    ('column', 'elements'),
    [
        ('int_col', [1, 2, 3]),
        ('int_col', (1, 2, 3)),
        ('string_col', ['1', '2', '3']),
        ('string_col', ('1', '2', '3')),
        ('int_col', {1}),
        ('int_col', frozenset({1})),
    ],
)
@pytest.mark.xfail_unsupported
def test_isin(backend, alltypes, sorted_df, column, elements):
    sorted_alltypes = alltypes.sort_by('id')
    expr = sorted_alltypes[
        'id', sorted_alltypes[column].isin(elements).name('tmp')
    ].sort_by('id')
    result = expr.execute().tmp

    expected = sorted_df[column].isin(elements)
    expected = backend.default_series_rename(expected)
    backend.assert_series_equal(result, expected)


@pytest.mark.parametrize(
    ('column', 'elements'),
    [
        ('int_col', [1, 2, 3]),
        ('int_col', (1, 2, 3)),
        ('string_col', ['1', '2', '3']),
        ('string_col', ('1', '2', '3')),
        ('int_col', {1}),
        ('int_col', frozenset({1})),
    ],
)
@pytest.mark.xfail_unsupported
def test_notin(backend, alltypes, sorted_df, column, elements):
    sorted_alltypes = alltypes.sort_by('id')
    expr = sorted_alltypes[
        'id', sorted_alltypes[column].notin(elements).name('tmp')
    ].sort_by('id')
    result = expr.execute().tmp

    expected = ~sorted_df[column].isin(elements)
    expected = backend.default_series_rename(expected)
    backend.assert_series_equal(result, expected)


@pytest.mark.parametrize(
    ('predicate_fn', 'expected_fn'),
    [
        (lambda t: t['bool_col'], lambda df: df['bool_col']),
        (lambda t: ~t['bool_col'], lambda df: ~df['bool_col']),
    ],
)
@pytest.mark.skip_backends(['dask'])  # TODO - sorting - #2553
@pytest.mark.xfail_unsupported
def test_filter(backend, alltypes, sorted_df, predicate_fn, expected_fn):
    sorted_alltypes = alltypes.sort_by('id')
    table = sorted_alltypes[predicate_fn(sorted_alltypes)].sort_by('id')
    result = table.execute()
    expected = sorted_df[expected_fn(sorted_df)]

    backend.assert_frame_equal(result, expected)


@pytest.mark.xfail_unsupported
def test_case_where(backend, alltypes, df):
    table = alltypes
    table = table.mutate(
        new_col=(
            ibis.case()
            .when(table['int_col'] == 1, 20)
            .when(table['int_col'] == 0, 10)
            .else_(0)
            .end()
            .cast('int64')
        )
    )

    result = table.execute()

    expected = df.copy()
    mask_0 = expected['int_col'] == 1
    mask_1 = expected['int_col'] == 0

    expected['new_col'] = 0
    expected['new_col'][mask_0] = 20
    expected['new_col'][mask_1] = 10
    expected['new_col'] = expected['new_col']

    backend.assert_frame_equal(result, expected)

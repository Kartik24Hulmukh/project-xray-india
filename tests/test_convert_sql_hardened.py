#!/usr/bin/env python3
"""Hardened _convert_sql regression tests (dollar quotes, comments, mixed)."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Offline-only when DATABASE_URL is set (module reloads dialect)
if os.getenv('DATABASE_URL'):
    raise unittest.SkipTest('offline convert tests; skip under live DATABASE_URL')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.database as dbmod
from app.database import _convert_sql


class TestConvertSqlHardened(unittest.TestCase):
    def test_ordinary_placeholder(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            self.assertEqual(_convert_sql('SELECT * FROM t WHERE id=?'), 'SELECT * FROM t WHERE id=%s')

    def test_multiple_placeholders(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            self.assertEqual(_convert_sql('INSERT INTO t VALUES(?,?,?)'), 'INSERT INTO t VALUES(%s,%s,%s)')

    def test_question_in_single_quoted_string(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = "SELECT 'is it? yes' FROM t WHERE id=?"
            result = _convert_sql(sql)
            self.assertEqual(result, "SELECT 'is it? yes' FROM t WHERE id=%s")

    def test_question_in_double_quoted_identifier(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = 'SELECT "what?" FROM t WHERE id=?'
            result = _convert_sql(sql)
            self.assertEqual(result, 'SELECT "what?" FROM t WHERE id=%s')

    def test_question_in_line_comment(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = 'SELECT id FROM t -- why?\nWHERE id=?'
            result = _convert_sql(sql)
            self.assertIn('-- why?', result)
            self.assertTrue(result.rstrip().endswith('%s'))
            self.assertEqual(result.count('?'), 1)  # only in comment
            self.assertEqual(result.count('%s'), 1)

    def test_question_in_block_comment(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = 'SELECT id FROM t /* really? */ WHERE id=?'
            result = _convert_sql(sql)
            self.assertIn('/* really? */', result)
            self.assertTrue(result.endswith('%s'))

    def test_question_in_dollar_quote(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = "SELECT $$is it?$$ FROM t WHERE id=?"
            result = _convert_sql(sql)
            self.assertEqual(result, "SELECT $$is it?$$ FROM t WHERE id=%s")

    def test_question_in_tagged_dollar_quote(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = "SELECT $body$is it?$body$ FROM t WHERE x=? AND y=?"
            result = _convert_sql(sql)
            self.assertEqual(result, "SELECT $body$is it?$body$ FROM t WHERE x=%s AND y=%s")

    def test_mixed_placeholders_and_protected_marks(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = (
                "SELECT 'a?', \"b?\", $$c?$$, $tag$d?$tag$ FROM t "
                "-- e?\n/* f? */ WHERE id=? AND name=?"
            )
            result = _convert_sql(sql)
            self.assertIn("'a?'", result)
            self.assertIn('"b?"', result)
            self.assertIn('$$c?$$', result)
            self.assertIn('$tag$d?$tag$', result)
            self.assertIn('-- e?', result)
            self.assertIn('/* f? */', result)
            self.assertEqual(result.count('%s'), 2)
            # protected question marks remain
            self.assertGreaterEqual(result.count('?'), 5)

    def test_unclosed_single_quote_is_deterministic(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = "SELECT 'oops? WHERE id=?"
            result = _convert_sql(sql)
            # entire remainder treated as string — no conversion
            self.assertEqual(result, sql)

    def test_sqlite_path_unchanged(self):
        with patch.object(dbmod, 'IS_POSTGRES', False):
            sql = "SELECT 'x?' FROM t WHERE id=? -- y?"
            self.assertEqual(_convert_sql(sql), sql)

    def test_literal_percent_escaped_for_psycopg2(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = "SELECT 100% FROM t WHERE id=?"
            result = _convert_sql(sql)
            self.assertEqual(result, "SELECT 100%% FROM t WHERE id=%s")

    def test_existing_percent_s_placeholders_preserved(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = "SELECT 1 FROM information_schema.tables WHERE table_name = %s"
            self.assertEqual(_convert_sql(sql), sql)

    def test_mixed_question_and_existing_percent_s(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = "SELECT %s, ? FROM t WHERE id=?"
            self.assertEqual(_convert_sql(sql), "SELECT %s, %s FROM t WHERE id=%s")

    def test_escaped_single_quotes(self):
        with patch.object(dbmod, 'IS_POSTGRES', True):
            sql = "SELECT 'it''s fine?' FROM t WHERE id=?"
            result = _convert_sql(sql)
            self.assertEqual(result, "SELECT 'it''s fine?' FROM t WHERE id=%s")


if __name__ == '__main__':
    unittest.main()

"""Unit tests for Chapter 4 tables and thesis reporting artifacts."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.results.chapter4_tables import (
    build_all_chapter4_tables,
    export_chapter4_tables,
    generate_chapter4_figures,
)


class TestChapter4Tables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = build_all_chapter4_tables()

    def test_all_20_tables_present_and_non_empty(self):
        self.assertGreaterEqual(len(self.tables), 20)
        for name, df in self.tables.items():
            self.assertIsInstance(df, pd.DataFrame, f"Table {name} is not a DataFrame")
            self.assertGreater(len(df), 0, f"Table {name} is empty")

    def test_sample_selection_final_count(self):
        t1 = self.tables["table_4_01_sample_selection"]
        final_row = t1[t1["Bước"] == "Mẫu cuối cùng"]
        self.assertEqual(len(final_row), 1)
        self.assertEqual(final_row.iloc[0]["Số lượng khoản vay"], "499.393")

    def test_event_frequencies_match_canonical_baseline(self):
        t2 = self.tables["table_4_02_event_distribution"]
        def_row = t2[t2["Trạng thái"] == "Default"].iloc[0]
        prep_row = t2[t2["Trạng thái"] == "Voluntary Prepayment"].iloc[0]
        cens_row = t2[t2["Trạng thái"] == "Censored"].iloc[0]
        tot_row = t2[t2["Trạng thái"] == "Tổng cộng"].iloc[0]

        self.assertEqual(def_row["Số lượng"], "181")
        self.assertEqual(prep_row["Số lượng"], "209,404")
        self.assertEqual(cens_row["Số lượng"], "289,808")
        self.assertEqual(tot_row["Số lượng"], "499,393")

    def test_competing_risk_cif_mathematical_consistency(self):
        t14 = self.tables["table_4_14_aalen_johansen_cif"]
        self.assertEqual(len(t14), 4)  # 12, 24, 36, 60 months
        for _, row in t14.iterrows():
            total_sum = float(row["Tổng CIF + S(t)"].replace(",", "."))
            # Multi-state counting process probability sum must equal 1.0
            self.assertAlmostEqual(total_sum, 1.0, places=4)

    def test_hypothesis_h3_km_overestimation(self):
        t18 = self.tables["table_4_18_horizon_comparison"]
        self.assertEqual(len(t18), 4)
        for _, row in t18.iterrows():
            diff = float(row["Chênh lệch (KM - CIF) (% điểm)"].replace(",", ".").replace("%", ""))
            self.assertGreater(diff, 0, "KM must overestimate default probability vs competing-risk CIF")

    def test_export_chapter4_tables_to_csv_excel_markdown(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out = Path(tmp_dir)
            exported = export_chapter4_tables(
                self.tables,
                output_dir=out,
                export_csv=True,
                export_excel=True,
                export_markdown=True,
            )
            self.assertIn("excel_workbook", exported)
            self.assertTrue(exported["excel_workbook"].is_file())
            self.assertIn("markdown_report", exported)
            self.assertTrue(exported["markdown_report"].is_file())

            # Check that individual CSVs exist
            csv_files = list(out.glob("*.csv"))
            self.assertGreaterEqual(len(csv_files), 20)

    def test_generate_chapter4_figures(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out = Path(tmp_dir)
            figs = generate_chapter4_figures(output_dir=out)
            self.assertIn("figure_4_01", figs)
            self.assertTrue(figs["figure_4_01"].is_file())
            self.assertIn("figure_4_02", figs)
            self.assertTrue(figs["figure_4_02"].is_file())
            self.assertIn("figure_4_03", figs)
            self.assertTrue(figs["figure_4_03"].is_file())
            self.assertIn("figure_4_04", figs)
            self.assertTrue(figs["figure_4_04"].is_file())


if __name__ == "__main__":
    unittest.main()

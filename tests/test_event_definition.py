import unittest
from datetime import date

import polars as pl

from src.data.event_definition import (
    build_event_mapping,
)


class TestEventDefinition(unittest.TestCase):

    def setUp(self):

        # =================================================
        # ORIGINATION MOCK DATA
        # =================================================

        self.orig = pl.DataFrame(
            {
                "loan_id": [
                    "L_DEFAULT",
                    "L_PREPAY",
                    "L_CENSOR",
                    "L_RA",
                    "L_ZB03",
                    "L_CONFLICT",
                    "L_ADMIN",
                ],

                "vintage_year": [
                    2020,
                    2020,
                    2020,
                    2020,
                    2020,
                    2020,
                    2020,
                ],

                "first_payment_month": [
                    date(2020, 1, 1),
                    date(2020, 1, 1),
                    date(2020, 1, 1),
                    date(2020, 1, 1),
                    date(2020, 1, 1),
                    date(2020, 1, 1),
                    date(2020, 1, 1),
                ],

                "maturity_month": [
                    date(2050, 1, 1),
                    date(2050, 1, 1),
                    date(2050, 1, 1),
                    date(2050, 1, 1),
                    date(2050, 1, 1),
                    date(2050, 1, 1),
                    date(2050, 1, 1),
                ],
            }
        ).lazy()


        # =================================================
        # PERFORMANCE MOCK DATA
        # =================================================

        self.perf = pl.DataFrame(
            {
                "loan_id": [

                    # DEFAULT via first 90+
                    "L_DEFAULT",
                    "L_DEFAULT",

                    # PREPAYMENT
                    "L_PREPAY",
                    "L_PREPAY",

                    # RIGHT CENSOR
                    "L_CENSOR",
                    "L_CENSOR",

                    # DEFAULT fallback via RA
                    "L_RA",
                    "L_RA",

                    # DEFAULT fallback via ZB03
                    "L_ZB03",
                    "L_ZB03",

                    # DEFAULT and PREPAY same month
                    "L_CONFLICT",
                    "L_CONFLICT",

                    # ADMIN CENSOR
                    "L_ADMIN",
                    "L_ADMIN",
                ],

                "reporting_period_num": [
                    202001,
                    202002,

                    202001,
                    202002,

                    202001,
                    202002,

                    202001,
                    202002,

                    202001,
                    202002,

                    202001,
                    202002,

                    202001,
                    202002,
                ],

                "delinquency_num": [
                    0,
                    3,

                    0,
                    0,

                    0,
                    0,

                    0,
                    None,

                    0,
                    1,

                    0,
                    3,

                    0,
                    0,
                ],

                "is_ra": [
                    False,
                    False,

                    False,
                    False,

                    False,
                    False,

                    False,
                    True,

                    False,
                    False,

                    False,
                    False,

                    False,
                    False,
                ],

                "zero_balance_code": [
                    None,
                    None,

                    None,
                    "01",

                    None,
                    None,

                    None,
                    None,

                    None,
                    "03",

                    None,
                    "01",

                    None,
                    "15",
                ],

                "zero_balance_effective_date": [
                    None,
                    None,

                    None,
                    "202002",

                    None,
                    None,

                    None,
                    None,

                    None,
                    "202002",

                    None,
                    "202002",

                    None,
                    "202002",
                ],

                "zero_balance_effective_month": [
                    None,
                    None,

                    None,
                    date(2020, 2, 1),

                    None,
                    None,

                    None,
                    None,

                    None,
                    date(2020, 2, 1),

                    None,
                    date(2020, 2, 1),

                    None,
                    date(2020, 2, 1),
                ],

                "remaining_months_maturity": [
                    360,
                    359,

                    360,
                    358,

                    360,
                    359,

                    360,
                    359,

                    360,
                    359,

                    360,
                    358,

                    360,
                    359,
                ],
            }
        ).lazy()


    def _result(self):

        return (
            build_event_mapping(
                self.orig,
                self.perf,
            )
            .collect()
        )


    def _loan(
        self,
        loan_id: str,
    ):

        return (
            self._result()
            .filter(
                pl.col(
                    "loan_id"
                )
                == loan_id
            )
            .to_dicts()[0]
        )


    # =====================================================
    # TEST PRIMARY DEFAULT
    # =====================================================

    def test_d90_default(self):

        loan = self._loan(
            "L_DEFAULT"
        )

        self.assertEqual(
            loan["event_type"],
            "DEFAULT",
        )

        self.assertEqual(
            loan["event_month"],
            202002,
        )

        self.assertEqual(
            loan["event_source"],
            "D90",
        )


    # =====================================================
    # TEST PREPAYMENT
    # =====================================================

    def test_prepayment(self):

        loan = self._loan(
            "L_PREPAY"
        )

        self.assertEqual(
            loan["event_type"],
            "PREPAYMENT",
        )

        self.assertEqual(
            loan["event_month"],
            202002,
        )

        self.assertEqual(
            loan["raw_zero_balance_code"],
            "01",
        )


    # =====================================================
    # TEST RIGHT CENSOR
    # =====================================================

    def test_right_censor(self):

        loan = self._loan(
            "L_CENSOR"
        )

        self.assertEqual(
            loan["event_type"],
            "CENSOR",
        )

        self.assertEqual(
            loan["event_source"],
            "RIGHT_CENSOR",
        )

        self.assertEqual(
            loan["event_month"],
            202002,
        )


    # =====================================================
    # TEST RA FALLBACK
    # =====================================================

    def test_ra_default(self):

        loan = self._loan(
            "L_RA"
        )

        self.assertEqual(
            loan["event_type"],
            "DEFAULT",
        )

        self.assertEqual(
            loan["event_source"],
            "RA",
        )


    # =====================================================
    # TEST CREDIT ZERO BALANCE FALLBACK
    # =====================================================

    def test_zb03_default(self):

        loan = self._loan(
            "L_ZB03"
        )

        self.assertEqual(
            loan["event_type"],
            "DEFAULT",
        )

        self.assertEqual(
            loan["event_source"],
            "ZB03",
        )

        self.assertEqual(
            loan["raw_zero_balance_code"],
            "03",
        )


    # =====================================================
    # TEST SAME MONTH CONFLICT
    # =====================================================

    def test_same_month_default_wins(self):

        loan = self._loan(
            "L_CONFLICT"
        )

        self.assertEqual(
            loan["event_type"],
            "DEFAULT",
        )

        self.assertTrue(
            loan[
                "same_month_default_prepay_flag"
            ]
        )


    # =====================================================
    # TEST ADMIN CENSOR
    # =====================================================

    def test_admin_censor(self):

        loan = self._loan(
            "L_ADMIN"
        )

        self.assertEqual(
            loan["event_type"],
            "CENSOR",
        )

        self.assertEqual(
            loan["event_source"],
            "ZB15_WHOLE_LOAN_SALE",
        )

        self.assertEqual(
            loan["raw_zero_balance_code"],
            "15",
        )


    # =====================================================
    # ONE ROW PER LOAN
    # =====================================================

    def test_one_row_per_loan(self):

        result = self._result()

        self.assertEqual(
            result.height,
            7,
        )

        self.assertEqual(
            result[
                "loan_id"
            ]
            .n_unique(),
            7,
        )


if __name__ == "__main__":
    unittest.main()
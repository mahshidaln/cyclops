"""MIMIC-IV query API.

Supports querying of MIMICIV-2.0.

"""

import logging

from sqlalchemy import Integer, func, select

import cyclops.query.ops as qo
from cyclops.query.base import DatasetQuerier
from cyclops.query.interface import QueryInterface
from cyclops.query.util import get_column
from cyclops.utils.log import setup_logging


# Logging.
LOGGER = logging.getLogger(__name__)
setup_logging(print_level="INFO", logger=LOGGER)


class MIMICIVQuerier(DatasetQuerier):
    """MIMICIV dataset querier."""

    def patients(
        self,
    ) -> QueryInterface:
        """Query MIMIC patient data.

        Returns
        -------
        cyclops.query.interface.QueryInterface
            Constructed query, wrapped in an interface object.

        Notes
        -----
        The function infers the approximate year a patient received care, using the
        `anchor_year` and `anchor_year_group` columns. The `join` and `ops` supplied
        are applied after the approximate year is inferred. `dod` is
        adjusted based on the inferred approximate year of care.

        """
        table = self.get_table("mimiciv_hosp", "patients")

        # Process and include patient's anchor year.
        table = select(
            table,
            (
                func.substr(get_column(table, "anchor_year_group"), 1, 4).cast(Integer)
            ).label("anchor_year_group_start"),
            (
                func.substr(get_column(table, "anchor_year_group"), 8, 12).cast(Integer)
            ).label("anchor_year_group_end"),
        ).subquery()

        # Select the middle of the anchor year group as the anchor year
        table = select(
            table,
            (
                get_column(table, "anchor_year_group_start")
                + (
                    get_column(table, "anchor_year_group_end")
                    - get_column(table, "anchor_year_group_start")
                )
                / 2
            ).label("anchor_year_group_middle"),
        ).subquery()

        table = select(
            table,
            (
                get_column(table, "anchor_year_group_middle")
                - get_column(table, "anchor_year")
            ).label("anchor_year_difference"),
        ).subquery()

        # Shift relevant columns by anchor year difference
        table = qo.AddDeltaColumn("dod", years="anchor_year_difference")(table)
        table = qo.Drop(
            [
                "anchor_year_group_start",
                "anchor_year_group_end",
                "anchor_year_group_middle",
            ],
        )(table)

        return QueryInterface(self.db, table)

    def diagnoses(
        self,
    ) -> QueryInterface:
        """Query MIMIC diagnosis data.

        Parameters
        ----------
        join
            Join arguments.
        ops
            Additional operations to apply to the query.

        Returns
        -------
        cyclops.query.interface.QueryInterface
            Constructed query, wrapped in an interface object.

        """
        table = self.get_table("mimiciv_hosp", "diagnoses_icd")

        # Join with diagnoses dimension table.
        table = qo.Join(
            join_table=self.get_table("mimiciv_hosp", "d_icd_diagnoses"),
            on=["icd_code", "icd_version"],
            on_to_type=["str", "int"],
        )(table)

        return QueryInterface(self.db, table)

    def labevents(
        self,
    ) -> QueryInterface:
        """Query lab events from the hospital module.

        Returns
        -------
        cyclops.query.interface.QueryInterface
            Constructed query, wrapped in an interface object.

        """
        table = self.get_table("mimiciv_hosp", "labevents")
        dim_items_table = self.get_table("mimiciv_hosp", "d_labitems")

        # Join with lab items dimension table.
        table = qo.Join(
            join_table=dim_items_table,
            on=["itemid"],
        )(table)

        return QueryInterface(self.db, table)

    def chartevents(
        self,
    ) -> QueryInterface:
        """Query ICU chart events from the ICU module.

        Returns
        -------
        cyclops.query.interface.QueryInterface
            Constructed table, wrapped in an interface object.

        """
        table = self.get_table("mimiciv_icu", "chartevents")
        dim_items_table = self.get_table("mimiciv_icu", "d_items")

        # Join with items dimension table.
        table = qo.Join(
            dim_items_table,
            on="itemid",
        )(table)

        return QueryInterface(self.db, table)

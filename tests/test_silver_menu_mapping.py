import csv
import re
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from pyspark.sql import SparkSession, functions as F


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "1_source_systems"


def notebook_cells(name):
    source = (ROOT / "fabric" / f"{name}.Notebook" / "notebook-content.py").read_text()
    return re.split(r"(?=^# (?:PARAMETERS )?CELL \*{20}$)", source, flags=re.M)[1:]


def run_notebook(name, spark, tables, parameters=None):
    namespace = {
        "spark": SimpleNamespace(
            table=lambda name: tables[name],
            sql=lambda query: spark.sql(query),
            createDataFrame=spark.createDataFrame,
        )
    }

    def save(df, table):
        tables[f"silver.{table}"] = df.withColumn(
            "_silver_batch_id", F.lit(namespace["BATCH_ID"])).cache()

    for cell in notebook_cells(name):
        exec(compile(cell, name, "exec"), namespace)
        if cell.startswith("# PARAMETERS CELL "):
            namespace.update(parameters or {})
        if "def save(" in cell:
            namespace["save"] = save
    return namespace


class SilverRunnerTests(unittest.TestCase):
    def test_runner_rejects_missing_or_different_output_batches(self):
        validation = notebook_cells("nb_silver_run_all")[-2]
        for batches in (["runner-batch"], ["child-batch"], [], [None],
                        ["runner-batch", "child-batch"]):
            with self.subTest(batches=batches), redirect_stdout(StringIO()):
                frame = SimpleNamespace(
                    select=lambda _: SimpleNamespace(distinct=lambda: SimpleNamespace(
                        collect=lambda: [(batch,) for batch in batches])))
                namespace = {"batch_id": "runner-batch",
                             "spark": SimpleNamespace(table=lambda _: frame)}
                if batches == ["runner-batch"]:
                    exec(compile(validation, "silver-runner", "exec"), namespace)
                else:
                    with self.assertRaisesRegex(AssertionError, "not written to all outputs"):
                        exec(compile(validation, "silver-runner", "exec"), namespace)

    def test_silver_and_gold_parameters_use_native_fabric_cells(self):
        names = ["nb_silver_master_data", "nb_silver_micros", "nb_silver_aloha",
                 "nb_silver_as400_commissary", "nb_silver_online_app",
                 "nb_gold_reference_data", "nb_gold_legacy", "nb_gold_run_legacy"]
        for name in names:
            with self.subTest(notebook=name):
                cells = notebook_cells(name)
                self.assertTrue(cells[0].startswith("# PARAMETERS CELL "))
                namespace = {}
                exec(compile(cells[0], name, "exec"), namespace)
                self.assertIn("batch_id", namespace)


class SilverMenuMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = TemporaryDirectory(prefix="silver-menu-tests-")
        cls.addClassCleanup(cls.workspace.cleanup)
        cls.spark = (SparkSession.builder.master("local[2]")
                     .appName("silver-menu-mapping-tests")
                     .config("spark.ui.enabled", "false")
                     .config("spark.sql.warehouse.dir", cls.workspace.name)
                     .config("spark.sql.shuffle.partitions", "2")
                     .getOrCreate())
        cls.spark.sparkContext.setLogLevel("ERROR")
        cls.addClassCleanup(cls.spark.stop)
        cls.tables = {}
        for stem in ("stores", "menu", "calendar", "recipes"):
            df = cls.spark.read.option("header", "true").csv(str(SOURCE / "master_data" / f"{stem}.csv"))
            cls.tables[f"bronze.master_{stem}"] = cls.with_meta(df)
        run_notebook("nb_silver_master_data", cls.spark, cls.tables)
        for file_name, table in (("CHECKS.csv", "aloha_checks"), ("ITEMS.csv", "aloha_items")):
            paths = [str(path) for path in sorted((SOURCE / "aloha").glob(f"*/*/{file_name}"))]
            df = cls.spark.read.option("header", "true").csv(paths)
            cls.tables[f"bronze.{table}"] = cls.with_meta(df)

    @staticmethod
    def with_meta(df):
        for name in ("_source_system", "_source_file", "_file_modified", "_ingest_ts", "_batch_id"):
            df = df.withColumn(name, F.lit("fixture"))
        return df

    def test_shared_menu_prices_preserve_all_aloha_lines(self):
        menu = self.tables["silver.menu"]
        self.assertEqual(menu.count(), 19)
        self.assertEqual(menu.select("price_excl_tax").distinct().count(), 17)
        run_notebook("nb_silver_aloha", self.spark, self.tables, {"batch_id": "runner-fixture"})
        lines = self.tables["silver.aloha_check_lines"]
        self.assertEqual([r[0] for r in lines.select("_silver_batch_id").distinct().collect()],
                         ["runner-fixture"])
        self.assertEqual(lines.count(), self.tables["bronze.aloha_items"].count())
        self.assertEqual(lines.count(), 7341)
        mappings = {
            (row.ITEMCODE, row.sku) for row in
            lines.filter("TYPE = 'ITEM'").select("ITEMCODE", "sku").distinct().collect()
        }
        for pair in (("LGPEP", "PZ-PEP-L"), ("MDMEAT", "PZ-MTL-M"),
                     ("MDVEG", "PZ-VEG-M"), ("WING10", "SD-WING10")):
            self.assertIn(pair, mappings)
        self.assertEqual(len(mappings), 19)
        self.assertEqual(lines.filter("is_item_unmapped OR is_duplicate_line").count(), 0)
        self.assertEqual(lines.filter("TYPE = 'COMP' AND sku IS NOT NULL").count(), 0)

    def test_unresolved_mapping_evidence_is_retained(self):
        with (SOURCE / "aloha" / "2207" / "20260309" / "ITEMS.csv").open() as file:
            template = next(csv.DictReader(file))
        cases = [
            ("LGPEP", "LG PEP", "15.81", "ITEM"),
            ("UNKNOWN", "LG PEP", "15.81", "ITEM"),
            ("LGPEP", "MD MEAT", "15.81", "ITEM"),
            ("LGPEP", "LG PEP", "99.99", "ITEM"),
            ("2F1TUE", "2F1 TUES", "-15.81", "COMP"),
        ]
        rows = []
        for entry, (code, name, price, line_type) in enumerate(cases, 1):
            rows.append(dict(template, ENTRYID=str(entry), ITEMCODE=code, ITEMNAME=name,
                             PRICE=price, AMOUNT=price, TYPE=line_type))
        raw = self.with_meta(self.spark.createDataFrame(rows))
        tables = dict(self.tables, **{"bronze.aloha_items": raw})
        namespace = {
            "spark": SimpleNamespace(table=lambda name: tables[name],
                                     createDataFrame=self.spark.createDataFrame),
            "F": F,
            "META": ["_source_system", "_source_file", "_file_modified", "_ingest_ts", "_batch_id"],
        }
        from pyspark.sql import Window
        namespace["Window"] = Window
        namespace["parsed"] = lambda name, kind: F.expr(f"try_cast(trim(`{name}`) AS {kind})")
        item_cell = next(cell for cell in notebook_cells("nb_silver_aloha")
                         if "items_raw = " in cell)
        transform = item_cell.split("assert items.filter(", 1)[0]
        exec(compile(transform, "nb_silver_aloha", "exec"), namespace)
        items = {row.entry_id: row for row in namespace["items"].collect()}
        self.assertEqual(len(items), len(cases))
        self.assertEqual(items[1].sku, "PZ-PEP-L")
        self.assertTrue(items[2].is_item_unmapped)
        self.assertTrue(items[3].is_item_name_mismatch)
        self.assertTrue(items[4].is_item_price_mismatch)
        for entry in (2, 3, 4, 5):
            self.assertIsNone(items[entry].sku)
        self.assertTrue(items[5].is_comp)
        self.assertFalse(items[5].is_item_unmapped)
        diagnostics = StringIO()
        with redirect_stdout(diagnostics), self.assertRaisesRegex(
                AssertionError, "3 Aloha item lines have unresolved menu mappings"):
            exec(compile(item_cell[len(transform):], "nb_silver_aloha", "exec"), namespace)
        self.assertIn("UNKNOWN", diagnostics.getvalue())


if __name__ == "__main__":
    unittest.main()

# Uploading the source files to the lakehouse (OneLake)

Fabric Git integration only syncs Fabric items (lakehouse definition, notebooks), **not data files**. The Bronze notebooks read from `Files/polar_slice/` in `lh_polarslice`, so upload the source files once.

Never upload `3_answer_key/`. It is not in this repo and must stay out of the pipeline.

## Target layout

Upload the *contents* of `data/1_source_systems/` into `Files/polar_slice/`:

```
Files/polar_slice/
  master_data/      stores.csv menu.csv calendar.csv recipes.csv
  micros/           check_header_YYYYMMDD.txt, check_detail_YYYYMMDD.txt (5 days each)
  aloha/<store>/<YYYYMMDD>/CHECKS.csv, ITEMS.csv     (3 stores x 5 days)
  online_app/       orders_20260309..20260314.json, customers.csv
  as400_commissary/ ITEMMAST.TXT, SHP*.TXT (3), CNT*.TXT (2), *.CPY
```
README.md files are optional (the notebooks ignore them).

## Option 1: Fabric UI
1. Open the workspace, then `lh_polarslice`.
2. In the Explorer, hover **Files** > `...` > **New subfolder** > `polar_slice`.
3. On `polar_slice` choose `...` > **Upload** > **Upload folder**, and select each of `master_data`, `micros`, `aloha`, `online_app`, `as400_commissary` from `data\1_source_systems\`.

## Option 2: OneLake file explorer
1. Install OneLake file explorer for Windows and sign in; the workspace appears in File Explorer.
2. Copy the five folders from `data\1_source_systems\` into
   `OneLake - <tenant>\<workspace>\lh_polarslice.Lakehouse\Files\polar_slice\`.
3. Wait for the sync icons to turn green.

## Option 3: azcopy
```powershell
azcopy login
azcopy copy "data\1_source_systems\*" `
  "https://onelake.dfs.fabric.microsoft.com/<workspace>/lh_polarslice.Lakehouse/Files/polar_slice/" `
  --recursive --exclude-pattern "README.md" --trusted-microsoft-suffixes "fabric.microsoft.com"
```
Use the workspace and lakehouse GUIDs in the URL if names contain spaces.

## Verify
In a notebook: `len(notebookutils.fs.ls("Files/polar_slice"))` should be 5 (folders). Expected data files: 4 master, 10 MICROS, 30 Aloha, 7 online, 6 AS/400 data files plus 3 copybooks.

## Run Bronze
Open `nb_bronze_run_all` (default lakehouse `lh_polarslice`) and run it. Tables appear in the `bronze` schema:

| Notebook | Tables |
|---|---|
| nb_bronze_master_data | master_stores, master_menu, master_calendar, master_recipes |
| nb_bronze_micros | micros_check_header, micros_check_detail |
| nb_bronze_aloha | aloha_checks, aloha_items |
| nb_bronze_online_app | online_orders, online_order_items, online_customers |
| nb_bronze_as400_commissary | as400_itemmast, as400_shipments, as400_counts |

If a notebook shows no default lakehouse after the first Git sync, re-attach `lh_polarslice` once.

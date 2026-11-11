# AS/400 commissary

The IBM i (AS/400) system that runs the central commissary, which ships dough, cheese and toppings to every store on Monday, Wednesday and Friday.

Every file is **fixed-width**: no separators, each field sits at a fixed character position, and the `.CPY` COBOL copybooks give the layout. Windows line endings (CRLF).

## Files

| File | Copybook | Line length | What it holds |
|---|---|---|---|
| ITEMMAST.TXT | ITEMREC.CPY | 47 | Ingredient list: code, description, base unit (KG or EA), base units per case, cost per case |
| SHP1260309.TXT, SHP1260311.TXT, SHP1260313.TXT | SHIPREC.CPY | 59 | One line per item shipped to a store that day: quantity, unit (CS or KG) and cost |
| CNT1260309.TXT | CNTREC.CPY | 31 | Opening stock count for every store and ingredient, before trading on 9 March |
| CNT1260313.TXT | CNTREC.CPY | 31 | Closing stock count, after trading on 13 March |

## Reading AS/400 files

- **Dates are CYYMMDD.** C is the century (1 = 2000s), so `1260309` is 2026-03-09. File names use it too.
- **Implied decimals.** `0000600` with 2 implied decimals is 6.00. In the copybook, `V` shows where the decimal point goes (`PIC 9(5)V99` is 5 digits, then 2 decimals).
- **Trailing signs.** The shipment cost ends with `+` or `-`. A `-` marks a credit (a damaged case sent back). The quantity itself has no sign.

For example, this shipment line:

```
022141260311MOZ00410MOZZ SHRED 4X2.5KG  0017750KG000149988+
```

reads as store 02214, date 1260311 (2026-03-11), item MOZ00410, description MOZZ SHRED 4X2.5KG, quantity 177.50, unit KG, cost 1,499.88, positive.

## Cheese variance

For each store and ingredient:

- **Actual usage** = opening count + shipped (in base units) − closing count.
- **Theoretical usage** = what the tills sold × `master_data/recipes.csv`.
- **Variance** = actual − theoretical. Normal waste is a few percent.

## Watch out for

| Problem | How to spot it | How many |
|---|---|---|
| Cheese shipped in kilograms | The Aloha stores order cheese by weight: unit `KG`, not `CS`. Reading it as cases overstates their cheese tenfold | 9 lines |
| Credits | A `-` at the end of a shipment line; that quantity must be subtracted, not added | 3 lines |
| Cheese going missing | Stores 1055 and 2214 use about 15% more cheese than their sales explain. Everyone else is within normal waste | 2 stores |

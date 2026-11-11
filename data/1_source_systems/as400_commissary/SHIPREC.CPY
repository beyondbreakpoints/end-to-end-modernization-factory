      * SHIPMENT HISTORY  -  FILES SHPCYYMMDD  -  RECORD LENGTH 59
       01  SHIP-REC.
           05  SH-STORE-NO       PIC 9(5).
           05  SH-SHIP-DATE      PIC 9(7).
      *        CYYMMDD  C=1 FOR 20XX  1260309 = 2026-03-09
           05  SH-ITEM-CODE      PIC X(8).
           05  SH-ITEM-DESC      PIC X(20).
           05  SH-QTY            PIC 9(5)V99.
      *        2 IMPLIED DECIMALS  0000600 = 6.00
           05  SH-UOM            PIC X(2).
      *        CS = CASE, KG = KILOGRAM
           05  SH-EXT-COST       PIC S9(7)V99 SIGN TRAILING SEPARATE.
      *        EXTENDED COST IN CAD  -  TRAILING - MARKS A CREDIT

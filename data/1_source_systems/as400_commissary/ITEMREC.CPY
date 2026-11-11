      * ITEM MASTER  -  FILE ITEMMAST  -  RECORD LENGTH 47
       01  ITEM-REC.
           05  IT-ITEM-CODE      PIC X(8).
           05  IT-ITEM-DESC      PIC X(20).
           05  IT-PACK-UOM       PIC X(2).
      *        CS = CASE
           05  IT-BASE-UOM       PIC X(2).
      *        KG = KILOGRAM, EA = EACH
           05  IT-PACK-QTY       PIC 9(4)V999.
      *        BASE UNITS PER CASE, 3 IMPLIED DECIMALS
           05  IT-PACK-COST      PIC 9(5)V99.
      *        COST PER CASE IN CAD, 2 IMPLIED DECIMALS
           05  IT-STATUS         PIC X(1).
      *        A = ACTIVE

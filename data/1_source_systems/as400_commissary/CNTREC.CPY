      * STORE STOCK COUNT  -  FILES CNTCYYMMDD  -  RECORD LENGTH 31
       01  COUNT-REC.
           05  CT-STORE-NO       PIC 9(5).
           05  CT-COUNT-DATE     PIC 9(7).
      *        CYYMMDD
           05  CT-COUNT-TYPE     PIC X(1).
      *        O = OPENING COUNT (BEFORE TRADING), C = CLOSING COUNT (AFTER TRADING)
           05  CT-ITEM-CODE      PIC X(8).
           05  CT-QTY-ON-HAND    PIC 9(5)V999.
      *        IN BASE UNITS, 3 IMPLIED DECIMALS
           05  CT-BASE-UOM       PIC X(2).

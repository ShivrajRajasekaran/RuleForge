       IDENTIFICATION DIVISION.
       PROGRAM-ID. EVALACCT.
      *
      * Hand-labelled benchmark program for precision/recall evaluation.
      * One EVALUATE that sets minimum balance and interest rate by type.
      *
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ACCOUNT-TYPE      PIC X(3).
          88 SAVINGS            VALUE 'SAV'.
          88 CURRENT            VALUE 'CUR'.
          88 FIXED-DEPOSIT      VALUE 'FDR'.
       01 WS-MINIMUM-BALANCE   PIC 9(7)V99.
       01 WS-INTEREST-RATE     PIC 9(2)V9(4).
       PROCEDURE DIVISION.
       SET-ACCOUNT-PARAMS.
           EVALUATE TRUE
               WHEN SAVINGS
                   MOVE 1000.00 TO WS-MINIMUM-BALANCE
                   MOVE 04.5000 TO WS-INTEREST-RATE
               WHEN CURRENT
                   MOVE 5000.00 TO WS-MINIMUM-BALANCE
                   MOVE 00.0000 TO WS-INTEREST-RATE
               WHEN FIXED-DEPOSIT
                   MOVE 10000.00 TO WS-MINIMUM-BALANCE
                   MOVE 07.2500 TO WS-INTEREST-RATE
               WHEN OTHER
                   MOVE 0 TO WS-MINIMUM-BALANCE
                   MOVE 0 TO WS-INTEREST-RATE
           END-EVALUATE.
           STOP RUN.

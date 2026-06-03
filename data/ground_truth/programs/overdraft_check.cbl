       IDENTIFICATION DIVISION.
       PROGRAM-ID. OVERDRAFT.
      *
      * Hand-labelled benchmark program for precision/recall evaluation.
      * Mixed program: validation + conditional + computational rules.
      *
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ACCOUNT-BALANCE   PIC S9(9)V99.
       01 WS-WITHDRAWAL-AMT    PIC 9(7)V99.
       01 WS-OVERDRAFT-LIMIT   PIC 9(7)V99.
       01 WS-OVERDRAFT-FEE     PIC 9(5)V99.
       01 WS-CUSTOMER-TIER     PIC X(10).
          88 TIER-PLATINUM      VALUE 'PLATINUM'.
          88 TIER-GOLD          VALUE 'GOLD'.
          88 TIER-SILVER        VALUE 'SILVER'.
          88 TIER-BASIC         VALUE 'BASIC'.
       01 WS-TXN-STATUS        PIC X(8).
       01 WS-NEW-BALANCE       PIC S9(9)V99.
       01 WS-FEE-RATE          PIC 9(2)V99.
       PROCEDURE DIVISION.
       CHECK-WITHDRAWAL.
           IF WS-WITHDRAWAL-AMT <= 0
               MOVE 'INVALID' TO WS-TXN-STATUS
           ELSE
               IF WS-WITHDRAWAL-AMT > 100000
                   MOVE 'OVERLIMT' TO WS-TXN-STATUS
               ELSE
                   PERFORM CALCULATE-BALANCE
               END-IF
           END-IF.
       CALCULATE-BALANCE.
           COMPUTE WS-NEW-BALANCE =
               WS-ACCOUNT-BALANCE - WS-WITHDRAWAL-AMT.
           IF WS-NEW-BALANCE >= 0
               MOVE 'APPROVED' TO WS-TXN-STATUS
           ELSE
               MOVE 'OVERDRFT' TO WS-TXN-STATUS
               PERFORM CALCULATE-OD-FEE
           END-IF.
       CALCULATE-OD-FEE.
           EVALUATE TRUE
               WHEN TIER-PLATINUM
                   MOVE 0.00 TO WS-FEE-RATE
               WHEN TIER-GOLD
                   MOVE 1.50 TO WS-FEE-RATE
               WHEN TIER-SILVER
                   MOVE 2.50 TO WS-FEE-RATE
               WHEN TIER-BASIC
                   MOVE 5.00 TO WS-FEE-RATE
           END-EVALUATE.
           COMPUTE WS-OVERDRAFT-FEE =
               WS-NEW-BALANCE * WS-FEE-RATE / 100.
           STOP RUN.

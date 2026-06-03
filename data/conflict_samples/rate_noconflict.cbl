       IDENTIFICATION DIVISION.
       PROGRAM-ID. RATEOK.
      *
      * Negative control for the conflict detector. The two guards are
      * mutually exclusive (balance > 5000 vs balance < 1000), so even
      * though their actions differ there is NO conflict.
      *
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ACCT-BALANCE  PIC 9(9)V99.
       01 WS-INT-RATE      PIC 9(2)V99.
       PROCEDURE DIVISION.
       HIGH-BALANCE.
           IF WS-ACCT-BALANCE > 5000
               PERFORM APPLY-PREMIUM-RATE
           END-IF.
       LOW-BALANCE.
           IF WS-ACCT-BALANCE < 1000
               PERFORM APPLY-STANDARD-RATE
           END-IF.
       APPLY-PREMIUM-RATE.
           MOVE 4.50 TO WS-INT-RATE.
       APPLY-STANDARD-RATE.
           MOVE 2.00 TO WS-INT-RATE.

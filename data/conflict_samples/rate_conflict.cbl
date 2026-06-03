       IDENTIFICATION DIVISION.
       PROGRAM-ID. RATECONF.
      *
      * Conflict-detector fixture. CONTAINS A DELIBERATE RULE CONFLICT:
      * a savings balance over 5000 satisfies BOTH paragraphs below, but
      * they PERFORM different rate routines. The program resolves it by
      * order; the business spec is ambiguous.
      *
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ACCT-TYPE     PIC X(3).
       01 WS-ACCT-BALANCE  PIC 9(9)V99.
       01 WS-INT-RATE      PIC 9(2)V99.
       PROCEDURE DIVISION.
       APPLY-PREMIUM.
           IF WS-ACCT-TYPE = 'SAV' AND WS-ACCT-BALANCE > 5000
               PERFORM APPLY-PREMIUM-RATE
           END-IF.
       APPLY-STANDARD.
           IF WS-ACCT-TYPE = 'SAV' AND WS-ACCT-BALANCE > 1000
               PERFORM APPLY-STANDARD-RATE
           END-IF.
       APPLY-PREMIUM-RATE.
           MOVE 4.50 TO WS-INT-RATE.
       APPLY-STANDARD-RATE.
           MOVE 2.00 TO WS-INT-RATE.

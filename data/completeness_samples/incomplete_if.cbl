       IDENTIFICATION DIVISION.
       PROGRAM-ID. INCMPIF.
      *
      * Completeness fixture: IF with NO ELSE. When the balance is not
      * greater than the credit limit, the action is UNDEFINED.
      *
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ACCT-BALANCE  PIC 9(9)V99.
       01 WS-CREDIT-LIMIT  PIC 9(9)V99.
       01 WS-ACCT-STATUS   PIC X(8).
       PROCEDURE DIVISION.
       CHECK-LIMIT.
           IF WS-ACCT-BALANCE > WS-CREDIT-LIMIT
               MOVE 'OVERLIMT' TO WS-ACCT-STATUS
           END-IF.
           STOP RUN.

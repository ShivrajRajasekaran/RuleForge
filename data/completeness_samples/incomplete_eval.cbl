       IDENTIFICATION DIVISION.
       PROGRAM-ID. INCMPEVL.
      *
      * Completeness fixture: EVALUATE with NO catch-all (WHEN OTHER).
      * Account types other than SAV/CUR/FDR have UNDEFINED behaviour.
      *
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ACCT-TYPE   PIC X(3).
       01 WS-INT-RATE    PIC 9(2)V99.
       PROCEDURE DIVISION.
       SET-RATE.
           EVALUATE WS-ACCT-TYPE
               WHEN 'SAV'
                   MOVE 4.50 TO WS-INT-RATE
               WHEN 'CUR'
                   MOVE 1.00 TO WS-INT-RATE
               WHEN 'FDR'
                   MOVE 6.00 TO WS-INT-RATE
           END-EVALUATE.
           STOP RUN.

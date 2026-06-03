       IDENTIFICATION DIVISION.
       PROGRAM-ID. CMPLEVL.
      *
      * Completeness fixture: EVALUATE WITH a WHEN OTHER catch-all.
      * Every account type maps to a defined rate -> complete.
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
               WHEN OTHER
                   MOVE 0.00 TO WS-INT-RATE
           END-EVALUATE.
           STOP RUN.

       IDENTIFICATION DIVISION.
       PROGRAM-ID. INFRAONLY.
      *
      * Hand-labelled benchmark program for precision/recall evaluation.
      * NEGATIVE control: pure infrastructure, ZERO business rules.
      * Any rule detected here is a false positive.
      *
       DATA DIVISION.
       FILE SECTION.
       WORKING-STORAGE SECTION.
       01 WS-FILE-STATUS       PIC X(2).
       01 WS-EOF-FLAG          PIC X(1) VALUE 'N'.
       01 WS-MESSAGE           PIC X(50).
       PROCEDURE DIVISION.
       OPEN-FILES.
           OPEN INPUT CUSTOMER-FILE.
           IF WS-FILE-STATUS NOT = '00'
               DISPLAY 'OPEN FAILED'
           END-IF.
       READ-RECORD.
           READ CUSTOMER-FILE
               AT END MOVE 'Y' TO WS-EOF-FLAG
           END-READ.
       CLOSE-FILES.
           CLOSE CUSTOMER-FILE.
           IF WS-FILE-STATUS NOT = '00'
               DISPLAY 'CLOSE FAILED'
           END-IF.
           STOP RUN.

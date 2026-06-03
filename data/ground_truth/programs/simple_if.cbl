       IDENTIFICATION DIVISION.
       PROGRAM-ID. SIMPLEIF.
      *
      * Hand-labelled benchmark program for precision/recall evaluation.
      * Single IF-ELSE pricing decision on order total.
      *
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CUSTOMER-TYPE     PIC X(10).
       01 WS-DISCOUNT-RATE     PIC 9(2)V99.
       01 WS-ORDER-TOTAL       PIC 9(7)V99.
       PROCEDURE DIVISION.
       CALCULATE-DISCOUNT.
           IF WS-ORDER-TOTAL > 10000
               MOVE 15.00 TO WS-DISCOUNT-RATE
           ELSE
               MOVE 5.00 TO WS-DISCOUNT-RATE
           END-IF.
           STOP RUN.

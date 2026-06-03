       IDENTIFICATION DIVISION.
       PROGRAM-ID. COMPFIN.
      *
      * Hand-labelled benchmark program for precision/recall evaluation.
      * Three paragraphs, each a computational rule (interest, EMI, TDS).
      *
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-PRINCIPAL         PIC 9(9)V99.
       01 WS-RATE              PIC 9(2)V9(4).
       01 WS-TIME-YEARS        PIC 9(2).
       01 WS-SIMPLE-INTEREST   PIC 9(9)V99.
       01 WS-TAX-AMOUNT        PIC 9(7)V99.
       01 WS-NET-INTEREST      PIC 9(9)V99.
       01 WS-TDS-RATE          PIC 9(2)V99 VALUE 10.00.
       PROCEDURE DIVISION.
       CALCULATE-INTEREST.
           COMPUTE WS-SIMPLE-INTEREST =
               WS-PRINCIPAL * WS-RATE * WS-TIME-YEARS / 100.
       CALCULATE-TAX.
           COMPUTE WS-TAX-AMOUNT =
               WS-SIMPLE-INTEREST * WS-TDS-RATE / 100.
       CALCULATE-NET.
           COMPUTE WS-NET-INTEREST =
               WS-SIMPLE-INTEREST - WS-TAX-AMOUNT.
           STOP RUN.

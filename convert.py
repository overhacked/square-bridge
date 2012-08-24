# Script to convert CSV to IIF output.

import os
import sys, traceback, re
import csv
from decimal import *

PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))

class SquareTransactions(object):
    """Interprets squareup.com CSV export files"""
    def __init__(self, fh):
        super(SquareCSVReader, self).__init__()
        self.fh = fh
        self.reader = csv.DictReader(self.fh, dialect='excel')
        
    def __iter__(self):
        return SquareCSVIterator(self)
        
    def dumpAll(self):
        try:
            for row in self.reader:
                print row
        except csv.Error, e:
            sys.exit('file %s, line %d: %s' % (self.fh.name, self.reader.line_num, e))

class SquareCSVIterator(object):
    def __init__(self, transactions):
        self.trans = transactions
    def __iter__(self):
        return self
    def next(self):
        row = self.trans.reader.next()
        for k, v in row.iteritems()
            if v[0] == '$':
                row[k] = Decimal(v[1:])
            if k == 'Date':
                pass
            if k == 'Time':
                pass
        return row
                
        
def error(trans):
    sys.stderr.write("%s\n" % trans)
    traceback.print_exc(None, sys.stderr)


def main():
    input_file = open(os.path.join(PROJECT_ROOT, 'input.csv'), 'r')
    square = SquareCSVReader(input_file)
    square.dumpAll()
    sys.exit()
    # DEBUG - go no further
    
    output_file = open(os.path.join(PROJECT_ROOT, 'output.iif'), 'w')


    # This is the name of the QuickBooks checking account
    account = "Square"

    # This is the IIF template

    head = "!TRNS	TRNSID	TRNSTYPE	DATE	ACCNT	NAME	CLASS	AMOUNT	DOCNUM	MEMO	CLEAR	TOPRINT	NAMEISTAXABLE	DUEDATE	TERMS	PAYMETH	SHIPVIA	SHIPDATE	REP	FOB	PONUM	INVMEMO	ADDR1	ADDR2	ADDR3	ADDR4	ADDR5	SADDR1	SADDR2	SADDR3	SADDR4	SADDR5	TOSEND	ISAJE	OTHER1	ACCTTYPE	ACCTSPECIAL\r\n"\
           + "!SPL	SPLID	TRNSTYPE	DATE	ACCNT	NAME	CLASS	AMOUNT	DOCNUM	MEMO	CLEAR	QNTY	PRICE	INVITEM	PAYMETH	TAXABLE	EXTRA	VATCODE	VATRATE	VATAMOUNT	VALADJ	SERVICEDATE	TAXCODE	TAXRATE	TAXAMOUNT	TAXITEM	OTHER2	OTHER3	REIMBEXP	ACCTTYPE	ACCTSPECIAL	ITEMTYPE\r\n"\
    + "!ENDTRNS\r\n"

    output_file.write(head)

    template = "TRNS		CREDIT CARD	%s	Square			-%s		%s		N	N	%s																			N			CCARD\r\n"\
               + "SPL		CREDIT CARD	%s	Ask My Accountant			%s				0	%s							0.00					0.00					EXP\r\n"\
    + "ENDTRNS\r\n"


    # And here's the part that inserts data into the tempalate
    for trans in input_file:

        try:
            list = trans.split(',')
            assert (len(list) == 3 )
        except:
            error(trans)
            continue

        try:
            (date, amount, comments) = list
        #            date = date.replace('/', '-')
        except:
            error(trans)
            continue

        try:
            amount = float(amount)
        except:
            error(trans)
            continue

        comments = comments.strip('"')
        comments = comments.strip("\n")
        comments = comments.strip("\r")

        output_file.write(template % (date, amount, comments, date,
                                      date, amount, amount))


if __name__ == '__main__':
    main()
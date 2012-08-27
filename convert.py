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
    transactions_file = open(os.path.join(PROJECT_ROOT, 'transactions.csv'), 'r')
    transactions = csv.DictReader(transactions_file, dialect='excel')
    items_file = open(os.path.join(PROJECT_ROOT, 'items.csv'), 'r')
    items = csv.DictReader(items_file, dialect='excel')

    output_dialect = csv.Dialect()
    output_dialect.delimeter = "\t"
    output_dialect.doublequote = False
    output_dialect.escapechar = '\\'
    output_dialect.quotechar = '"'
    
    output_file = open(os.path.join(PROJECT_ROOT, 'output.iif'), 'w')
    #output = csv.DictWriter(output_file, dialect=output_dialect)

    # This is the name of the QuickBooks checking account
    account = "Square"

    # This is the IIF template

    head = "!TRNS	TRNSID	TRNSTYPE	DATE	ACCNT	NAME	CLASS	AMOUNT	DOCNUM	MEMO	TOPRINT	NAMEISTAXABLE\r\n"\
           + "!SPL	SPLID	TRNSTYPE	DATE	ACCNT	NAME	CLASS	AMOUNT	DOCNUM	MEMO	QNTY	PRICE	INVITEM	TAXABLE\r\n"\
    + "!ENDTRNS\r\n"

    output_file.write(head)

    trans_template = "TRNS		CASH SALE	{month:02d}/{day:02d}/{year:d}	{till_account}	{customer}	{qb_class}	{total:.2f}	{square_id:s}	{cc_digits:s}	N	N\r\n"
    item_template = "SPL		CASH SALE	{month:02d}/{day:02d}/{year:d}	{sales_account}		{class}	-{total:.2f}			{qty:d}	{price:.2f}	{item_name:s}	N\r\n"
    trans_footer = "ENDTRNS\r\n"


    # And here's the part that inserts data into the tempalate
    for trans in transactions:

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
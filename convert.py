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
        for k, v in row.iteritems():
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
    
    output_file = open(os.path.join(PROJECT_ROOT, 'output.iif'), 'w')

    # This is the name of the QuickBooks checking account
    account = "Square"

    # This is the IIF template

    head = "!TRNS	TRNSID	TRNSTYPE	DATE	ACCNT	NAME	CLASS	AMOUNT	DOCNUM	MEMO	TOPRINT	NAMEISTAXABLE\r\n"\
           + "!SPL	SPLID	TRNSTYPE	DATE	ACCNT	NAME	CLASS	AMOUNT	DOCNUM	MEMO	QNTY	PRICE	INVITEM	TAXABLE\r\n"\
    + "!ENDTRNS\r\n"

    output_file.write(head)

    trans_template = "TRNS		CASH SALE	{month:02d}/{day:02d}/{year:d}	{till_account}	{customer}	{qb_class}	{total:.2f}	{square_id:s}	{cc_digits:s}	N	N\r\n"
    item_template = "SPL		CASH SALE	{month:02d}/{day:02d}/{year:d}	{sales_account}		{qb_class}	-{total:.2f}			{qty:d}	{price:.2f}	{item_name:s}	N\r\n"
    trans_footer = "ENDTRNS\r\n"


    # TODO: implement config file
    cfg_cashAccount = 'Market Till'
    cfg_defaultSalesAccount = 'Sales'
    cfg_customer = 'PRFM Customers'
    cfg_defaultClass = 'Layers'

    # Initialize a buffer for stray items
    itemBuffer = list()
    
    # And here's the part that inserts data into the tempalate
    for trans in transactions:
        try:
            (year, month, day) = map(int,trans['Date'].split('-', 2))
        except:
            error(trans)
            continue
        
        square_id = trans['Payment ID']
        cc_digits = trans['Card Number'].translate(None,'="')
        try:
            total = float(trans['Total'].lstrip('$'))
        except:
            error(trans)
            continue
        
        output_file.write(trans_template.format(month=month, day=day, year=year, till_account=cfg_cashAccount, customer=cfg_customer, qb_class=cfg_defaultClass, total=total, square_id=square_id, cc_digits=cc_digits))
        while True:
            if len(itemBuffer) > 0:
                item = itemBuffer.pop()
            else:
                try:
                    item = items.next()
                except StopIteration:
                    break
                if item['Payment ID'] != square_id:
                    itemBuffer.append(item)
                    break
            try:
                item_total = float(item['Price'].lstrip('$')) - float(item['Discount'].lstrip('$'))
            except:
                error(item)
                break
            
            # TODO: count quantities
            output_file.write(item_template.format(month=month, day=day, year=year, sales_account=cfg_defaultSalesAccount, qb_class=cfg_defaultClass, total=item_total, qty=1, price=item_total, item_name=item['Item Name']))
        
        output_file.write(trans_footer)

if __name__ == '__main__':
    main()
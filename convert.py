# Script to convert CSV to IIF output.

import os
import sys, traceback, re
import csv
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))

class SquareCSVReader(object):
    """Interprets squareup.com CSV export files"""

    def __init__(self, csvfile):
        self.reader = csv.reader(csvfile, dialect='excel')        
        self.fieldnames = self.reader.next()
        self.floatRe = re.compile('[-+]?[0-9]+\.[0-9]+')
        
    def __iter__(self):
        return self

    def next(self):
        row = self.reader.next()
        newRow = list()
        for v in row:
            newValue = v

            if len(v) > 0 and v[0] == '$':
                newValue = float(v[1:])

            floatMatch = self.floatRe.match(v)
            if floatMatch:
                newValue = float(floatMatch.group(0))
            
            newRow.append(newValue)

        return newRow

class SquareReader(object):
    """Interprets squareup.com CSV export files"""
    # This is the IIF template
    IIF_HEAD =  "!TRNS	TRNSID	TRNSTYPE	DATE	ACCNT	NAME	CLASS	AMOUNT	DOCNUM	MEMO	TOPRINT	NAMEISTAXABLE\r\n"\
                + "!SPL	SPLID	TRNSTYPE	DATE	ACCNT	NAME	CLASS	AMOUNT	DOCNUM	MEMO	QNTY	PRICE	INVITEM	TAXABLE\r\n"\
                + "!ENDTRNS\r\n"
    TRANS_TEMPLATE = "TRNS		CASH SALE	{month:02d}/{day:02d}/{year:d}	{till_account}	{customer}	{qb_class}	{total:.2f}	{square_id:s}	{cc_digits:s}	N	N\r\n"
    TRANS_TYPES = {'Subtotal':'REAL','Discount':'REAL','Sales Tax':'REAL','Tips':'REAL','Total':'REAL','Fee':'REAL','Net':'REAL',}
    ITEM_TEMPLATE = "SPL		CASH SALE	{month:02d}/{day:02d}/{year:d}	{sales_account}		{qb_class}	-{total:.2f}			{qty:.2f}	{price:.2f}	{item_name:s}	N\r\n"
    DISC_TEMPLATE = "SPL		CASH SALE	{month:02d}/{day:02d}/{year:d}	{sales_account}		{qb_class}	{total:.2f}				{price:.2f}	{item_name:s}	N\r\n"
    ITEM_TYPES = {'Price':'REAL','Discount':'REAL','Tax':'REAL',}
    TRANS_FOOTER = "ENDTRNS\r\n"


    def __init__(self):
        self.transactionsFile = None
        self.transactionsReader = None
        self.itemsFile = None
        self.itemsReader = None
        self.depositsFile = None
        self.depositsReader = None

        # Use tempfile databases
        self.db = sqlite3.connect('')

    def importTransactions(self,transactions_fh):
        self.transactionsFile = transactions_fh
        self.transactionsReader = SquareCSVReader(self.transactionsFile)

        # Create the transactions table
        transactionFieldsSql = []
        for field in self.transactionsReader.fieldnames:
            if field in self.TRANS_TYPES:
                fieldType = self.TRANS_TYPES[field]	
            else:
                fieldType = 'TEXT'
            fieldSql = '"%s" %s' % (field.replace(' ','_'), fieldType)
            transactionFieldsSql.append(fieldSql)

        createTransactionsSql = 'CREATE TABLE transactions ( %s )' % ','.join(transactionFieldsSql)
        self.db.execute(createTransactionsSql)
        self.db.commit()

        transactionsInsertSql = 'INSERT INTO transactions VALUES (%s);' % ( ('?, ' * len(self.transactionsReader.fieldnames)).rstrip(', ') )
        cur = self.db.cursor()
        cur.executemany(transactionsInsertSql, self.transactionsReader)
        self.db.commit()
        
    def importItems(self,items_fh):
        self.itemsFile = items_fh
        self.itemsReader = SquareCSVReader(self.itemsFile)
        # Create the items table
        itemFieldsSql = []
        for field in self.itemsReader.fieldnames:
            if field in self.ITEM_TYPES:
                fieldType = self.ITEM_TYPES[field]	
            else:
                fieldType = 'TEXT'
            fieldSql = '"%s" %s' % (field.replace(' ','_'), fieldType)
            itemFieldsSql.append(fieldSql)

        createItemsSql = 'CREATE TABLE items ( %s )' % ','.join(itemFieldsSql)
        self.db.execute(createItemsSql)
        self.db.commit()

        itemsInsertSql = 'INSERT INTO items VALUES (%s);' % ( ('?, ' * len(self.itemsReader.fieldnames)).rstrip(', ') )
        cur = self.db.cursor()
        cur.executemany(itemsInsertSql, self.itemsReader)
        self.db.commit()

    def exportIif(self,output_fh):
        # TODO: implement config file
        cfg_cashAccount = 'Market Till'
        cfg_defaultSalesAccount = 'Sales'
        cfg_discountAccount = 'Discount Expenses'
        cfg_discountItemName = 'Industry Discount'
        cfg_customer = 'PRFM Customers'
        cfg_defaultClass = 'Layers'

        # Transaction columns: Date,Time,Transaction_Type,Payment_Type,Subtotal,Discount,Sales_Tax,Tips,Total,Fee,Net,Payment_Method,Card_Brand,Card_Number,Details,Payment_ID,Device_Name,Description
        tCur = self.db.cursor()
        tCur.execute('SELECT "Date","Transaction_Type","Payment_Type","Subtotal","Discount","Sales_Tax","Tips","Total","Fee","Net","Payment_Method","Card_Brand","Card_Number","Payment_ID" FROM "transactions"')
        output_fh.write(self.IIF_HEAD)
        for date,transaction_type,payment_type,subtotal,discount,sales_tax,tips,total,fee,net,payment_method,card_brand,card_number,payment_id in tCur:
            #TODO: unimplemented sales_tax and tips handling
            
            (year, month, day) = map(int,date.split('-', 2))
            
            cc_digits = card_brand + " " + card_number.translate({ord(u'='):None,ord(u'"'):None})
            
            #TODO: implement difference between cash transactions and card transactions
            output_fh.write(self.TRANS_TEMPLATE.format(month=month, day=day, year=year, till_account=cfg_cashAccount, customer=cfg_customer, qb_class=cfg_defaultClass, total=total, square_id=payment_id, cc_digits=cc_digits))

            # Item columns: Date,Time,Details,Payment_ID,Device_Name,Category_Name,Item_Name,Price,Discount,Tax,Notes
            iCur = self.db.cursor()
            iCur.execute('SELECT "Category_Name","Item_Name",CASE WHEN "Price" < 1.0 THEN COUNT(*)/100.0 ELSE COUNT(*) END AS \'Quantity\',CASE WHEN "Price" < 1.0 THEN "Price"*100 ELSE "Price" END AS \'Item_Price\',SUM("Discount") AS \'Discount\',SUM("Tax") AS \'Tax\' FROM "items" WHERE "Payment_ID" = ? GROUP BY "Category_Name","Item_Name","Price";',(payment_id,))
            for item_category,item_name,item_quantity,item_price,item_discount,item_tax in iCur:
                output_fh.write(self.ITEM_TEMPLATE.format(month=month, day=day, year=year, sales_account=cfg_defaultSalesAccount, qb_class=cfg_defaultClass, total=item_price, qty=item_quantity, price=item_price, item_name=item_name))
            
            # Output one discount line per transaction, if any discount specified
            if discount < 0:
                output_fh.write(self.DISC_TEMPLATE.format(month=month, day=day, year=year, sales_account=cfg_discountAccount, qb_class=cfg_defaultClass, total=-discount, price=-discount, item_name=cfg_discountItemName))
            
            # END of sales transaction
            output_fh.write(self.TRANS_FOOTER)
            #TODO: implement fee transaction
            #TODO: implement deposits, if deposits.csv provided

        
    def dumpSqliteMaster(self):
        cur = self.db.cursor()
        cur.execute('SELECT * FROM sqlite_master;')
        print repr(cur.fetchall())

    def dumpSql(self):
        for line in self.db.iterdump():
            print line

    def dumpCsv(self):
        try:
            for row in self.transactionsReader:
                print row
        except csv.Error, e:
            sys.exit('file %s, line %d: %s' % (self.transactionsFile.name, self.transactionsReader.line_num, e))

def main():
    transactions_file = open(os.path.join(PROJECT_ROOT, 'transactions.csv'), 'r')
    items_file = open(os.path.join(PROJECT_ROOT, 'items.csv'), 'r')
    output_file = open(os.path.join(PROJECT_ROOT, 'output.iif'), 'w')
    
    square = SquareReader()
	
    # This is the name of the QuickBooks checking account
    account = "Square"

    #DEBUG
    square.importTransactions(transactions_file)
    square.importItems(items_file)
    square.dumpSql()
    square.exportIif(output_file)
    exit()

    # And here's the part that inserts data into the tempalate
    item = None
    prevItem = None
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
        
        #DEBUG
        print "--- Transaction %s ---" % (square_id)
        #END DEBUG
        itemsCount = 0
        while True:
            prevItem = item
            if prevItem is not None:
                itemsCount += 1
            print "itemsCount: %d" % itemsCount
            try:
                item = items.next()
            except StopIteration:
                # TODO: handle case for last item
                outputItem(prevItem, itemsCount, cfg_defaultSalesAccount, cfg_defaultClass)
                print "!!! StopIteration !!!"
                break
            print "item: %r\nprevItem: %r" % (item,prevItem)
            if prevItem is None or (item['Payment ID'] == square_id and item['Item Name'] == prevItem['Item Name'] and item['Category Name'] == prevItem['Category Name'] and item['Price'] == prevItem['Price']):
                print "DUPE!"
                continue
            else:
                try:
                    outputItem(prevItem, itemsCount, cfg_defaultSalesAccount, cfg_defaultClass)
                    prevItem = None
                    itemsCount = 0
                except:
                    error(prevItem)
                    break
                
            if item['Payment ID'] != square_id:
                break
            
        output_file.write(trans_footer)
        #DEBUG
        print "--- END Transaction ---"
        #END DEBUG
        
if __name__ == '__main__':
    main()

# Script to convert CSV to IIF output.

import os
import sys, traceback, re
import csv
import sqlite3
import config

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
            else:
                floatMatch = self.floatRe.match(v)
                if floatMatch:
                    newValue = float(floatMatch.group(0))
            
            newRow.append(newValue)

        return newRow

class SquareReader(object):
    """Interprets squareup.com CSV export files"""
    # This is the IIF template
    TRANS_HEAD =      "!TRNS\tTRNSID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tMEMO\tTOPRINT\tPAYMETH\tNAMEISTAXABLE\r\n"\
                    + "!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tMEMO\tQNTY\tPRICE\tINVITEM\tTAXABLE\r\n"\
                    + "!ENDTRNS\r\n"
    TRANS_TEMPLATE = "TRNS\t\tCASH SALE\t{month:02d}/{day:02d}/{year:d}\t{till_account}\t{customer}\t{qb_class}\t{total:.2f}\t{square_id:s}\t{memo:s}\tN\t{payment_method:s}\tN\r\n"
    TRANS_TYPES = {'Subtotal':'REAL','Discount':'REAL','Sales Tax':'REAL','Tips':'REAL','Total':'REAL','Fee':'REAL','Net':'REAL',}
    ITEM_TEMPLATE = "SPL\t\tCASH SALE\t{month:02d}/{day:02d}/{year:d}\t{sales_account}\t\t{qb_class}\t-{total:.2f}\t\t\t{qty:.2f}\t{price:.2f}\t{item_name:s}\tN\r\n"
    DISC_TEMPLATE = "SPL\t\tCASH SALE\t{month:02d}/{day:02d}/{year:d}\t{sales_account}\t\t{qb_class}\t{total:.2f}\t\t\t\t{price:.2f}\t{item_name:s}\tN\r\n"
    ITEM_TYPES = {'Price':'REAL','Discount':'REAL','Tax':'REAL',}
    TRANS_FOOTER = "ENDTRNS\r\n"
    FEE_HEAD =      "!TRNS\tTRNSID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tCLEAR\tTOPRINT\r\n"\
                +   "!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tCLEAR\r\n"\
                +   "!ENDTRNS\r\n"
    FEE_TEMPLATE =      "TRNS\t\tCHECK\t{month:02d}/{day:02d}/{year:d}\t{square_account}\t{square_vendor}\t{qb_class}\t-{amount}\t{square_id:s}\tN\tN\r\n"\
                    +   "SPL\t\tCHECK\t{month:02d}/{day:02d}/{year:d}\t{fees_account}\t\t\t{amount}\t\tN\r\n"\
                    +   "ENDTRNS\r\n"


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
        # Transaction columns: Date,Time,Transaction_Type,Payment_Type,Subtotal,Discount,Sales_Tax,Tips,Total,Fee,Net,Payment_Method,Card_Brand,Card_Number,Details,Payment_ID,Device_Name,Description
        tCur = self.db.cursor()
        tCur.execute('SELECT "Date","Transaction_Type","Payment_Type","Subtotal","Discount","Sales_Tax","Tips","Total","Fee","Net","Payment_Method","Card_Brand","Card_Number","Payment_ID" FROM "transactions"')
        output_fh.write(self.TRANS_HEAD)
        for date,transaction_type,payment_type,subtotal,discount,sales_tax,tips,total,fee,net,square_payment_method,card_brand,card_number,payment_id in tCur:
            #TODO: unimplemented sales_tax and tips handling
            
            (year, month, day) = map(int,date.split('-', 2))
            
            if payment_type == 'Cash':
                cc_digits = 'Square Cash Sale'
                till_account=config.accounts.cash
                payment_method=config.payments.cash
            else:
                cc_digits = '{0:s}: {1:s} {2:s}'.format(square_payment_method,card_brand,card_number.strip('="'))
                till_account=config.accounts.square
                payment_method=config.payments.square
            
            #TODO: separate items into separate sales transactions based on Category_Name
            # Item columns: Date,Time,Details,Payment_ID,Device_Name,Category_Name,Item_Name,Price,Discount,Tax,Notes
            iCur = self.db.cursor()
            iCur.execute('SELECT DISTINCT "Category_Name" FROM "items" WHERE "Payment_ID" = ?;',(payment_id,))
            categoryMap = dict()
            for (category_name,) in iCur:
                if category_name in config.classMap:
                    classKey = config.classMap[category_name]
                else:
                    classKey = config.classes.default

                try:
                    categoryMap[classKey] += (category_name,)
                except KeyError:
                    categoryMap[classKey] = (category_name,)

            for qb_class, square_categories in categoryMap.iteritems():
                category_placeholders = ','.join('?'*len(square_categories))
                iCur.execute('SELECT SUM("Price"+"Discount") FROM "items" WHERE "Payment_ID" = ? AND "Category_Name" IN ({categoryPlaceholders:s}) GROUP BY "Payment_ID"'.format(categoryPlaceholders=category_placeholders),(payment_id,) + square_categories) 
                (category_total,) = iCur.fetchone()

                output_fh.write(self.TRANS_TEMPLATE.format(month=month, day=day, year=year, till_account=till_account, customer=config.names.customer, qb_class=qb_class, total=category_total, square_id=payment_id, memo=cc_digits, payment_method=payment_method))

                iCur.execute('SELECT "Category_Name","Item_Name",CASE WHEN "Price" < 1.0 THEN COUNT(*)/100.0 ELSE COUNT(*) END AS \'Quantity\',CASE WHEN "Price" < 1.0 THEN "Price"*100 ELSE "Price" END AS \'Item_Price\',SUM("Discount") AS \'Discount\',SUM("Tax") AS \'Tax\' FROM "items" WHERE "Payment_ID" = ? AND "Category_Name" IN ({categoryPlaceholders:s}) GROUP BY "Category_Name","Item_Name","Price";'.format(categoryPlaceholders=category_placeholders),(payment_id,) + square_categories)
                for item_category,item_name,item_quantity,item_price,item_discount,item_tax in iCur:
                    output_fh.write(self.ITEM_TEMPLATE.format(month=month, day=day, year=year, sales_account=config.accounts.sales, qb_class=qb_class, total=item_price*item_quantity, qty=item_quantity, price=item_price, item_name=item_name))
                    # Output one discount line per item, if any discount specified
                    if item_discount < 0:
                        output_fh.write(self.DISC_TEMPLATE.format(month=month, day=day, year=year, sales_account=config.discounts.account, qb_class=qb_class, total=-discount, price=-discount, item_name=config.discounts.item))
                # END of sales transaction
                output_fh.write(self.TRANS_FOOTER)
            
            

        fCur = self.db.cursor()
        output_fh.write(self.FEE_HEAD)
        fCur.execute('SELECT "Date","Fee","Payment_ID" FROM "transactions" WHERE "Fee" > 0')
        for date, fee, payment_id in fCur:
            (year, month, day) = map(int,date.split('-', 2))
            output_fh.write(self.FEE_TEMPLATE.format(month=month, day=day, year=year, square_account=config.accounts.square, square_vendor=config.names.square, qb_class=config.classes.fees, amount=fee, square_id=payment_id, fees_account=config.accounts.fees))
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
    #TODO: implement files as command line arguments
    transactions_file = open(os.path.join(PROJECT_ROOT, 'transactions.csv'), 'r')
    items_file = open(os.path.join(PROJECT_ROOT, 'items.csv'), 'r')
    output_file = open(os.path.join(PROJECT_ROOT, 'output.iif'), 'w')
    
    square = SquareReader()

    square.importTransactions(transactions_file)
    square.importItems(items_file)
    square.dumpSql()
    square.exportIif(output_file)
        
if __name__ == '__main__':
    main()

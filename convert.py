#!/usr/bin/env python
# Script to convert CSV to IIF output.

import os
import sys, traceback, re
import csv
import sqlite3
import config

PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))

class UnknownCSVTypeWarning(Warning):
    pass

class SquareCSVReader(object):
    """Interprets squareup.com CSV export files"""

    def __init__(self, csvfile):
        self.reader = csv.reader(csvfile, dialect='excel')        
        self.fieldnames = self.reader.next()
        # Kludge to fix duplicate 'Total Collected' field from squareup.com
        try:
            replacementIndex = self.fieldnames.index(u'Total Collected')
            self.fieldnames[replacementIndex] = u'Total Collected DUP'
        except ValueError:
            # Nothing to replace
            pass

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
    TRANS_HEAD =      "!TRNS\tTRNSID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tPONUM\tMEMO\tTOPRINT\tPAYMETH\tSHIPVIA\tNAMEISTAXABLE\r\n"\
                    + "!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tQNTY\tPRICE\tINVITEM\tTAXABLE\r\n"\
                    + "!ENDTRNS\r\n"
    TRANS_TYPE_SALE = "CASH SALE"
    TRANS_TYPE_REFUND = "CASH REFUND"
    TRANS_TEMPLATE =  "TRNS\t\t{qb_type:s}\t{month:02d}/{day:02d}/{year:d}\t{till_account}\t{customer}\t{qb_class}\t{total:.2f}\t{square_id:s}\t{square_id:s}\t{memo:s}\tN\t{payment_method:s}\t{shipvia:s}\tN\r\n"
    PART_HEAD =     "!INVITEM\tNAME\tINVITEMTYPE\tDESC\tACCNT\tPRICE\tTAXABLE\r\n"
    PART_TEMPLATE = "INVITEM\t{item_name}\tPART\t{item_description}\t{sales_account}\t{item_price:.2f}\t{taxable}\r\n"
    ITEM_TEMPLATE = "SPL\t\t{qb_type:s}\t{month:02d}/{day:02d}/{year:d}\t{sales_account}\t\t{qb_class}\t{total:.2f}\t{qty:.2f}\t{price:.2f}\t{item_name:s}\tN\r\n"
    TAX_TEMPLATE = "SPL\t\t{qb_type:s}\t{month:02d}/{day:02d}/{year:d}\t{sales_account}\t{vendor_name}\t{qb_class}\t{total:.2f}\t\t{rate:.2f}%\t{item_name:s}\tN\r\n"
    TIPS_TEMPLATE = "SPL\t\t{qb_type:s}\t{month:02d}/{day:02d}/{year:d}\t{sales_account}\t\t{qb_class}\t{total:.2f}\t\t\t{item_name:s}\tN\r\n"
    DISC_TEMPLATE = "SPL\t\t{qb_type:s}\t{month:02d}/{day:02d}/{year:d}\t{sales_account}\t\t{qb_class}\t{total:.2f}\t\t\t{item_name:s}\tN\r\n"
    TRANS_FOOTER = "ENDTRNS\r\n"
    FEE_HEAD =      "!TRNS\tTRNSID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tCLEAR\tTOPRINT\r\n"\
                +   "!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tCLEAR\r\n"\
                +   "!ENDTRNS\r\n"
    FEE_TEMPLATE =      "TRNS\t\tCHECK\t{month:02d}/{day:02d}/{year:d}\t{square_account}\t{square_vendor}\t{qb_class}\t{amount_neg}\t{square_id:s}\tN\tN\r\n"\
                    +   "SPL\t\tCHECK\t{month:02d}/{day:02d}/{year:d}\t{fees_account}\t\t{qb_class}\t{amount}\t\tN\r\n"\
                    +   "ENDTRNS\r\n"
    # This maps Squareup.com CSV fields to SQLite types
    ITEM_TYPES = {'Price':'REAL','Discount':'REAL','Tax':'REAL',}
    TRANS_TYPES = {'Sale':'REAL','Discount':'REAL','Sales Tax':'REAL','Tip':'REAL','Total Collected':'REAL','Fee':'REAL','Net Total':'REAL',}


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
        tCur = self.db.cursor()
        iCur = self.db.cursor()

        # If the user is using the [items] mapping support in the config file, generate
        # IIF !INVITEM lines so that items don't get repeatedly created for every !TRNS line
        if len(config.itemsMap) > 0:
            output_fh.write(self.PART_HEAD)
            iCur.execute('SELECT "Category_Name","Item_Name",MAX("Price"),MAX("Tax") FROM "items" GROUP BY "Category_Name","Item_Name";')
            for item_category,item_name,item_maxprice,item_maxtax in iCur:
                # Rewrite item name if specified in config
                if item_name in config.itemsMap:
                    item_qb_name = config.itemsMap[item_name]
                else:
                    item_qb_name = item_name

                if item_category in config.salesMap:
                    sales_account = config.salesMap[item_category]
                else:
                    sales_account = config.accounts.sales

                if item_maxprice < 1.0:
                    item_maxprice *= 100

                if isinstance(item_maxtax, (int,long)) and item_maxtax > 0:
                    item_taxable = 'Y'
                else:
                    item_taxable = 'N'

                output_fh.write(self.PART_TEMPLATE.format(item_name=item_qb_name,item_description=item_name,sales_account=sales_account,item_price=item_maxprice,taxable=item_taxable))
            
        # Transaction columns: Date,Time,Sale,Discount,Tip,Total Collected,Transaction Type,Cash,Gift Card,Wallet,Card - Swiped,Card - Keyed,Other,Total Collected,Fee,Net Total,Card Brand,Card Number,Details,Payment ID,Device Name,Description
        tCur.execute('SELECT "Date","Time","Transaction_Type","Sale","Discount","Sales_Tax","Tip","Total_Collected","Fee","Net_Total","Card_Brand","Card_Number","Payment_ID","Description" FROM "transactions" WHERE "Sale" <> 0')
        output_fh.write(self.TRANS_HEAD)
        for date,time,transaction_type,subtotal,discount,sales_tax,tips,total,fee,net,card_brand,card_number,payment_id,description in tCur:
            (year, month, day) = map(int,date.split('-', 2))
            
            if transaction_type == 'Payment':
                qb_type = self.TRANS_TYPE_SALE
                isRefund = False
            elif transaction_type == 'Refund':
                qb_type = self.TRANS_TYPE_REFUND
                isRefund = True
            else:
                raise UnknownCSVTypeWarning('Skipping transaction {transaction_id}; unknown Transaction Type: {value!r}'.format(transaction_id=payment_id,value=transaction_type))
                # Skip the current transaction
                continue

            # Card Brand is only filled in for Card sales, so use it to detect card sales
            # TODO: support sales with multiple payment sources
            if not card_brand:
                cc_digits = 'Square Cash ' + ('REFUND: {0:s}'.format(description) if isRefund else 'Sale')
                till_account=config.accounts.cash
                payment_method=config.payments.cash
            else:
                cc_digits = '{0:s} {1:s}{2:s}'.format(card_brand,card_number.strip('="'),' (REFUND: {0:s})'.format(description) if isRefund else '')
                till_account=config.accounts.square
                payment_method=config.payments.square

            # Fix for missing transactions.Sales_Tax column
            if not isinstance(sales_tax, (int,long)):
                sales_tax = 0
            
            # Item columns: Date,Time,Details,Payment ID,Device Name,Category Name,Item Name,Price,Discount,Notes
            output_fh.write(self.TRANS_TEMPLATE.format(qb_type=qb_type, month=month, day=day, year=year, till_account=till_account, customer=config.names.customer, qb_class=config.classes.default, total=total, square_id=payment_id, memo=cc_digits, payment_method=payment_method, shipvia=config.payments.shipvia))

            iCur.execute('SELECT "Category_Name","Item_Name",CASE WHEN "Price" BETWEEN -1.0 AND 1.0 THEN COUNT(*)/100.0 ELSE COUNT(*) END AS \'Quantity\',CASE WHEN "Price" BETWEEN -1.0 AND 1.0 THEN "Price"*100 ELSE "Price" END AS \'Item_Price\',SUM("Discount") AS \'Discount\',SUM("Tax") AS \'Tax\' FROM "items" WHERE "Payment_ID" = ? AND "Date" = ? AND "Time" = ? GROUP BY "Category_Name","Item_Name","Price";',(payment_id,date,time,))
            for item_category,item_name,item_quantity,item_price,item_discount,item_tax in iCur:
                if item_category in config.salesMap:
                    sales_account = config.salesMap[item_category]
                else:
                    sales_account = config.accounts.sales

                if item_category in config.classMap:
                    item_class = config.classMap[item_category]
                else:
                    item_class = config.classes.default

                # Rewrite item name if specified in config
                if item_name in config.itemsMap:
                    item_name = config.itemsMap[item_name]

                # Fix for missing items.Tax column
                if not isinstance(item_tax, (int,long)):
                    item_tax = 0

                output_fh.write(self.ITEM_TEMPLATE.format(qb_type=qb_type, month=month, day=day, year=year, sales_account=sales_account, qb_class=item_class, total=-item_price*item_quantity, qty=-item_quantity, price=item_price, item_name=item_name))
                # Output one discount line per item, if any discount specified
                if item_discount < 0 or (isRefund and item_discount > 0):
                    output_fh.write(self.DISC_TEMPLATE.format(qb_type=qb_type, month=month, day=day, year=year, sales_account=config.discounts.account, qb_class=item_class, total=-item_discount, price=-item_discount, item_name=config.discounts.item))
            
            if sales_tax > 0 or (isRefund and sales_tax < 0):
                output_fh.write(self.TAX_TEMPLATE.format(qb_type=qb_type, month=month, day=day, year=year, sales_account=config.accounts.tax, qb_class=config.classes.default, total=-sales_tax, rate=abs(sales_tax/total*100.0), item_name=config.names.tax_item, vendor_name=config.names.tax_vendor))

            if tips > 0 or (isRefund and tips < 0):
                output_fh.write(self.TIPS_TEMPLATE.format(qb_type=qb_type, month=month, day=day, year=year, sales_account=config.accounts.tips, qb_class=config.classes.default, total=-tips, item_name=config.names.tips_item))

            # END of sales transaction
            output_fh.write(self.TRANS_FOOTER)
            
            

        fCur = self.db.cursor()
        output_fh.write(self.FEE_HEAD)
        fCur.execute('SELECT "Date","Fee","Payment_ID" FROM "transactions" WHERE "Fee" <> 0')
        for date, fee, payment_id in fCur:
            (year, month, day) = map(int,date.split('-', 2))
            output_fh.write(self.FEE_TEMPLATE.format(month=month, day=day, year=year, square_account=config.accounts.square, square_vendor=config.names.square, qb_class=config.classes.fees, amount=fee, amount_neg=-fee, square_id=payment_id, fees_account=config.accounts.fees))
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
    transactions_file = open(os.path.join(PROJECT_ROOT, config.cmdline.transactions), 'r')
    items_file = open(os.path.join(PROJECT_ROOT, config.cmdline.items), 'r')
    output_file = open(os.path.join(PROJECT_ROOT, config.cmdline.output), 'w')
    
    square = SquareReader()

    square.importTransactions(transactions_file)
    square.importItems(items_file)
    square.exportIif(output_file)
        
if __name__ == '__main__':
    main()

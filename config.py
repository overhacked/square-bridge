import ConfigParser, os
import argparse
from StringIO import StringIO

class Struct:
    def __init__(self, **entries): self.__dict__.update(entries)

# Parse command line options and arguments
cmdline_parser = argparse.ArgumentParser(description='Convert Square transactions and items from squareup.com CSV format to QuickBooks IIF format.',epilog='The transactions CSV and items CSV must cover the same date range, or some transactions will not be imported.')
cmdline_parser.add_argument('--customer','-C',help='QuickBooks Customer to whom imported transactions are assigned')
cmdline_parser.add_argument('--output','-o',required=True,help='name of the QuickBooks IIF file to write to',metavar='FILE.iif')
cmdline_parser.add_argument('--config','-c',help='Configuration file name',default='square.cfg',metavar='FILE.cfg')
cmdline_parser.add_argument('transactions',help='Transactions CSV file downloaded from squareup.com',default='transactions.csv')
cmdline_parser.add_argument('items',help='Items CSV file downloaded from squareup.com',default='items.csv')
cmdline = cmdline_parser.parse_args()

file_defaults = StringIO("""\
[accounts]
cash=Cash
square=Square
sales=Sales
fees=Square Fees
tax=Sales Tax Payable
tips=Tips

[discounts]
account=Discount Expenses
item=Industry Discount

[names]
square=Square
customer=Market Customers
tax_vendor=Sales Tax Vendor
tax_item=State Sales Tax

[payments]
square=Square
cash=Cash

[classes]
default=
fees=
""")

file_parser = ConfigParser.SafeConfigParser()
file_parser.optionxform = str
file_parser.readfp(file_defaults)
file_parser.readfp(open(cmdline.config))

classMap = dict()
if file_parser.has_section('categories'):
	for category,qb_class in file_parser.items('categories'):
		classMap[category] = qb_class

salesMap = dict()
if file_parser.has_section('sales'):
	for category,account in file_parser.items('sales'):
		salesMap[category] = account

for section in ['accounts','discounts','names','payments','classes']:
	sectionDict = dict()
	for k,v in file_parser.items(section):
		# Allow command line customer to override config file
		if section == 'names' and k == 'customer' and cmdline.customer is not None:
			v = cmdline.customer
		sectionDict[k] = v
	globals()[section] = Struct(**sectionDict)


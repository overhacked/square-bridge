import ConfigParser, os
from StringIO import StringIO

class Struct:
    def __init__(self, **entries): self.__dict__.update(entries)

defaults = StringIO("""\
[accounts]
cash=Cash
square=Square
sales=Sales
fees=Square Fees
tax=Sales Tax Payable

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

parser = ConfigParser.SafeConfigParser()
parser.optionxform = str
parser.readfp(defaults)
parser.readfp(open('square.cfg'))

classMap = dict()
if parser.has_section('categories'):
	for category,qb_class in parser.items('categories'):
		classMap[category] = qb_class

salesMap = dict()
if parser.has_section('sales'):
	for category,account in parser.items('sales'):
		salesMap[category] = account

for section in ['accounts','discounts','names','payments','classes']:
	sectionDict = dict()
	for k,v in parser.items(section):
		sectionDict[k] = v
	globals()[section] = Struct(**sectionDict)

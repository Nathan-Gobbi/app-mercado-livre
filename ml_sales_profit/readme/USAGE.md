**Load your products**

1. Go to *ML Sales Profit > Records > Import Stock Spreadsheet* and upload the
   stock spreadsheet. The sheet `Estoque` is read: the first row of each
   product holds its data and the Premium listing, and the next row with the
   same SKU holds the Classic listing.
2. Review the products in *Records > Products* and the listings in
   *Records > Listings*. Both can also be edited directly in Odoo.

**Analyze your sales**

1. In Mercado Livre, export the sales report of the period.
2. Go to *ML Sales Profit > Imports > Sales*, create a record, upload the file
   and click *Process*.
3. Check the summary, the sales without a registered listing (highlighted in
   yellow) and click *Download Excel Report* to get the spreadsheet.
4. Use *Analysis > Sales* to compare products and months in the graph and
   pivot views.

When a sale has a registered listing, processing the report automatically
deducts its units from the product stock. Reimporting the same sale does not
deduct it again. If the sale is later imported as cancelled, its units are
restored. Sales without a registered listing do not change stock.

**Close the statement**

1. In Mercado Pago, export the account statement.
2. Go to *ML Sales Profit > Imports > Statements*, upload it and click
   *Process*.
3. Write a note for each outflow and download the Excel report.

**Load your products**

1. Go to *ML Sales Profit > Records > Import Stock Spreadsheet* and upload the
   stock spreadsheet. The sheet `Estoque` is read: the first row of each
   product holds its data and the Premium listing, and the next row with the
   same SKU holds the Classic listing.
   A listing that sells multiple units stays below the physical product with
   an empty `Produto` cell, its own SKU (for example `NG0020_2`), and the
   optional `Qtd. por Venda` column set to `2`.
2. Review the products in *Records > Products* and the listings in
   *Records > Listings*. Both can also be edited directly in Odoo.

For a kit made from different products, open the kit product, enable **Is a
Kit** below NCM, and select the physical products in **Kit Products**. Each tag
contributes one unit to the kit. Registering or editing this composition does
not change stock. New kit sales deduct the selected products and keep the
kit's own stock unchanged.

**Analyze your sales**

1. In Mercado Livre, export the sales report of the period.
2. Go to *ML Sales Profit > Imports > Sales*, create a record, upload the file
   and click *Process*.
3. Check the summary, the sales without a registered listing (highlighted in
   yellow) and click *Download Excel Report* to get the spreadsheet.
4. Use *Analysis > Sales* to compare products and months in the graph and
   pivot views.

When a sale has a registered listing, processing the report automatically
deducts the listing units multiplied by its **Units per Sale** from the physical
product stock. For kits, the components and quantities actually deducted are
saved on the sale, so later composition changes do not rewrite history.
Reimporting the same sale does not deduct it again. If the sale is later
imported as cancelled, its original physical units are restored. Sales without
a registered listing do not change stock.

**Close the statement**

1. In Mercado Pago, export the account statement.
2. Go to *ML Sales Profit > Imports > Statements*, upload it and click
   *Process*.
3. Write a note for each outflow and download the Excel report.

**Prepare purchases**

1. Register contacts in *Records > Suppliers*.
2. Select the preferred supplier and minimum stock on each product.
3. Go to *Purchases > Purchase Requirement* to review products below minimum
   stock. Products without a supplier are identified separately.
4. Click *Generate PDF* to create one purchase section for each supplier.

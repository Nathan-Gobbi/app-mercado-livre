This module brings the Mercado Livre sales and account statement
spreadsheets into Odoo, so you can see how much you sold and how much you
earned with each product.

- **Records**: products with the same columns as a stock spreadsheet (SKU,
  manufacturer code, EAN, NCM, cost, stock, minimum stock, stock difference
  and stock value) and their Mercado Livre listings (Premium or Classic), with
  sale price, net amount, tax, packaging, net profit and profit percentage
  computed automatically.
- **Sales import**: upload the sales report exported by Mercado Livre and each
  sale is crossed with its listing to compute revenue, gross and net profit
  and margins. Cancelled sales, sales without SKU and sales without units are
  ignored. Importing overlapping periods (for example, a week and then the
  whole month) does not duplicate sales.
- **Statement import**: upload the account statement and get the list of
  outflows, leaving out the transaction types you choose to ignore, with a
  free note for each one.
- **Analysis**: graph, pivot and list views of sales and outflows by product,
  listing type and month.
- **Excel reports**: download the same summaries the original scripts
  produced ("Resumo_Estoque", "Resumo_Financeiro" and "Saídas").

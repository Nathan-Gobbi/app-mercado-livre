1. Give the users the *ML Sales Profit / Administrator* group. The admin user
   gets it on installation.
2. Go to *ML Sales Profit > Configuration > Settings* and set the tax rate
   applied over the sale price (6% by default).
3. Check the transaction types ignored by the statement import in
   *ML Sales Profit > Configuration > Ignored Transaction Types*.
4. Make sure the company currency is the Brazilian Real (BRL).

**Mercado Livre API**

1. Create an application in Mercado Livre Developers and register the exact
   callback URL shown in Odoo, for example
   `http://localhost:18069/ml/oauth/callback` for a local installation.
2. In *ML Sales Profit > Configuration > Settings*, enter the Application ID,
   Secret Key and the same Redirect URI registered in Mercado Livre.
3. Click *Connect Mercado Livre* and authorize the seller administrator account.
4. Keep *API synchronization* enabled. Paid and cancelled orders are synchronized
   every 15 minutes. Use *Synchronize Orders* to run it immediately.

Tokens and the Secret Key are restricted to system administrators. Never paste
them in source code, logs or support requests.

# %%
from __future__ import print_function
import csv
import datetime
import collections
import pandas as pd
import glob
import warnings
import os


warnings.filterwarnings("ignore")

def indent(text):
    return '\n'.join([ '    ' + line for line in text.split('\n')])

class InvoiceFile(object):

    def __init__(self, file_name):
        self.file_name = file_name
        self.invoices = []

    def _add_invoice_from_row(self, row):
        invoice = Invoice.from_row(row)
        self.invoices.append(invoice)

    def _add_detail_to_last_invoice_from_row(self, row):
        try:
            last_invoice = self.invoices[-1]
        except IndexError:
            raise Exception('Detail without invoice', ''.join(row))
        last_invoice._add_detail_from_row(row)

    @classmethod
    def from_file(cls, file_name):
        invoice_file = cls(file_name)
        with open(file_name, 'r', encoding='utf-8-sig') as csv_file:
            for index, raw_row in enumerate(csv.reader(csv_file, delimiter='|')):
                if index <= 1:  # Skip the second row
                    continue
                row = [field for field in raw_row]
                kind = row[0]
                if kind == 'M':
                    invoice_file._add_invoice_from_row(row)
                elif kind == 'D':
                    invoice_file._add_detail_to_last_invoice_from_row(row)
                else:
                    raise Exception('Unknown row type: ' + kind)
        return invoice_file
    
    # Export the result to a dataframe
    @classmethod
    def to_dataframe(cls, invoice):
        data = []
        for invoice in invoice.invoices:
            for detail in invoice.details:
                data.append({
                    'invoice_number': invoice.invoice_number,
                    'card_name': invoice.card_name,
                    'card_id': invoice.card_id,
                    'invoice_date': invoice.invoice_date,
                    'seller_id': invoice.seller_id,
                    'seller_name': invoice.seller_name,
                    'amount': invoice.amount,
                    'invoice_status': invoice.invoice_status,
                    'description': detail.description,
                    'amount': detail.amount,
                })
        df = pd.DataFrame(data)
        return df

class Invoice(object):

    FIELDS = collections.OrderedDict([
        ('card_name',      '載具名稱'),
        ('card_id',        '載具號碼'),
        ('invoice_date',   '發票日期'),
        ('seller_id',      '商店統編'),
        ('seller_name',    '商店店名'),
        ('invoice_number', '發票號碼'),
        ('amount',         '總金額　'),
        ('invoice_status', '發票狀態'),
    ])

    def __init__(self, **keywords):
        for name in self.FIELDS:
            setattr(self, name, keywords[name])
        if self.invoice_status not in ['開立', '作廢']:
            raise Exception('Invalid invoice status: {0}, not in 開立 or 作廢'.format(self.invoice_status))
        self.details = []

    @classmethod
    def from_row(cls, row):
        # Remove invoice identifier
        if row[0] != "M":
            raise Exception("Invalid row kind for invoice: {0}, it should be M".format(row[0]))
        row = row[1:]
        # Unpack fields
        fields = dict(zip(cls.FIELDS, row))
        fields['invoice_date'] = datetime.datetime.strptime(fields['invoice_date'], '%Y%m%d')
        fields['seller_id'] = int(fields['seller_id'])
        fields['amount'] = int(fields['amount'])
        fields['invoice_status'] = str(fields['invoice_status'])
        # OK, create the object
        invoice = cls(**fields)
        return invoice

    def _add_detail_from_row(self, row):
        detail = Detail.from_row(row)
        if self.invoice_number != detail.invoice_number:
            raise Exception("Different invoice number: invoice: {0}, detail: {0}".format(
                                self.invoice_number,
                                detail.invoice_number))
        self.details.append(detail)
    

class Detail(object):

    FIELDS = collections.OrderedDict([
        ('invoice_number', '發票號碼'),
        ('amount',         '小計'),
        ('description',    '品項名稱'),
    ])

    def __init__(self, **keywords):
        for name in self.FIELDS:
            setattr(self, name, keywords[name])

    @classmethod
    def from_row(cls, row):
        # Remove invoice identifier
        assert row[0] == "D"
        row = row[1:]
        # Unpack fields
        fields = dict(zip(cls.FIELDS, row))
        fields['amount'] = float(fields['amount'])
        # OK, create the object
        detail = cls(**fields)
        return detail


def invoice_tidying(df):
    df = df[df['invoice_status'] == '開立']
    df.drop(columns=[ 'card_name', 'card_id', 'seller_id', 'invoice_status'], inplace=True)
    df.reset_index(drop=True, inplace=True)

    for index, row in df.iterrows():
        if row['amount'] < 0:
            invoice_number = row['invoice_number']
            discount_description = row['description']
            discount_amount = row['amount']
            df.drop(index, inplace=True)

            filtered_df = df[df['invoice_number'] == invoice_number]
            max_amount_index = filtered_df['amount'].idxmax()

            if df.at[max_amount_index, 'amount'] + discount_amount < 0:
                total_amount = filtered_df['amount'].sum()
                for index, row in filtered_df.iterrows():
                    df.at[index, 'amount'] += round(discount_amount * row['amount'] / total_amount)
                    df.at[index, 'description'] += " *** " + discount_description
            else:
                df.at[max_amount_index, 'amount'] += discount_amount
                df.at[max_amount_index, 'description'] += " *** " + discount_description

    df = df[df['amount'] != 0]
    df.reset_index(drop=True, inplace=True)
    return df

if __name__ == "__main__":
    input_folder_path = 'input_folder'
    file_extension = '*.csv'
    file_names = glob.glob(f"{input_folder_path}/{file_extension}")

    for file_name in file_names:
        invoice = InvoiceFile.from_file(file_name)

        # Export the result to a dataframe
        df = InvoiceFile.to_dataframe(invoice)
        df = invoice_tidying(df)

        output_folder_path = 'output_folder'
        if not os.path.exists(output_folder_path):
            os.makedirs(output_folder_path)
        output_file_name = file_name.replace('.csv', '').replace('input_folder\\','') + '_tidied.xlsx'
        df.to_excel(f"{output_folder_path}/{output_file_name}")


# %%

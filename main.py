# %%
from __future__ import print_function
import csv
import warnings
import collections
import datetime
import pandas as pd
import os
import glob
import requests

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
        try:
            with open(file_name, 'r', encoding='utf-8-sig') as csv_file:
                for index, raw_row in enumerate(csv.reader(csv_file, delimiter='|')):
                    if index == 0:
                        if raw_row != ['表頭=M', '載具名稱', '載具號碼', '發票日期', '商店統編', '商店店名', '發票號碼', '總金額', '發票狀態', '']:
                            raise Exception('Invalid header: ' + file_name + '\n' + indent(str(raw_row)))
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
        except Exception as e:
            raise Exception('Invalid file: ' + file_name)
    
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
                    'amount': int(invoice.amount),
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

def export_file(df_multiple_files):
    # Find the start time and end time of the invoices
    start_YM = df_multiple_files['invoice_date'].min().strftime('%Y%m')
    end_YM = df_multiple_files['invoice_date'].max().strftime('%Y%m')

    df_multiple_files['amount'] = df_multiple_files['amount'].round().astype(int)
    df_multiple_files['YM'] = df_multiple_files['invoice_date'].dt.strftime('%Y%m')
    df_multiple_files.rename(columns={'invoice_date': 'Date', 'amount': 'Amount', 'description': 'Description', 'seller_name': 'Shop', 'invoice_number': 'Invoice Number'}, inplace=True)
    df_multiple_files = df_multiple_files[['YM', 'Date', 'Shop', 'Invoice Number','Amount', 'Description']]

    output_folder_path = 'output_folder'
    if not os.path.exists(output_folder_path):
        os.makedirs(output_folder_path)
    output_file_name = f'Invoice_tidied_{start_YM}_{end_YM}.xlsx'
    df_multiple_files.to_excel(f"{output_folder_path}/{output_file_name}", index=False)




# %%
if __name__ == "__main__":
    input_folder_path = 'input_folder'
    file_extension = '*.csv'
    file_names = glob.glob(f"{input_folder_path}/{file_extension}")
    df_multiple_files = pd.DataFrame()

    for file_name in file_names:
        invoice = InvoiceFile.from_file(file_name)

        # Merge the results into a dataframe
        df_single_file = InvoiceFile.to_dataframe(invoice)
        df_single_file = invoice_tidying(df_single_file)
        df_multiple_files = pd.concat([df_multiple_files, df_single_file])

    export_file(df_multiple_files)


# %%
import requests

def post_to_notion_database(get_all = True):
    notion_secret = "secret_YcOpxzmfN82Ogt8zzuFiJ5BKAM4D9C5ltiNfNNWYvNO"
    database_id = "67ee4c5e5b794d8892ae10d506046163"
    headers = {
        "Authorization": "Bearer " + notion_secret,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",  
        # Check what is the latest version here: https://developers.notion.com/reference/changes-by-version
    }
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    page_size = 100
    payload = {"page_size": page_size}
    response = requests.post(url, json=payload, headers=headers)
    data = response.json()
    print(response.status_code)
    print(response.text)
    results = data["results"]
    while data["has_more"] and get_all:
        payload = {"page_size": page_size, "start_cursor": data["next_cursor"]}
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        results.extend(data["results"])
    return results

pages = post_to_notion_database()
import json

# Assuming 'pages' is a list of dictionaries you're iterating over
pages_data = []
for page in pages:
    page_data = {
        "id": page["id"],
        "properties": page["properties"]
    }
    pages_data.append(page_data)

# Exporting to a JSON file
with open('pages_data.json', 'w', encoding="utf-8") as json_file:
    json.dump(pages_data, json_file, indent=4)
# %%
import re

title = "Bulbasaur"
text_content = "Bulbasaur is a small, quadrupedal amphibian Pokémon that has blue-green skin with darker patches."
type_text = "Grass"
notion_secret = "secret_YcOpxzmfN82Ogt8zzuFiJ5BKAM4D9C5ltiNfNNWYvNO"
database_id = "67ee4c5e5b794d8892ae10d506046163"


headers = {
    "Authorization": "Bearer " + notion_secret,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",  # Check the latest version here: https://developers.notion.com/reference/changes-by-version
}


def create_page(data: dict):
    create_url = "https://api.notion.com/v1/pages"
    payload = {"parent": {"database_id": database_id}, "properties": data}
    res = requests.post(create_url, headers=headers, json=payload)
    if res.status_code == 200:
        print(f"{res.status_code}: Page created successfully")
    else:
        print(f"{res.status_code}: Error during page creation")
    return res


properties = {
    "Type": {
        "id": "%3Dqql",
        "type": "select",
        "select": {
            "name": type_text,
        },
    },
    "Name": {
        "id": "title",
        "type": "title",
        "title": [
            {
                "type": "text",
                "text": {"content": title, "link": None},
                "annotations": {
                    "bold": False,
                    "italic": False,
                    "strikethrough": False,
                    "underline": False,
                    "code": False,
                    "color": "default",
                },
                "plain_text": title,
                "href": None,
            }
        ],
    },
}

properties_to_add = {
    "Description": {
                "id": "%3Dqql",
                "type": "rich_text",
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "\u91d1\u6d41\u624b\u7e8c\u8cbb",
                            "link": None
                        },
                        "annotations": {
                            "bold": False,
                            "italic": False,
                            "strikethrough": False,
                            "underline": False,
                            "code": False,
                            "color": "default"
                        },
                        "plain_text": "\u91d1\u6d41\u624b\u7e8c\u8cbb",
                        "href": None
                    }
                ]
            },
            "Amount": {
                "id": "VBJ%3F",
                "type": "number",
                "number": 15
            },
            "Category": {
                "id": "XeFw",
                "type": "multi_select",
                "multi_select": [
                    {
                        "id": "B{^U",
                        "name": "Utilities",
                        "color": "pink"
                    }
                ]
            },
            "Date": {
                "id": "fqkK",
                "type": "rich_text",
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "6/5/2024",
                            "link": None
                        },
                        "annotations": {
                            "bold": False,
                            "italic": False,
                            "strikethrough": False,
                            "underline": False,
                            "code": False,
                            "color": "default"
                        },
                        "plain_text": "6/5/2024",
                        "href": None
                    }
                ]
            },
            "Shop": {
                "id": "joux",
                "type": "rich_text",
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "\u5168\u652f\u4ed8\u96fb\u5b50\u652f\u4ed8\u80a1\u4efd\u6709\u9650\u516c\u53f8",
                            "link": None
                        },
                        "annotations": {
                            "bold": False,
                            "italic": False,
                            "strikethrough": False,
                            "underline": False,
                            "code": False,
                            "color": "default"
                        },
                        "plain_text": "\u5168\u652f\u4ed8\u96fb\u5b50\u652f\u4ed8\u80a1\u4efd\u6709\u9650\u516c\u53f8",
                        "href": None
                    }
                ]
            },
            "Name": {
                "id": "title",
                "type": "title",
                "title": [
                    {
                        "type": "text",
                        "text": {
                            "content": "BG98295741",
                            "link": None
                        },
                        "annotations": {
                            "bold": False,
                            "italic": False,
                            "strikethrough": False,
                            "underline": False,
                            "code": False,
                            "color": "default"
                        },
                        "plain_text": "BG98295741",
                        "href": None
                    }
                ]
            }
        }


response = create_page(properties)
page_block_id = response.json()["id"]


def edit_page(page_block_id, data: dict):
    edit_url = f"https://api.notion.com/v1/blocks/{page_block_id}/children"
    res = requests.patch(edit_url, headers=headers, json=data)
    if res.status_code == 200:
        print(f"{res.status_code}: Page edited successfully")
    else:
        print(f"{res.status_code}: Error during page editing")
    return res


chunks = re.findall(r".{1,2000}(?=\s|$)", text_content)

blocks = {
    "children": [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": chunk.strip(),
                        },
                    }
                ]
            },
        }
        for chunk in chunks
    ]
}

edit_page(page_block_id, blocks)
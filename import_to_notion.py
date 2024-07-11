# %%
from __future__ import print_function
import warnings
import pandas as pd
import os
import glob
import requests
import json
import os
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv(".env")

def get_notion_database(get_all = True):
    notion_secret = os.getenv("NOTION_SECRET")
    database_id = os.getenv("DATABASE_ID")
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
    results = data["results"]
    while data["has_more"] and get_all:
        payload = {"page_size": page_size, "start_cursor": data["next_cursor"]}
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        results.extend(data["results"])
    return results

def get_notion_database_invoice_numbers():
    results = get_notion_database()
    pages_data = []
    for page in results:
        page_data = {
            "id": page["id"],
            "properties": page["properties"]
        }
        pages_data.append(page_data)
    df = pd.json_normalize(pages_data)
    extracted_invoice_numbers = [item[0]["plain_text"] for item in df["properties.Invoice Number.rich_text"] if item]
    unique_invoice_numbers = pd.unique(extracted_invoice_numbers)
    return unique_invoice_numbers

def add_properties(YM, invoice_number, invoice_date, seller_name, amount, description):
    properties_to_add = {
        "Date": {
                "id": "%40rHL",
                "type": "date",
                "date": {
                    "start": invoice_date,
                    "end": None,
                    "time_zone": None
                }
            },
            "Shop": {
                "id": "Le%3DL",
                "type": "rich_text",
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": seller_name
                        },
                        "annotations": {
                            "bold": False,
                            "italic": False,
                            "strikethrough": False,
                            "underline": False,
                            "code": False,
                            "color": "default"
                        },
                        "plain_text": seller_name,
                        "href": None
                    }
                ]
            },
            "Description": {
                "id": "SjZ%7D",
                "type": "rich_text",
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": description,
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
                        "plain_text": description,
                        "href": None
                    }
                ]
            },
            "Category": {
                # TODO: Connect to GPT and analyse the shop and description to get the prediction of category
                "id": "Tri~",
                "type": "select",
                "select": None
            },
            "Amount": {
                "id": "iRIs",
                "type": "number",
                "number": amount
            },
            "Invoice Number": {
                "id": "%7DArt",
                "type": "rich_text",
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": invoice_number,
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
                        "plain_text": invoice_number,
                        "href": None
                    }
                ]
            },
            "YM": {
                "id": "title",
                "type": "title",
                "title": [
                    {
                        "type": "text",
                        "text": {
                            "content": YM,
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
                        "plain_text": YM,
                        "href": None
                    }
                ]
            }
    }
    return properties_to_add

def add_row(row):
    row_to_add = {
        "parent": {"database_id": os.getenv("DATABASE_ID")},
        # TODO: Use GPT to generate the emoji based on description
        # "icon": {
        #     "emoji": "🥬"
        # },
        "properties": add_properties(row["YM"], row["Invoice Number"], row["Date"].strftime("%Y-%m-%d"), row["Shop"], row["Amount"], row["Description"])
    }
    row_json_payload = json.dumps(row_to_add)
    return row_json_payload

def post_to_notion_database(row_json_payload, attempt_count):
    notion_secret = os.getenv("NOTION_SECRET")
    headers = {
        "Authorization": "Bearer " + notion_secret,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",  
        # Check what is the latest version here: https://developers.notion.com/reference/changes-by-version
    }
    url = f"https://api.notion.com/v1/pages"
    response = requests.post(url, data=row_json_payload, headers=headers)
    if response.status_code == 200:
        print("Successfully updated the database. Current progress:" + f" {attempt_count['success']} success, {attempt_count['fail']} fail")
        attempt_count["success"] += 1
    else:
        print("Failed to update the database for the following row:")
        print(response.text)
        attempt_count["fail"] += 1
    return attempt_count

if __name__ == "__main__":
    # Read the latest file in the output folder
    output_folder_path = 'output_folder/'
    files = glob.glob(output_folder_path + '*')
    latest_file = max(files, key=os.path.getmtime)
    df_multiple_files = pd.read_excel(latest_file)

    # Post the data to Notion, but let's first get the unique invoice numbers already saved in the database to avoid duplication
    unique_invoice_numbers = get_notion_database_invoice_numbers()
    df_post_to_notion = df_multiple_files[~df_multiple_files['Invoice Number'].isin(unique_invoice_numbers)]

    # Post the data to Notion, and keep track of the success and fail count
    attempt_count = {"success": 0, "fail": 0}
    for index, row in df_post_to_notion.iterrows():
        row_json_payload = add_row(row)
        attempt_count = post_to_notion_database(row_json_payload, attempt_count)

    print(f"Successfully uploaded {attempt_count['success']} rows")
    if attempt_count['fail'] > 0:
        print(f"Failed to upload {attempt_count['fail']} rows")


# %%

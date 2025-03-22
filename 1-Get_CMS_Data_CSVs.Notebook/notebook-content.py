# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse_name": "",
# META       "default_lakehouse_workspace_id": "",
# META       "known_lakehouses": []
# META     },
# META     "environment": {}
# META   }
# META }

# MARKDOWN ********************

# <div style="display: flex; align-items: center; justify-content: space-between;">
#     <span style="font-size: 40px; font-weight: bold;">
#         Step 1: Get Raw CMS Part D Data, Save to Files
#     </span>
#     <img src="https://upload.wikimedia.org/wikipedia/commons/2/2a/Centers_for_Medicare_and_Medicaid_Services_logo.svg" style="height: 90px;">
# </div>

# MARKDOWN ********************

# ##### 🤜🏻 Greg Beaumont @ Microsoft | Github Project

# MARKDOWN ********************

# ### ✅ Importers

# CELL ********************

import requests
import os
import pandas as pd
import time
import random

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************


# MARKDOWN ********************

# ### ✅ Set the Lakehouse Paths

# CELL ********************

# Get Workspace ID dynamically
WorkspaceID = notebookutils.runtime.context["currentWorkspaceId"]

# Define Lakehouse and storage path
bronze_lh_name = 'lh_cms_demo_bronze'
bronze_lh_id = notebookutils.lakehouse.get(bronze_lh_name, WorkspaceID)["id"]
raw_cms_dir = "Files/cms_raw"
raw_cms_path = f"abfss://{WorkspaceID}@onelake.dfs.fabric.microsoft.com/{bronze_lh_id}/{raw_cms_dir}"

# Local temp directory for downloads
local_temp_dir = "/tmp/cms_files"
os.makedirs(local_temp_dir, exist_ok=True)

# Create the /Files dir if it doesn't exist
notebookutils.fs.mkdirs(raw_cms_path)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### 🛜 Get the CMS Medicare Part D Data File List

# CELL ********************

# Step 1: Fetch the dataset JSON metadata from CMS
cms_url = "https://data.cms.gov/data.json"
title_filter = "Medicare Part D Prescribers - by Provider and Drug"

response = requests.get(cms_url, timeout=30)
if response.ok:
    data = response.json()
    dataset = data.get("dataset", [])

    csv_files = [
        {"downloadURL": distro["downloadURL"], "title": distro["title"]}
        for set in dataset if set["title"] == title_filter
        for distro in set.get("distribution", []) if distro.get("mediaType") == "text/csv"
    ]
else:
    error_message = f"Error downloading CMS metadata: HTTP {response.status_code}"
    print(error_message)
    notebookutils.notebook.exit(error_message, 1)

# Convert to Pandas DataFrame for easier handling
df_csv_files = pd.DataFrame(csv_files)

# Extract year from title
df_csv_files["year"] = df_csv_files["title"].str.extract(r"(\d{4})")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### 🧪 Functions for Download & Copy to OneLake

# CELL ********************

# Function to check if the file exists in OneLake
def file_exists_on_onelake(year):
    """Checks if a file already exists in OneLake (Bronze Storage)."""
    try:
        files = mssparkutils.fs.ls(raw_cms_path)  # List files in the destination directory
        return any(file.name == f"{year}.csv" for file in files)
    except Exception as e:
        print(f"⚠️ Could not check file existence for {year}.csv in OneLake: {e}")
        return False  # Assume it does not exist if the check fails

# Function to download and upload only if file doesn't exist
def download_and_upload(url, year):
    """Downloads a CMS data file and uploads it to OneLake, skipping if already present."""
    dest_path = f"{raw_cms_path}/{year}.csv"

    # Check if the file already exists in OneLake
    if file_exists_on_onelake(year):
        print(f"✅ File already exists in OneLake, skipping: {dest_path}")
        return dest_path

    local_file_path = os.path.join(local_temp_dir, f"{year}.csv")
    retries = 3
    attempt = 0

    while attempt < retries:
        try:
            # Download CSV
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            with open(local_file_path, "wb") as file:
                file.write(response.content)

            print(f"✅ Downloaded: {local_file_path}")

            # Upload to OneLake
            try:
                mssparkutils.fs.cp(f"file://{local_file_path}", dest_path)
                print(f"✅ Successfully uploaded to OneLake: {dest_path}")
                
                # Delete local file after successful upload
                os.remove(local_file_path)
                print(f"🗑️ Deleted local file: {local_file_path}")
                return dest_path

            except Exception as e:
                print(f"❌ Failed to upload {dest_path}: {e}")

        except requests.exceptions.RequestException as e:
            attempt += 1
            print(f"❌ Attempt {attempt} failed for {url}: {e}")
            if attempt < retries:
                time.sleep(random.randint(5, 15))
            else:
                print(f"❌ Failed to download {url} after {retries} attempts.")
                return None

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### 🚀 Download Each CMS File in the Data File List

# CELL ********************

# Process each CSV file one-by-one
df_csv_files["onelake_path"] = df_csv_files.apply(
    lambda row: download_and_upload(row["downloadURL"], row["year"]), axis=1
)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

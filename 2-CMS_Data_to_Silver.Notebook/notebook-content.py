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
# META     }
# META   }
# META }

# MARKDOWN ********************

# <div style="display: flex; align-items: center; justify-content: space-between;">
#     <span style="font-size: 40px; font-weight: bold;">
#         Step 2: Transform Raw CMS Part D Data, to Silver
#     </span>
#     <img src="https://upload.wikimedia.org/wikipedia/commons/2/2a/Centers_for_Medicare_and_Medicaid_Services_logo.svg" style="height: 90px;">
# </div>

# MARKDOWN ********************

# ### ✅ Importers

# CELL ********************

from notebookutils import mssparkutils
from pyspark.sql import functions as F
from pyspark.sql.types import LongType, DecimalType
from urllib.parse import urlparse
import os

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### ✅ Set the Lakehouse Paths

# CELL ********************


# Get Workspace ID dynamically
WorkspaceID = notebookutils.runtime.context["currentWorkspaceId"]

# Define Lakehouse and storage paths
bronze_lh_name = "lh_cms_bronze"
bronze_lh_id = notebookutils.lakehouse.get(bronze_lh_name, WorkspaceID)["id"]
raw_cms_path = f"abfss://{WorkspaceID}@onelake.dfs.fabric.microsoft.com/{bronze_lh_id}/Files/cms_raw"

silver_gold_lh_name = "lh_cms"
silver_gold_id = notebookutils.lakehouse.get(silver_gold_lh_name, WorkspaceID)["id"]
silver_table_name = "cms_provider_drug_costs"
silver_table_base_path = f"abfss://{WorkspaceID}@onelake.dfs.fabric.microsoft.com/{silver_gold_id}/Tables/silver_cms/"
silver_table_delta_path = f"abfss://{WorkspaceID}@onelake.dfs.fabric.microsoft.com/{silver_gold_id}/Tables/silver_cms/{silver_table_name}"

# Create the silver_gold schema (folder)
notebookutils.fs.mkdirs(silver_table_base_path)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### 👓 Read CMS Part D Raw Data into Dataframe + Metadata!

# CELL ********************

# Use the spark trick of adding full file metadata to the df
df = (
    spark.read.format("csv")
    .option("header", "true")
    .load(f"{raw_cms_path}/*.csv")
    .withColumn("file_path", F.input_file_name())
).selectExpr("*", "_metadata")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### 🧪 Transformation to Silver Dataset

# CELL ********************

# Extract Year from File Name from our handy _metadata column
df = df.withColumn("Year", 
    F.regexp_replace(F.col("_metadata.file_name"), ".csv", "").cast(LongType())
)

# Data Type Enforcement & Transformations
df_transformed = (
    df.withColumn("Tot_Drug_Cst", F.col("Tot_Drug_Cst").cast(DecimalType(10, 2)))
    .withColumn("Tot_30day_Fills", F.col("Tot_30day_Fills").cast(DecimalType(10, 2)))
    .withColumn("GE65_Tot_30day_Fills", F.col("GE65_Tot_30day_Fills").cast(DecimalType(10, 2)))
    .withColumn("GE65_Tot_Drug_Cst", F.col("GE65_Tot_Drug_Cst").cast(DecimalType(10, 2)))
    .withColumn("Prscrbr_City_State", F.concat(F.col("Prscrbr_City"), F.lit(", "), F.col("Prscrbr_State_Abrvtn")))
    .withColumn("Prscrbr_Full_Name", F.concat(F.col("Prscrbr_Last_Org_Name"), F.lit(", "), F.col("Prscrbr_First_Name")))
    .withColumn("Tot_Clms", F.col("Tot_Clms").cast(LongType()))
    .withColumn("Tot_Day_Suply", F.col("Tot_Day_Suply").cast(LongType()))
    .withColumn("Tot_Benes", F.col("Tot_Benes").cast(LongType()))
    .withColumn("GE65_Tot_Clms", F.col("GE65_Tot_Clms").cast(LongType()))
    .withColumn("GE65_Tot_Benes", F.col("GE65_Tot_Benes").cast(LongType()))
    .withColumn("GE65_Tot_Day_Suply", F.col("GE65_Tot_Day_Suply").cast(LongType()))
    .drop("file_path")  # Remove unneeded column
)


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### 👷 Write Silver Delta Table to Lakehouse

# CELL ********************

# Write to Delta Lake (Silver Table) with schema overwrite enabled
df_transformed.write \
    .option("overwriteSchema", "true") \
    .partitionBy('Year') \
    .mode("overwrite") \
    .format("delta") \
    .save(silver_table_delta_path)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

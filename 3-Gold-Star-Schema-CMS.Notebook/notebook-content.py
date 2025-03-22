# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "c09ab6df-f63c-4627-9855-cf11b566bc3d",
# META       "default_lakehouse_name": "lh_cms",
# META       "default_lakehouse_workspace_id": "c08071a7-fe5c-41f3-ae44-d54a314d8fad",
# META       "known_lakehouses": []
# META     },
# META     "environment": {}
# META   }
# META }

# MARKDOWN ********************

# <div style="display: flex; align-items: center; justify-content: space-between;">
#     <span style="font-size: 40px; font-weight: bold;">
#         Step 3: Transform Silver CMS Part D, Data to BI-Ready
#     </span>
#     <img src="https://upload.wikimedia.org/wikipedia/commons/2/2a/Centers_for_Medicare_and_Medicaid_Services_logo.svg" style="height: 90px;">
# </div>

# MARKDOWN ********************

# ### ✅ Set Variables

# CELL ********************

# Notebook and Lakehouse Config
NOTEBOOK_NAME = "3-Gold-Star-Schema-CMS"

# Get Workspace ID dynamically
WorkspaceID = notebookutils.runtime.context["currentWorkspaceId"]

# Define Lakehouse and storage paths
DEFAULT_LAKEHOUSE = "lh_cms"

# Define the Lakehouse Schemas
DEFAULT_SILVER_LAKEHOUSE_SCHEMA = "silver_cms"
DEFAULT_GOLD_LAKEHOUSE_SCHEMA = "curated_cms"

# Define the abfss:// paths for delta table & schema creation
# curated_lh_id = notebookutils.lakehouse.get(DEFAULT_LAKEHOUSE, WorkspaceID)["id"]
# curated_lh_abfss_path = f"abfss://{WorkspaceID}@onelake.dfs.fabric.microsoft.com/{curated_lh_id}/Tables/{DEFAULT_GOLD_LAKEHOUSE_SCHEMA}"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### 👷 Create Table: Date Dimension

# CELL ********************

from pyspark.sql.types import DateType
from pyspark.sql.functions import col

# Extract the year, add jan 1 to each for a date, new col
query = f"SELECT DISTINCT Year, CONCAT(CAST(Year AS STRING), '-01-01') \
AS Year_Date_Key FROM {DEFAULT_LAKEHOUSE}.{DEFAULT_SILVER_LAKEHOUSE_SCHEMA}.cms_provider_drug_costs"
dim_year_df = spark.sql(query)
dim_year_df = dim_year_df.withColumn("Year_Date_Key", col('Year_Date_Key').cast(DateType()))

#Write the table
dim_year_df.write.mode('overwrite').format('delta').saveAsTable(f"{DEFAULT_GOLD_LAKEHOUSE_SCHEMA}.cms_provider_dim_year")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### 👷 Create Table: Geography Dimension

# CELL ********************

# Define the query
query = f"""
    SELECT 
        Prscrbr_City, 
        Prscrbr_City_State, 
        Prscrbr_State_Abrvtn, 
        Prscrbr_State_FIPS, 
        MAX(Year) AS Max_Year, 
        MIN(Year) AS Min_Year,
        ROW_NUMBER() OVER (ORDER BY Prscrbr_State_Abrvtn, Prscrbr_City_State ASC) AS geo_key
    FROM {DEFAULT_LAKEHOUSE}.silver_cms.cms_provider_drug_costs
    GROUP BY 
        Prscrbr_City, 
        Prscrbr_City_State, 
        Prscrbr_State_Abrvtn, 
        Prscrbr_State_FIPS
"""

# Execute query in Spark SQL
dim_geo_df = spark.sql(query)

# Write to Delta Table
dim_geo_df.write.mode("overwrite").saveAsTable(f"{DEFAULT_GOLD_LAKEHOUSE_SCHEMA}.cms_provider_dim_geography")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### 👷 Create Table: Provider Dimension

# CELL ********************

# Define the SQL query
query = f"""
    SELECT 
        Prscrbr_First_Name,
        Prscrbr_Full_Name,
        Prscrbr_Last_Org_Name,
        Prscrbr_NPI,
        Prscrbr_Type,
        Prscrbr_Type_Src,
        MAX(Year) AS Max_Year,
        MIN(Year) AS Min_Year,
        ROW_NUMBER() OVER (ORDER BY Prscrbr_Full_Name, Prscrbr_NPI, Prscrbr_Type, Prscrbr_Type_Src ASC) AS provider_key
    FROM {DEFAULT_LAKEHOUSE}.silver_cms.cms_provider_drug_costs
    GROUP BY 
        Prscrbr_First_Name, 
        Prscrbr_Full_Name, 
        Prscrbr_Last_Org_Name, 
        Prscrbr_NPI, 
        Prscrbr_Type, 
        Prscrbr_Type_Src
"""

# Execute query in Spark SQL
dim_provider_df = spark.sql(query)

# Write to Delta Table
dim_provider_df.write.mode("overwrite").saveAsTable(f"{DEFAULT_GOLD_LAKEHOUSE_SCHEMA}.cms_provider_dim_provider")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### 👷 Create Table: Drug Cost Dimension

# CELL ********************

# Define the SQL query
query = f"""
    SELECT 
        Brnd_Name,
        Gnrc_Name,
        MAX(Year) AS Max_Year,
        MIN(Year) AS Min_Year,
        ROW_NUMBER() OVER (ORDER BY Brnd_Name, Gnrc_Name ASC) AS drug_key
    FROM {DEFAULT_LAKEHOUSE}.silver_cms.cms_provider_drug_costs
    GROUP BY Brnd_Name, Gnrc_Name
"""

# Execute query in Spark SQL
dim_drug_df = spark.sql(query)

# Write to Delta Table
dim_drug_df.write.mode("overwrite").saveAsTable(f"{DEFAULT_GOLD_LAKEHOUSE_SCHEMA}.cms_provider_dim_drug")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ### 👷 Create Table: Drug Cost Fact Table

# CELL ********************

# Define the SQL query
query = f"""
    SELECT 
        GE65_Bene_Sprsn_Flag,
        GE65_Sprsn_Flag,
        GE65_Tot_30day_Fills,
        GE65_Tot_Benes,
        GE65_Tot_Clms,
        GE65_Tot_Day_Suply,
        GE65_Tot_Drug_Cst,
        Tot_30day_Fills,
        Tot_Benes,
        Tot_Clms,
        Tot_Day_Suply,
        Tot_Drug_Cst,
        Year,
        b.drug_key,
        c.geo_key,
        d.provider_key
    FROM {DEFAULT_LAKEHOUSE}.silver_cms.cms_provider_drug_costs a
    LEFT OUTER JOIN {DEFAULT_LAKEHOUSE}.{DEFAULT_GOLD_LAKEHOUSE_SCHEMA}.cms_provider_dim_drug b 
        ON a.Brnd_Name = b.Brnd_Name 
        AND a.Gnrc_Name = b.Gnrc_Name
    LEFT OUTER JOIN {DEFAULT_LAKEHOUSE}.{DEFAULT_GOLD_LAKEHOUSE_SCHEMA}.cms_provider_dim_geography c 
        ON a.Prscrbr_City_State IS NOT DISTINCT FROM c.Prscrbr_City_State
    LEFT OUTER JOIN {DEFAULT_LAKEHOUSE}.{DEFAULT_GOLD_LAKEHOUSE_SCHEMA}.cms_provider_dim_provider d 
        ON a.Prscrbr_Full_Name IS NOT DISTINCT FROM d.Prscrbr_Full_Name 
        AND a.Prscrbr_NPI = d.Prscrbr_NPI 
        AND a.Prscrbr_Type IS NOT DISTINCT FROM d.Prscrbr_Type 
        AND a.Prscrbr_Type_Src = d.Prscrbr_Type_Src
"""

# Execute query in Spark SQL
drug_costs_star_df = spark.sql(query)

# Write to OneLake Table
drug_costs_star_df.write.mode("overwrite").format("delta").option("overwriteSchema", "true").partitionBy('Year').saveAsTable(f"{DEFAULT_GOLD_LAKEHOUSE_SCHEMA}.cms_provider_drug_costs_star")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

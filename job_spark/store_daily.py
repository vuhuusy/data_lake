from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date, when, udf, regexp_extract
from pyspark.sql.types import StringType
from datetime import datetime, timedelta
import time

# Tạo SparkSession
spark = SparkSession.builder \
    .appName("DIM_LIQUOR_STORE_DAILY") \
    .config("spark.sql.legacy.timeParserPolicy", "LEGACY") \
    .config("spark.sql.shuffle.partitions", 1) \
    .getOrCreate()

# Tính toán ngày n-1
n1 = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

# Đường dẫn file nguồn và thư mục đích trên HDFS
input_path = f"hdfs://namenode:9000/raw_zone/sales/bi_core/country=usa/state=iowa/rd_liquor_store/partition={n1}/*"
output_path = f"hdfs://namenode:9000/gold_zone/sales/bi_core/country=usa/state=iowa/dim_liquor_store/partition={n1}/"

# Định nghĩa schema của bảng dim_liquor_store
schema = """
    store STRING,
    name STRING,
    store_status STRING,
    address STRING,
    city STRING,
    state STRING,
    zipcode STRING,
    store_address STRING,
    date STRING,
    partition STRING
"""

# Ghi lại thời gian bắt đầu
start_time = time.time()

# Đọc tất cả các file từ folder HDFS không có header
df = spark.read.csv(input_path, schema=schema, header=False)

# Đổi tên các cột
column_renamed_df = df.withColumnRenamed("store", "id") \
                     .withColumnRenamed("store_status", "status") \
                     .withColumnRenamed("date", "update_date")

# Xử lý cột status: thay A thành active, I thành inactive
column_renamed_df = column_renamed_df.withColumn("status", when(col("status") == "A", "active")
                                                  .when(col("status") == "I", "inactive")
                                                  .otherwise(col("status")))

# Mapping giá trị cho cột state
def map_state(state):
    mapping = {
        "AZ": "Arizona",
        "CO": "Colorado",
        "IA": "Iowa",
        "IL": "Illinois",
        "OR": "Oregon"
    }
    return mapping.get(state, state)

map_state_udf = udf(map_state, StringType())
column_renamed_df = column_renamed_df.withColumn("state", map_state_udf(col("state")))

# Chuyển kiểu dữ liệu cột update_date thành DATE
column_renamed_df = column_renamed_df.withColumn("update_date", to_date(col("update_date"), "yyyy-MM-dd"))

# Tách latitude (vĩ độ) từ cột store_address
column_renamed_df = column_renamed_df.withColumn("latitude", regexp_extract(col("store_address"), r"POINT\s*\(-?\d+\.\d+\s*(-?\d+\.\d+)\)", 1).cast("double"))

# Tách longitude (kinh độ) từ cột store_address
column_renamed_df = column_renamed_df.withColumn("longitude", regexp_extract(col("store_address"), r"POINT\s*\((-?\d+\.\d+)\s*-?\d+\.\d+\)", 1).cast("double"))

# Bỏ cột store_address vì đã tách thành latitude và longitude
column_renamed_df = column_renamed_df.drop("store_address")

# Ghi dữ liệu đã xử lý ra HDFS
column_renamed_df.coalesce(1).write \
    .mode("overwrite") \
    .parquet(output_path)

# Ghi lại thời gian kết thúc
end_time = time.time()
execution_time = end_time - start_time

# Số bản ghi
row_count = column_renamed_df.count()

print("Job completed successfully!")
print("Output path:", output_path)
print("Execution time (seconds):", round(execution_time, 2))
print("Number of rows written:", row_count)

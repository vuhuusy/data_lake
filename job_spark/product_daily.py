from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date
from datetime import datetime, timedelta
import time

# Tạo SparkSession
spark = SparkSession.builder \
    .appName("DIM_LIQUOR_PRODUCT_DAILY") \
    .config("spark.sql.legacy.timeParserPolicy", "LEGACY") \
    .config("spark.sql.shuffle.partitions", 1) \
    .getOrCreate()

# Tính toán ngày n-1
n1 = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

# Đường dẫn thư mục raw và thư mục đích trên HDFS
input_path = f"hdfs://namenode:9000/raw_zone/sales/bi_core/country=usa/state=iowa/rd_liquor_product/partition={n1}/*"
output_path = f"hdfs://namenode:9000/gold_zone/sales/bi_core/country=usa/state=iowa/dim_liquor_product/partition={n1}/"

# Schema của bảng rd_liquor_product
schema = """
    itemno STRING,
    category_name STRING,
    im_desc STRING,
    vendor_no STRING,
    vendor_name STRING,
    bottle_volume_ml DOUBLE,
    pack DOUBLE,
    innerpack DOUBLE,
    age DOUBLE,
    proof DOUBLE,
    listdate STRING,
    upc STRING,
    scc STRING,
    state_bottle_cost DOUBLE,
    state_case_cost DOUBLE,
    state_bottle_retail DOUBLE,
    date STRING,
    partition STRING
"""

# Ghi lại thời gian bắt đầu
start_time = time.time()

# Đọc file dữ liệu raw từ HDFS
df = spark.read.csv(input_path, schema=schema, header=False)

# Tạo trường ABV
df = df.withColumn("ABV", col("proof") / 200)

# Sắp xếp lại thứ tự các cột
columns_order = [
    "itemno", "category_name", "im_desc", "vendor_no", "vendor_name", "bottle_volume_ml", 
    "pack", "innerpack", "age", "proof", "ABV", "listdate", "upc", "scc", 
    "state_bottle_cost", "state_case_cost", "state_bottle_retail", "date", "partition"
]
df = df.select(columns_order)

# Convert dữ liệu cột listdate và date thành kiểu DATE
df = df.withColumn("listdate", to_date(col("listdate"), "yyyy-MM-dd"))
df = df.withColumn("date", to_date(col("date"), "yyyy-MM-dd"))

# Số bản ghi
row_count = df.count()

# Ghi dữ liệu vào HDFS
df.coalesce(1).write \
    .mode("overwrite") \
    .parquet(output_path)

# Ghi lại thời gian kết thúc
end_time = time.time()
execution_time = end_time - start_time

print("Job completed successfully!")
print("Output path:", output_path)
print("Execution time (seconds):", round(execution_time, 2))
print("Number of rows written:", row_count)

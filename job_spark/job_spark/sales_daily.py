from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date, expr
from datetime import datetime, timedelta
import time


# Tạo SparkSession
spark = SparkSession.builder \
    .appName("FACT_LIQUOR_SALES_DAILY") \
    .config("spark.sql.legacy.timeParserPolicy", "LEGACY") \
    .config("spark.sql.shuffle.partitions", 3) \
    .getOrCreate()

# Tính toán ngày N-1
n1 = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

# Đường dẫn file nguồn và thư mục đích trên HDFS
input_path = f"hdfs://namenode:9000/raw_zone/sales/bi_core/country=usa/state=iowa/rd_liquor_sales/partition={n1}/*"
output_path = f"hdfs://namenode:9000/gold_zone/sales/bi_core/country=usa/state=iowa/fact_liquor_sales/partition={n1}/"

# Định nghĩa schema của bảng iowa_liquor_sales
schema = """
    kafka_topic STRING,
    process_date STRING,
    hour_id STRING,
    invoice_line_no STRING,
    date STRING,
    store STRING,
    name STRING,
    address STRING,
    city STRING,
    zipcode STRING,
    store_location STRING,
    county_number STRING,
    county STRING,
    category STRING,
    category_name STRING,
    vendor_no STRING,
    vendor_name STRING,
    itemno STRING,
    im_desc STRING,
    pack INT,
    bottle_volume_ml DOUBLE,
    state_bottle_cost DOUBLE,
    state_bottle_retail DOUBLE,
    sale_bottles INT,
    sale_dollars DOUBLE,
    sale_liters DOUBLE,
    sale_gallons DOUBLE,
    partition STRING
"""

# Ghi lại thời gian bắt đầu
start_time = time.time()

# Đọc tất cả các file từ folder HDFS không có header
df = spark.read.csv(input_path, schema=schema, header=False)

# Kiểm tra dữ liệu đầu vào
if df.rdd.isEmpty():
    raise ValueError("Input data is empty. Please check the input path or data availability.")

# Chuyển kiểu dữ liệu cột process_date thành DATE và đổi tên thành date_key
df = df.withColumn("date_key", to_date(col("process_date"), "yyyy-MM-dd"))

# Đổi tên các cột store → store_id, itemno → product_id
df = df.withColumnRenamed("store", "store_id") \
       .withColumnRenamed("itemno", "product_id")

# Tạo các cột fact
df = df.withColumn("cost_dollars", expr("state_bottle_cost * sale_bottles"))  # Cost in dollars
df = df.withColumn("gross_profit", expr("sale_dollars - cost_dollars"))  # Gross Profit

# Chọn các cột cần thiết
output_df = df.select(
    "invoice_line_no",
    "date_key",
    "store_id",
    "product_id",
    "sale_bottles",
    "sale_dollars",
    "cost_dollars",
    "gross_profit",  # Gross Profit
    "sale_liters",
    "sale_gallons",
    "partition"
)


# Ghi dữ liệu đã xử lý ra HDFS
output_df.write \
    .mode("overwrite") \
    .parquet(output_path)

# Ghi lại thời gian kết thúc
end_time = time.time()
execution_time = end_time - start_time

# Số bản ghi
row_count = output_df.count()

print("Job completed successfully!")
print("Output path:", output_path)
print("Execution time (seconds):", round(execution_time, 2))
print("Number of rows written:", row_count)

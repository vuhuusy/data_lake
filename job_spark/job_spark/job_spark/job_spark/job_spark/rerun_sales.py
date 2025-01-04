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

# Hàm lặp qua khoảng thời gian
def date_range(start_date, end_date):
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)

# Khoảng thời gian cần xử lý
start_date = datetime.strptime("2024-12-01", "%Y-%m-%d")
end_date = datetime.strptime("2025-01-02", "%Y-%m-%d")

# Schema của bảng iowa_liquor_sales
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
overall_start_time = time.time()

# Lặp qua từng ngày trong khoảng thời gian
for current_date in date_range(start_date, end_date):
    n1 = current_date.strftime("%Y%m%d")  # Định dạng ngày theo yyyyMMdd

    # Đường dẫn file nguồn và thư mục đích trên HDFS
    input_path = f"hdfs://namenode:9000/raw_zone/sales/bi_core/country=usa/state=iowa/rd_liquor_sales/partition={n1}/*"
    output_path = f"hdfs://namenode:9000/gold_zone/sales/bi_core/country=usa/state=iowa/fact_liquor_sales/partition={n1}/"

    print(f"Processing date: {n1}")
    
    try:
        # Đọc tất cả các file từ folder HDFS không có header
        df = spark.read.csv(input_path, schema=schema, header=False)

        # Kiểm tra dữ liệu đầu vào
        if df.rdd.isEmpty():
            print(f"No data found for date: {n1}. Skipping...")
            continue

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

        # Số bản ghi
        row_count = output_df.count()

        # Ghi dữ liệu đã xử lý ra HDFS
        output_df.write \
            .mode("overwrite") \
            .parquet(output_path)

        print(f"Job completed successfully for date: {n1}")
        print(f"Output path: {output_path}")
        print(f"Number of rows written: {row_count}")

    except Exception as e:
        print(f"Failed to process date {n1}. Error: {str(e)}")

# Ghi lại thời gian kết thúc
overall_end_time = time.time()
execution_time = overall_end_time - overall_start_time

print("All jobs completed!")
print("Total execution time (seconds):", round(execution_time, 2))

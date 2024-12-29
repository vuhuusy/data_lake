from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date, lit
from datetime import datetime, timedelta
import time

# Tạo SparkSession
spark = SparkSession.builder \
    .appName("DIM_LIQUOR_PRODUCT_DAILY") \
    .config("spark.sql.legacy.timeParserPolicy", "LEGACY") \
    .config("spark.sql.shuffle.partitions", 1) \
    .getOrCreate()

# Hàm lấy giờ Việt Nam (UTC+7)
def get_vietnam_time():
    now_utc = datetime.utcnow()
    return now_utc + timedelta(hours=7)

# Khoảng thời gian cần xử lý
start_date = datetime.strptime("2024-12-01", "%Y-%m-%d")
end_date = datetime.strptime("2024-12-28", "%Y-%m-%d")

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
overall_start_time = time.time()

# Lặp qua từng ngày trong khoảng thời gian
current_date = start_date
while current_date <= end_date:
    # Lấy ngày theo múi giờ Việt Nam
    vietnam_date = current_date + timedelta(hours=7)
    n1 = vietnam_date.strftime("%Y%m%d")  # Định dạng ngày theo yyyyMMdd

    # Đường dẫn file nguồn và thư mục đích trên HDFS
    input_path = f"hdfs://namenode:9000/raw_zone/sales/bi_core/country=usa/state=iowa/rd_liquor_product/partition={n1}/*"
    output_path = f"hdfs://namenode:9000/gold_zone/sales/bi_core/country=usa/state=iowa/dim_liquor_product/partition={n1}/"

    print(f"Processing date: {n1}")
    
    try:
        # Đọc file dữ liệu raw từ HDFS
        df = spark.read.csv(input_path, schema=schema, header=False)

        # Đổi tên các cột
        df = df.withColumnRenamed("itemno", "id") \
               .withColumnRenamed("category_name", "category") \
               .withColumnRenamed("im_desc", "product_desc") \
               .withColumnRenamed("vendor_no", "vendor_id") \
               .withColumnRenamed("date", "update_date")

        # Tạo trường ABV
        df = df.withColumn("ABV", col("proof") / 200)

        # Sắp xếp lại thứ tự các cột
        columns_order = [
            "id", "category", "product_desc", "vendor_id", "vendor_name", "bottle_volume_ml", 
            "pack", "innerpack", "age", "proof", "ABV", "listdate", "upc", "scc", 
            "state_bottle_cost", "state_case_cost", "state_bottle_retail", "update_date", "partition"
        ]
        df = df.select(columns_order)

        # Convert dữ liệu cột listdate và update_date thành kiểu DATE
        df = df.withColumn("listdate", to_date(col("listdate"), "yyyy-MM-dd"))
        df = df.withColumn("update_date", to_date(lit(n1), "yyyyMMdd"))

        # Số bản ghi
        row_count = df.count()

        # Ghi dữ liệu vào HDFS
        df.coalesce(1).write \
            .mode("overwrite") \
            .parquet(output_path)

        print(f"Job completed successfully for date: {n1}")
        print(f"Output path: {output_path}")
        print(f"Number of rows written: {row_count}")

    except Exception as e:
        print(f"Failed to process date {n1}. Error: {str(e)}")

    # Tăng ngày lên 1
    current_date += timedelta(days=1)

# Ghi lại thời gian kết thúc
overall_end_time = time.time()
execution_time = overall_end_time - overall_start_time

print("All jobs completed!")
print("Total execution time (seconds):", round(execution_time, 2))

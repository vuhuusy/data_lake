from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, sum, to_date, split, explode, from_csv, col, to_date, to_timestamp, sum as _sum
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType
)
import time
import logging

# Cấu hình logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("LIQUOR_SALES_BI_STREAMING")

# Tạo SparkSession
spark = SparkSession.builder \
    .appName("LIQUOR_SALES_BI_STREAMING") \
    .config("spark.sql.shuffle.partitions", 3) \
    .config("spark.sql.legacy.timeParserPolicy", "LEGACY") \
    .config("spark.streaming.stopGracefullyOnShutdown", "true") \
    .getOrCreate()

# Định nghĩa schema của Kafka message
schema_csv = (
    "kafka_topic STRING, "
    "process_date STRING, "
    "hour_id STRING, "
    "invoice_line_no STRING, "
    "date STRING, "
    "store STRING, "
    "name STRING, "
    "address STRING, "
    "city STRING, "
    "zipcode STRING, "
    "store_location STRING, "
    "county_number STRING, "
    "county STRING, "
    "category STRING, "
    "category_name STRING, "
    "vendor_no STRING, "
    "vendor_name STRING, "
    "itemno STRING, "
    "im_desc STRING, "
    "pack INT, "
    "bottle_volume_ml INT, "
    "state_bottle_cost DOUBLE, "
    "state_bottle_retail DOUBLE, "
    "sale_bottles INT, "
    "sale_dollars DOUBLE, "
    "sale_liters DOUBLE, "
    "sale_gallons DOUBLE"
)

# Đọc dữ liệu từ Kafka
raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka0:9092,kafka1:9092,kafka2:9092") \
    .option("subscribe", "liquor_sales") \
    .option("failOnDataLoss", "false") \
    .option("startingOffsets", "earliest") \
    .option("maxOffsetsPerTrigger", 20) \
    .load()

# Xử lý message chứa nhiều bản ghi
raw_sales = raw_stream.selectExpr("CAST(value AS STRING) as message") \
    .select(explode(split(col("message"), "\\n")).alias("line")) \
    .select(from_csv(col("line"), schema_csv).alias("data")) \
    .select("data.*")


# Xử lý bảng f001_store_tot_sales
f001_store_tot_sales = raw_sales.groupBy(
    "kafka_topic",
    to_date("process_date", 'yyyy-MM-dd').alias("prd_id"),
    "hour_id",
    "name",
    "city"
).agg(
    sum("sale_bottles").alias("sale_bottles"),
    sum(col("state_bottle_cost") * col("sale_bottles")).alias("tot_cost_dollars"),
    sum("sale_dollars").alias("tot_sale_dollars"),
    (sum("sale_dollars") - sum(col("state_bottle_cost") * col("sale_bottles"))).alias("tot_profit_dollars"),
    sum("sale_liters").alias("sale_liters"),
    sum("sale_gallons").alias("sale_gallons")
).withColumnRenamed("name", "store_name").withColumnRenamed("city", "store_city")

# Xử lý bảng f002_vendor_tot_sales
f002_vendor_tot_sales = raw_sales.groupBy(
    "kafka_topic",
    to_date("process_date", 'yyyy-MM-dd').alias("prd_id"),
    "hour_id",
    "vendor_name"
).agg(
    sum("sale_bottles").alias("sale_bottles"),
    sum(col("state_bottle_cost") * col("sale_bottles")).alias("tot_cost_dollars"),
    sum("sale_dollars").alias("tot_sale_dollars"),
    (sum("sale_dollars") - sum(col("state_bottle_cost") * col("sale_bottles"))).alias("tot_profit_dollars"),
    sum("sale_liters").alias("sale_liters"),
    sum("sale_gallons").alias("sale_gallons")
)

# Xử lý bảng f003_product_tot_sales
f003_product_tot_sales = raw_sales.groupBy(
    "kafka_topic",
    to_date("process_date", 'yyyy-MM-dd').alias("prd_id"),
    "hour_id",
    "category_name",
    "im_desc"
).agg(
    sum("sale_bottles").alias("sale_bottles"),
    sum(col("state_bottle_cost") * col("sale_bottles")).alias("tot_cost_dollars"),
    sum("sale_dollars").alias("tot_sale_dollars"),
    (sum("sale_dollars") - sum(col("state_bottle_cost") * col("sale_bottles"))).alias("tot_profit_dollars"),
    sum("sale_liters").alias("sale_liters"),
    sum("sale_gallons").alias("sale_gallons")
)

# Ghi dữ liệu vào bộ nhớ tạm
query_store = f001_store_tot_sales.writeStream \
    .outputMode("complete") \
    .format("memory") \
    .queryName("f001_store_tot_sales") \
    .option("checkpointLocation", "hdfs://namenode:9000/work_zone/tmp/bi_streaming/spark/checkpoint/f001_store_tot_sales") \
    .trigger(processingTime="1 minute") \
    .start()

query_vendor = f002_vendor_tot_sales.writeStream \
    .outputMode("complete") \
    .format("memory") \
    .queryName("f002_vendor_tot_sales") \
    .option("checkpointLocation", "hdfs://namenode:9000/work_zone/tmp/bi_streaming/spark/checkpoint/f002_vendor_tot_sales") \
    .trigger(processingTime="1 minute") \
    .start()

query_product = f003_product_tot_sales.writeStream \
    .outputMode("complete") \
    .format("memory") \
    .queryName("f003_product_tot_sales") \
    .option("checkpointLocation", "hdfs://namenode:9000/work_zone/tmp/bi_streaming/spark/checkpoint/f003_product_tot_sales") \
    .trigger(processingTime="1 minute") \
    .start()

# Trích xuất numInputRows để kiểm tra dữ liệu mới
while True:
    try:
        for query_name, path in zip([
            "f001_store_tot_sales", "f002_vendor_tot_sales", "f003_product_tot_sales"
        ], [
            "hdfs://namenode:9000/gold_zone/sales/bi_core/streaming/country=usa/state=iowa/f001_store_tot_sales",
            "hdfs://namenode:9000/gold_zone/sales/bi_core/streaming/country=usa/state=iowa/f002_vendor_tot_sales",
            "hdfs://namenode:9000/gold_zone/sales/bi_core/streaming/country=usa/state=iowa/f003_product_tot_sales"
        ]):
            query = next((q for q in spark.streams.active if q.name == query_name), None)
            if query:
                progress = query.lastProgress
                if progress and progress['sources'][0]['numInputRows'] > 0:
                    data_from_memory = spark.sql(f"SELECT * FROM {query_name}")
                    data_from_memory.write.mode("append").parquet(path)
                    spark.catalog.uncacheTable(query_name)

                    # Ghi ra console
                    data_from_memory.show(truncate=False)
    except Exception as e:
        logger.error(f"Error while writing to HDFS: {e}")

    # Đợi một khoảng thời gian trước khi xử lý batch tiếp theo
    time.sleep(60)

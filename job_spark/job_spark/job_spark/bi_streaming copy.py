import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import split, explode, from_csv, col, to_date, to_timestamp, sum as _sum

# Tắt log INFO
logging.getLogger("py4j").setLevel(logging.ERROR)

# 1. Tạo SparkSession
spark = SparkSession.builder \
    .appName("Kafka Multiline Message Processor with Aggregation") \
    .config("spark.streaming.stopGracefullyOnShutdown", "true") \
    .config("spark.sql.legacy.timeParserPolicy", "LEGACY") \
    .config("spark.sql.shuffle.partitions", 3) \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# 2. Định nghĩa schema dạng CSV
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

# 3. Đọc dữ liệu từ Kafka
kafka_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka0:9092,kafka1:9092,kafka2:9092") \
    .option("subscribe", "liquor_sales") \
    .option("startingOffsets", "earliest") \
    .load()

# 4. Xử lý message chứa nhiều dòng
parsed_stream = kafka_stream.selectExpr("CAST(value AS STRING) as message") \
    .select(explode(split(col("message"), "\n")).alias("line")) \
    .select(from_csv(col("line"), schema_csv).alias("data")) \
    .select("data.*")

# 5. Xử lý dữ liệu: Thêm watermark, chuyển đổi dữ liệu và tổng hợp
aggregated_stream = parsed_stream \
    .withColumn("process_timestamp", to_timestamp(col("process_date"), "yyyy-MM-dd HH:mm:ss")) \
    .withColumn("prd_id", to_date(col("process_date"), "yyyy-MM-dd")) \
    .withWatermark("process_timestamp", "1 minute") \
    .groupBy(
        col("kafka_topic"),
        col("prd_id"),
        col("hour_id"),
        col("name").alias("store_name"),
        col("city").alias("store_city"),
        col("county").alias("store_county")
    ).agg(
        _sum("sale_bottles").alias("sale_bottles"),
        _sum(col("state_bottle_cost") * col("sale_bottles")).alias("tot_cost_dollars"),
        _sum("sale_dollars").alias("tot_sale_dollars"),
        (_sum("sale_dollars") - _sum(col("state_bottle_cost") * col("sale_bottles"))).alias("tot_profit_dollars"),
        _sum("sale_liters").alias("sale_liters"),
        _sum("sale_gallons").alias("sale_gallons")
    )

# 6. Ghi dữ liệu tổng hợp ra console
query = aggregated_stream.writeStream \
    .outputMode("update") \
    .format("console") \
    .option("truncate", "false") \
    .trigger(processingTime="1 minute") \
    .start()

# 7. Đợi job Spark hoàn thành
query.awaitTermination()

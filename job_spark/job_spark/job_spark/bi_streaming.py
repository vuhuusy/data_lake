from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_csv, split, explode, sum as _sum, to_date
import time
import logging
import mysql.connector
from mysql.connector import Error
from datetime import datetime

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
    .option("maxOffsetsPerTrigger", 100) \
    .load()

# Xử lý message chứa nhiều bản ghi
raw_sales = raw_stream.selectExpr("CAST(value AS STRING) as message") \
    .select(explode(split(col("message"), "\\n")).alias("line")) \
    .select(from_csv(col("line"), schema_csv).alias("data")) \
    .select("data.*")

# Tính toán aggregations
f001_store_tot_sales = raw_sales.groupBy(
    "kafka_topic",
    to_date("process_date", 'yyyy-MM-dd').alias("prd_id"),
    "hour_id",
    "name",
    "city"
).agg(
    _sum("sale_bottles").alias("sale_bottles"),
    _sum(col("state_bottle_cost") * col("sale_bottles")).alias("tot_cost_dollars"),
    _sum("sale_dollars").alias("tot_sale_dollars"),
    (_sum("sale_dollars") - _sum(col("state_bottle_cost") * col("sale_bottles"))).alias("tot_profit_dollars"),
    _sum("sale_liters").alias("sale_liters"),
    _sum("sale_gallons").alias("sale_gallons")
).withColumnRenamed("name", "store_name").withColumnRenamed("city", "store_city")

f002_vendor_tot_sales = raw_sales.groupBy(
    "kafka_topic",
    to_date("process_date", 'yyyy-MM-dd').alias("prd_id"),
    "hour_id",
    "vendor_name"
).agg(
    _sum("sale_bottles").alias("sale_bottles"),
    _sum(col("state_bottle_cost") * col("sale_bottles")).alias("tot_cost_dollars"),
    _sum("sale_dollars").alias("tot_sale_dollars"),
    (_sum("sale_dollars") - _sum(col("state_bottle_cost") * col("sale_bottles"))).alias("tot_profit_dollars"),
    _sum("sale_liters").alias("sale_liters"),
    _sum("sale_gallons").alias("sale_gallons")
)

f003_product_tot_sales = raw_sales.groupBy(
    "kafka_topic",
    to_date("process_date", 'yyyy-MM-dd').alias("prd_id"),
    "hour_id",
    "category_name",
    "im_desc"
).agg(
    _sum("sale_bottles").alias("sale_bottles"),
    _sum(col("state_bottle_cost") * col("sale_bottles")).alias("tot_cost_dollars"),
    _sum("sale_dollars").alias("tot_sale_dollars"),
    (_sum("sale_dollars") - _sum(col("state_bottle_cost") * col("sale_bottles"))).alias("tot_profit_dollars"),
    _sum("sale_liters").alias("sale_liters"),
    _sum("sale_gallons").alias("sale_gallons")
)

queries = [
    {"name": "f001_store_tot_sales", "df": f001_store_tot_sales},
    {"name": "f002_vendor_tot_sales", "df": f002_vendor_tot_sales},
    {"name": "f003_product_tot_sales", "df": f003_product_tot_sales},
]

# Ghi dữ liệu vào bộ nhớ tạm và HDFS
for query in queries:
    query["stream"] = query["df"].writeStream \
        .outputMode("complete") \
        .format("memory") \
        .queryName(query["name"]) \
        .option("checkpointLocation", f"hdfs://namenode:9000/work_zone/tmp/bi_streaming/spark/checkpoint/{query['name']}") \
        .trigger(processingTime="5 minutes") \
        .start()

# Hàm chuyển đổi định dạng thời gian
def convert_to_mariadb_datetime(iso_time):
    return datetime.strptime(iso_time, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d %H:%M:%S")

# Hàm ghi log vào MariaDB
def write_log_to_db(app_name, table_name, batch_start_time, batch_end_time, processing_time_seconds, record_count, status, error_details=None):
    try:
        # Chuyển đổi thời gian sang định dạng MariaDB
        batch_start_time = convert_to_mariadb_datetime(batch_start_time)
        batch_end_time = convert_to_mariadb_datetime(batch_end_time)

        conn = mysql.connector.connect(
            host="mariadb",
            database="datalake",
            user="datalake",
            password="123456"
        )
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO streaming_logs (
                app_name, table_name, batch_start_time, batch_end_time, processing_time_seconds, record_count, status, error_details
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (app_name, table_name, batch_start_time, batch_end_time, processing_time_seconds, record_count, status, error_details))
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        logger.error(f"Error inserting log into MariaDB: {e}")

# Vòng lặp xử lý batch
while True:
    try:
        for query in queries:
            spark_query = next((q for q in spark.streams.active if q.name == query["name"]), None)
            if spark_query:
                progress = spark_query.lastProgress
                if progress and progress['sources'][0]['numInputRows'] > 0:
                    batch_start_time = progress['timestamp']
                    batch_end_time = datetime.utcnow().isoformat() + "Z"  # Lấy thời gian hiện tại
                    processing_time_seconds = progress['durationMs']['triggerExecution'] / 1000
                    record_count = progress['sources'][0]['numInputRows']

                    try:
                        data_from_memory = spark.sql(f"SELECT * FROM {query['name']}")
                        data_from_memory.write.mode("append").parquet(
                            f"hdfs://namenode:9000/gold_zone/sales/bi_core/streaming/country=usa/state=iowa/{query['name']}"
                        )
                        spark.catalog.uncacheTable(query["name"])

                        # Ghi log thành công
                        write_log_to_db(
                            app_name="LIQUOR_SALES_BI_STREAMING",
                            table_name=query["name"],
                            batch_start_time=batch_start_time,
                            batch_end_time=batch_end_time,
                            processing_time_seconds=processing_time_seconds,
                            record_count=record_count,
                            status="succeed"
                        )
                    except Exception as e:
                        logger.error(f"Error while writing to HDFS: {e}")
                        write_log_to_db(
                            app_name="LIQUOR_SALES_BI_STREAMING",
                            table_name=query["name"],
                            batch_start_time=batch_start_time,
                            batch_end_time=batch_end_time,
                            processing_time_seconds=processing_time_seconds,
                            record_count=record_count,
                            status="error",
                            error_details=str(e)
                        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

    # Đợi một phút trước khi kiểm tra lại
    time.sleep(60)

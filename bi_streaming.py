from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, sum as _sum, count
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

# Define schema for incoming data
schema = StructType([
    StructField("invoice_line_no", StringType(), True),
    StructField("date", StringType(), True),
    StructField("store", StringType(), True),
    StructField("name", StringType(), True),
    StructField("address", StringType(), True),
    StructField("city", StringType(), True),
    StructField("zipcode", StringType(), True),
    StructField("store_location", StringType(), True),
    StructField("county_number", StringType(), True),
    StructField("county", StringType(), True),
    StructField("category", StringType(), True),
    StructField("category_name", StringType(), True),
    StructField("vendor_no", StringType(), True),
    StructField("vendor_name", StringType(), True),
    StructField("itemno", StringType(), True),
    StructField("im_desc", StringType(), True),
    StructField("pack", StringType(), True),
    StructField("bottle_volume_ml", StringType(), True),
    StructField("state_bottle_cost", DoubleType(), True),
    StructField("state_bottle_retail", DoubleType(), True),
    StructField("sale_bottles", DoubleType(), True),
    StructField("sale_dollars", DoubleType(), True),
    StructField("sale_liters", DoubleType(), True),
    StructField("sale_gallons", DoubleType(), True)
])

# Create SparkSession
spark = SparkSession.builder \
    .appName("KafkaSparkStreaming") \
    .master("spark://spark-master:7077") \
    .config("spark.sql.streaming.checkpointLocation", "hdfs://namenode:9000/work_zone/streaming/checkpoint") \
    .getOrCreate()

# Read data from Kafka
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka0:9092,kafka1:9092,kafka2:9092") \
    .option("subscribe", "liquor_sales") \
    .option("startingOffsets", "earliest") \
    .load()

# Parse the Kafka value as JSON
data = df.selectExpr("CAST(value AS STRING) as json") \
         .select(from_json(col("json"), schema).alias("data")) \
         .select("data.*")

# Perform aggregations
aggregated_data = data.groupBy("store") \
    .agg(
        _sum("sale_dollars").alias("total_sales_dollars"),
        _sum("sale_bottles").alias("total_bottles_sold"),
        count("invoice_line_no").alias("total_transactions")
    )

# Write the output to the console
query = aggregated_data.writeStream \
    .outputMode("complete") \
    .format("console") \
    .start()

query.awaitTermination()
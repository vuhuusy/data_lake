import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

# Cấu hình logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Khởi tạo SparkSession
spark = SparkSession.builder \
    .appName("KafkaStructuredStreaming") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.2.1") \
    .getOrCreate()

# Đọc dữ liệu từ Kafka
kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka0:9092,kafka1:9092,kafka2:9092") \
    .option("subscribe", "test") \
    .option("startingOffsets", "earliest") \
    .load()

# Định nghĩa schema
json_schema = StructType([
    StructField("field1", StringType(), True),
    StructField("field2", IntegerType(), True)
])

# Xử lý dữ liệu
kafka_df = kafka_df.withColumn("value", col("value").cast("string"))
parsed_df = kafka_df.withColumn("data", from_json(col("value"), json_schema))

# Sử dụng foreachBatch để đếm số bản ghi trong mỗi batch
def process_batch(batch_df, batch_id):
    # Đếm số lượng bản ghi trong batch
    record_count = batch_df.count()
    logger.error(f"Batch ID: {batch_id}, Record Count: {record_count}")

query = parsed_df.writeStream \
    .foreachBatch(process_batch) \
    .start()

query.awaitTermination()

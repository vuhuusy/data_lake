from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, when, date_format, to_date, expr, sequence, weekofyear

# Tạo SparkSession
spark = SparkSession.builder \
    .appName("DIM_IOWA_DATE") \
    .config("spark.sql.shuffle.partitions", 1) \
    .getOrCreate()

# Khởi tạo ngày bắt đầu và kết thúc
start_date = "2020-01-01"
end_date = "2030-12-31"

# Tạo range ngày
date_range = spark.sql(f"SELECT sequence(to_date('{start_date}'), to_date('{end_date}'), interval 1 day) as date_seq")

# Expand range thành từng dòng
expanded_dates = date_range.selectExpr("explode(date_seq) as full_date")

# Danh sách các ngày lễ cố định
fixed_holidays = [
    "01-01",  # New Year’s Day
    "07-04",  # Independence Day
    "11-11",  # Veterans Day
    "12-25",  # Christmas Day
]

# Tính toán các trường cần thiết
dim_iowa_date = expanded_dates \
    .withColumn("date_key", date_format(col("full_date"), "yyyy-MM-dd")) \
    .withColumn("day_of_week", date_format(col("full_date"), "EEEE")) \
    .withColumn("day_of_month", date_format(col("full_date"), "dd")) \
    .withColumn("month", date_format(col("full_date"), "MM")) \
    .withColumn("month_name", date_format(col("full_date"), "MMMM")) \
    .withColumn("quarter", expr("quarter(full_date)")) \
    .withColumn("year", date_format(col("full_date"), "yyyy")) \
    .withColumn("year_month", date_format(col("full_date"), "yyyyMM")) \
    .withColumn("is_weekend", when(col("day_of_week").isin("Saturday", "Sunday"), lit("weekend")).otherwise(lit("weekday"))) \
    .withColumn("is_holiday", 
        when(date_format(col("full_date"), "MM-dd").isin(fixed_holidays), lit("yes"))
        .when(
            # Martin Luther King Jr. Day (Thứ hai thứ ba của tháng 1)
            (date_format(col("full_date"), "MM") == "01") & (weekofyear(col("full_date")) == 3) & (col("day_of_week") == "Monday"), lit("yes")
        )
        .when(
            # Presidents' Day (Thứ hai thứ ba của tháng 2)
            (date_format(col("full_date"), "MM") == "02") & (weekofyear(col("full_date")) == 3) & (col("day_of_week") == "Monday"), lit("yes")
        )
        .when(
            # Memorial Day (Thứ hai cuối cùng của tháng 5)
            (date_format(col("full_date"), "MM") == "05") & (expr("day(full_date) > 24")) & (col("day_of_week") == "Monday"), lit("yes")
        )
        .when(
            # Labor Day (Thứ hai đầu tiên của tháng 9)
            (date_format(col("full_date"), "MM") == "09") & (expr("day(full_date) <= 7")) & (col("day_of_week") == "Monday"), lit("yes")
        )
        .when(
            # Thanksgiving Day (Thứ năm thứ tư của tháng 11)
            (date_format(col("full_date"), "MM") == "11") & (weekofyear(col("full_date")) == 4) & (col("day_of_week") == "Thursday"), lit("yes")
        )
        .otherwise(lit("no"))
    ) \
    .withColumn("week_of_year", weekofyear(col("full_date")))

# Ghi dữ liệu vào HDFS (không phân vùng)
output_path = 'hdfs://namenode:9000/gold_zone/sales/bi_core/country=usa/state=iowa/dim_iowa_date/'
dim_iowa_date.write \
    .mode("overwrite") \
    .parquet(output_path)

print("dim_iowa_date table created and data written to:", output_path)

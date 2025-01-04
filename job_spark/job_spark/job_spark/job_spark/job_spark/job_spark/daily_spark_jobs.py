from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'syvh',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='daily_spark_jobs',
    default_args=default_args,
    description='Run daily Spark jobs at 2 AM',
    schedule_interval='0 2 * * *',  # Lịch chạy 2h sáng hàng ngày
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:

    product_daily = BashOperator(
        task_id='product_daily',
        bash_command='docker exec -it spark-master /spark/bin/spark-submit '
                     '--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.2.1 '
                     '--master spark://spark-master:7077 '
                     '/job_spark/product_daily.py'
    )

    store_daily = BashOperator(
        task_id='store_daily',
        bash_command='docker exec -it spark-master /spark/bin/spark-submit '
                     '--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.2.1 '
                     '--master spark://spark-master:7077 '
                     '/job_spark/store_daily.py'
    )

    sales_daily = BashOperator(
        task_id='sales_daily',
        bash_command='docker exec -it spark-master /spark/bin/spark-submit '
                     '--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.2.1 '
                     '--master spark://spark-master:7077 '
                     '/job_spark/sales_daily.py'
    )

    product_daily >> store_daily >> sales_daily
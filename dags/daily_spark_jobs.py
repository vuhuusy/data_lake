from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
from airflow.utils.email import send_email

# Hàm chung để gửi email với giao diện đẹp
def send_notification_email(context, status):
    task_id = context['task_instance'].task_id
    dag_id = context['task_instance'].dag_id
    execution_date = context['execution_date']
    start_date = context['task_instance'].start_date
    end_date = context['task_instance'].end_date
    log_url = context['task_instance'].log_url
    exception = context.get('exception', 'N/A')  # Lỗi cụ thể nếu có
    try_number = context['task_instance'].try_number

    # Icon và màu sắc dựa trên trạng thái
    if status == "Succeeded":
        icon = "✅"
        color = "#28a745"
    elif status == "Failed":
        icon = "❌"
        color = "#dc3545"
    elif status == "Timed Out":
        icon = "⚠️"
        color = "#ffc107"
    else:
        icon = "⚠️"
        color = "#17a2b8"

    # Tạo tiêu đề và nội dung email
    subject = f"{icon} Task {task_id} {status} in DAG {dag_id}"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6;">
        <h2 style="color: {color};">{icon} Task {status}</h2>
        <p><strong>Task:</strong> {task_id}</p>
        <p><strong>DAG:</strong> {dag_id}</p>
        <p><strong>Status:</strong> {status}</p>
        <p><strong>Execution Date:</strong> {execution_date}</p>
        <p><strong>Start Time:</strong> {start_date}</p>
        <p><strong>End Time:</strong> {end_date}</p>
        <p><strong>Try Number:</strong> {try_number}</p>
        <p><strong>Exception:</strong> {exception}</p>
        <p><strong>Log URL:</strong> <a href="{log_url}" style="color: #007bff; text-decoration: none;">View Logs</a></p>
    </body>
    </html>
    """

    # Kiểm tra email có được cấu hình không
    email = context['dag'].default_args.get('email', [])
    if email:
        send_email(email, subject, body)
    else:
        print("No email configured for notification.")

# Callback khi thành công, thất bại, hoặc timeout
def success_email(context):
    send_notification_email(context, "Succeeded")

def failure_email(context):
    send_notification_email(context, "Failed")

def timeout_email(context):
    send_notification_email(context, "Timed Out")

# Cấu hình mặc định
default_args = {
    'owner': 'syvh',
    'depends_on_past': False,
    'email': ['syvh.de@gmail.com'],  # Email nhận thông báo
    'email_on_failure': True,        # Gửi email khi task thất bại
    'email_on_retry': True,          # Gửi email khi task retry
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=10),  # Timeout mặc định cho mỗi task
}

# Hàm tạo task BashOperator
def create_spark_task(task_id, script_name):
    return BashOperator(
        task_id=task_id,
        bash_command=f'docker exec -it spark-master /spark/bin/spark-submit '
                     f'--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.2.1 '
                     f'--master spark://spark-master:7077 '
                     f'/job_spark/{script_name}',
        on_success_callback=success_email,
        on_failure_callback=failure_email,
        on_retry_callback=failure_email,
        env={"SPARK_HOME": "/spark"}  # Thêm biến môi trường nếu cần
    )

# Định nghĩa DAG
with DAG(
    dag_id='daily_spark_jobs',
    default_args=default_args,
    description='Run daily Spark jobs at 2 AM',
    schedule_interval='0 2 * * *',  # Lịch chạy 2h sáng hàng ngày
    start_date=datetime(2024, 12, 18),
    catchup=False,
) as dag:

    # Tạo các task
    product_daily = create_spark_task('product_daily', 'product_daily.py')
    store_daily = create_spark_task('store_daily', 'store_daily.py')
    sales_daily = create_spark_task('sales_daily', 'sales_daily.py')

    # Xác định thứ tự chạy
    product_daily >> store_daily >> sales_daily

### MariaDB

docker exec -it mariadb mysql -u root -p

GRANT ALL PRIVILEGES ON datalake.* TO 'datalake'@'%' IDENTIFIED BY '123456';
FLUSH PRIVILEGES;


CREATE TABLE streaming_logs (
     app_name VARCHAR(255) NOT NULL,
     table_name VARCHAR(255) NOT NULL,
     batch_start_time TIMESTAMP NOT NULL,
     batch_end_time TIMESTAMP NOT NULL,
     processing_time_seconds DOUBLE NOT NULL,
     record_count BIGINT NOT NULL,
     status VARCHAR(50) NOT NULL,
     error_details TEXT,
     PRIMARY KEY (app_name, table_name, batch_start_time)
 );


### NiFi

docker cp ./nifi/conf/nifi.properties nifi0:/opt/nifi/nifi-current/conf/nifi.properties

docker cp ./nifi/conf/nifi.properties nifi1:/opt/nifi/nifi-current/conf/nifi.properties

docker cp ./nifi/conf/nifi.properties nifi2:/opt/nifi/nifi-current/conf/nifi.properties

docker restart nifi0 nifi1 nifi2

### Airflow

source airflow_env/bin/activate
airflow scheduler

source airflow_env/bin/activate
airflow webserver

Khi config 

List dag: airflow dags list
Kiểm tra folder lưu dags: airflow config get-value core dags_folder
Trigger dag thủ công: airflow dags trigger daily_spark_jobs (dag_id)

Gửi mail: thêm thông tin về ngày gửi, mức độ quan trọng (bthg, quan trọng, cần xử lý ngay,...)
- Người xử lý: syvh


### Spark Streaming

pip install mysql-connector-python



/spark/bin/spark-submit   --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.2.1   --master spark://spark-master:7077   --executor-memory 512M   --total-executor-cores 1   --driver-memory 512M   /job_spark/bi_streaming.py

nohup /spark/bin/spark-submit   --master spark://spark-master:7077  /job_spark/bi_streaming.py > /spark-job.log 2>&1 &/ 

docker exec -it spark-master bash

mkdir /job_spark


docker cp ./job_spark spark-master:/job_spark/

cd /spark/bin

/spark/bin/spark-submit \
--jars /spark/jars/spark-sql-kafka-0-10_2.12-3.2.1.jar \
--master spark://spark-master:7077 \
/job_spark/bi_streaming.py

/spark/bin/spark-submit \
--jars /spark/jars/spark-sql-kafka-0-10_2.12-3.2.1.jar \
--master spark://spark-master:7077 \
/job_spark/dim_date_generator.py

/spark/bin/spark-submit \
--jars /spark/jars/spark-sql-kafka-0-10_2.12-3.2.1.jar \
--master spark://spark-master:7077 \
/job_spark/sales.py

### Hive

URL connection trong DBeaver:

jdbc:hive2://localhost:10000/default
localhost
10000

Tăng tốc độ

SET hive.exec.parallel=true;


### Superset

docker load -i superset.tar

Cấu hình thời gian timeout cho câu query chart

SUPERSET_WEBSERVER_TIMEOUT = int(timedelta(minutes=5).total_seconds())

Phải run khi start service

docker exec -it superset superset fab create-admin \
              --username admin \
              --firstname Superset \
              --lastname Admin \
              --email syvh.de@gmail.com \
              --password admin
			  			  
docker exec -it superset superset db upgrade

docker exec -it superset superset init


Thư viện để connect với Hive: 

pip install pyhive[trino]
pip install thrift
pip install thrift-sasl

docker restart superset

hive://bi_app@hive-server:10000/default

### Zeppelin

We install Zeppelin in our local machine.

Create a new interpreter, name it to hive using group jdbc.

Hive interpreter configurations:
- **default.url**: jdbc:hive2://localhost:10000/default 
- **default.user**: hive
- **default.driver**: org.apache.hive.jdbc.HiveDriver 
- **Dependencies**:
    - org.apache.hive:hive-jdbc:0.14.0
    - org.apache.hadoop:hadoop-common:3.2.1
- **Other configs**: default value
  
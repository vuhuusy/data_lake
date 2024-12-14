### Superset

docker load -i superset.tar

Phải chạy câu lệnh dưới đây sau khi chạy docker compose up -d

docker exec -it superset superset fab create-admin \
              --username admin \
              --firstname Superset \
              --lastname Admin \
              --email syvh.de@gmail.com \
              --password admin
			  
			  
			  
docker exec -it superset superset db upgrade

docker exec -it superset superset init


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
 
 
 Gitlab
 
 root
 
 123456Sya^^
 
 gitlab-runner register \
  --url http://localhost \
  --token glrt-9yePnCW_3dFTHfACq2op 
  

Cổng 8080 của zeppelin và gitlab đang xung đột (service nào đó của gitlab cũng dùng cổng 8080)
  
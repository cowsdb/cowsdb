<img src="https://github.com/cowsdb/cowsdb/assets/1423657/0df1c101-4f0b-46ac-b33f-aa06cb74f11a" width=140>

# 🐄 CowsDB 

> CowsDB is a community maintained chdb/ClickHouse alternative server without corporate owners

<img src="https://github.com/cowsdb/cowsdb/assets/1423657/7d937499-9512-4a5f-b832-7a689112fc1e" width=600>


### Why not chdb?

_Cows are peaceful and produce milk. Snakes bite and poison._


> chdb was a great promise and we contributed to its inception and its bindings from the very beginning.<br>
> sadly it has been _"sold"_ by its main author to ClickHouse Inc. and is now controlled by a corporation.<br>
> This fork builds on the same technology stack without politics, redtape or hidden comemrcial interests.<br>


> 
## Features
**CowsDB** prentends to be _ClickHouse_ and can be used with any ClickHouse HTTP/S client

- In-process SQL OLAP Engine based on chdb/ClickHouse
- Designed for cloud services and microservices
- Not liked, endorsed or controlled by ClickHouse.

## Usage
```
docker run --rm -p 8123:8123 ghcr.io/cowsdb/cowsdb:latest
```

### Authentication
CowsDB queries default to stateless. Stateful sessions can be enabled with Basic HTTP Auth.

#### Play
CowsDB ships with a Play interface, just like ClickHouse
![image](https://github.com/cowsdb/cowsdb/assets/1423657/ea3f5546-0b24-40c4-93f7-a551ee976459)

#### Grafana
CowsDB can be used using the ClickHouse Grafana datasource via HTTP/S
![image](https://github.com/cowsdb/cowsdb/assets/1423657/e69c5a6d-1352-4bbd-ac31-2d4585f83663)

#### Superset
CowsDB can be used with Superset using the ClickHouse sqlalchemy driver
```
clickhouse+http://cowsdb-server:443/db?protocol=https
```
![image](https://github.com/cowsdb/cowsdb/assets/1423657/1a3956b4-c637-403e-ada6-579fde00554c)


### License
CowsDB is licensed under the AGPLv3 license and is not affiliated in any way with ClickHouse Inc. 

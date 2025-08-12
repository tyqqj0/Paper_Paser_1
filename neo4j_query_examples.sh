#!/bin/bash

# Neo4j 查询示例脚本
# 如果Browser有CORS问题，可以使用这些命令行查询

echo "=== Neo4j Literature Parser 数据探索 ==="

echo -e "\n📊 1. 数据概览："
sudo docker compose exec neo4j cypher-shell -u neo4j -p literature_parser_neo4j \
"MATCH (n) RETURN labels(n) as NodeType, count(n) as Count"

echo -e "\n📚 2. 查看所有文献："
sudo docker compose exec neo4j cypher-shell -u neo4j -p literature_parser_neo4j \
"MATCH (lit:Literature) 
RETURN lit.lid as LID, 
       substring(apoc.convert.fromJsonMap(lit.metadata).title, 0, 50) + '...' as Title,
       apoc.convert.fromJsonMap(lit.metadata).year as Year
ORDER BY lit.lid 
LIMIT 10"

echo -e "\n🎯 3. 查看Transformer论文详情："
sudo docker compose exec neo4j cypher-shell -u neo4j -p literature_parser_neo4j \
"MATCH (lit:Literature {lid: '2017-vaswani-aayn-b373'})
RETURN lit.lid as LID,
       apoc.convert.fromJsonMap(lit.metadata).title as Title,
       size(apoc.convert.fromJsonMap(lit.metadata).authors) as AuthorCount,
       apoc.convert.fromJsonMap(lit.metadata).year as Year"

echo -e "\n🔗 4. 查看别名映射："
sudo docker compose exec neo4j cypher-shell -u neo4j -p literature_parser_neo4j \
"MATCH (alias:Alias)-[:IDENTIFIES]->(lit:Literature) 
RETURN alias.alias_type as AliasType, 
       alias.alias_value as AliasValue, 
       lit.lid as LID 
LIMIT 5"

echo -e "\n📝 5. 查看任务状态："
sudo docker compose exec neo4j cypher-shell -u neo4j -p literature_parser_neo4j \
"MATCH (lit:Literature) 
WHERE lit.task_info IS NOT NULL
RETURN lit.lid as LID,
       apoc.convert.fromJsonMap(lit.task_info).status as TaskStatus"

echo -e "\n✅ 查询完成！如果Browser无法连接，可以运行 './neo4j_query_examples.sh' 进行数据查询"

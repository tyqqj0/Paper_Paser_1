#!/bin/bash

echo "🔍 检查Docker容器日志"
echo "====================================="

echo
echo "📊 检查所有容器状态:"
docker compose ps

echo
echo "🔧 API容器日志 (最后50行):"
echo "-------------------------------------"
docker compose logs --tail=50 api

echo
echo "👷 Worker容器日志 (最后50行):"
echo "-------------------------------------"
docker compose logs --tail=50 worker

echo
echo "📦 Redis容器日志 (最后20行):"
echo "-------------------------------------"
docker compose logs --tail=20 redis

echo
echo "🗄️ MongoDB容器日志 (最后20行):"
echo "-------------------------------------"
docker compose logs --tail=20 db

echo
echo "🌐 GROBID容器日志 (最后20行):"
echo "-------------------------------------"
docker compose logs --tail=50 grobid

echo
echo "====================================="
echo "🔍 日志检查完成"
read -p "按回车键继续..."

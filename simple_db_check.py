#!/usr/bin/env python3
"""简单检查数据库中的references数据"""

import subprocess
import json

def simple_db_check():
    """简单检查数据库"""
    print("=== 简单数据库检查 ===")
    
    # 检查文献总数
    cmd1 = ['docker', 'exec', 'paper_paser_1-db-1', 'mongosh', '--quiet', '--eval', 
            'use literature_parser; print(db.literatures.countDocuments({}));']
    
    try:
        result = subprocess.run(cmd1, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            total_count = result.stdout.strip().split('\n')[-1]
            print(f"总文献数: {total_count}")
        else:
            print(f"查询总数失败: {result.stderr}")
    except Exception as e:
        print(f"查询总数出错: {e}")
    
    # 检查有references的文献数
    cmd2 = ['docker', 'exec', 'paper_paser_1-db-1', 'mongosh', '--quiet', '--eval', 
            'use literature_parser; print(db.literatures.countDocuments({"references": {$exists: true, $ne: []}}));']
    
    try:
        result = subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            refs_count = result.stdout.strip().split('\n')[-1]
            print(f"有references的文献数: {refs_count}")
        else:
            print(f"查询references数失败: {result.stderr}")
    except Exception as e:
        print(f"查询references数出错: {e}")
    
    # 检查最新文献
    cmd3 = ['docker', 'exec', 'paper_paser_1-db-1', 'mongosh', '--quiet', '--eval', 
            '''use literature_parser; 
            var doc = db.literatures.findOne({}, {sort: {created_at: -1}});
            if (doc) {
                print("最新文献:");
                print("ID: " + doc._id);
                print("标题: " + (doc.metadata && doc.metadata.title ? doc.metadata.title : "N/A"));
                print("References数量: " + (doc.references ? doc.references.length : 0));
            }''']
    
    try:
        result = subprocess.run(cmd3, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"\n最新文献信息:")
            print(result.stdout.strip())
        else:
            print(f"查询最新文献失败: {result.stderr}")
    except Exception as e:
        print(f"查询最新文献出错: {e}")

if __name__ == '__main__':
    simple_db_check() 
#!/usr/bin/env python3
"""直接检查数据库中的references数据"""

import subprocess
import json


def check_database_references():
    """检查数据库中的references数据"""
    print("=== 检查数据库中的References数据 ===")

    # MongoDB查询脚本
    mongo_script = """
    use literature_parser;
    print("=== 数据库统计 ===");
    var total = db.literatures.countDocuments({});
    var withRefs = db.literatures.countDocuments({"references": {$exists: true, $not: {$size: 0}}});
    print("总文献数: " + total);
    print("有references的文献数: " + withRefs);
    if (total > 0) {
        print("比例: " + (withRefs/total*100).toFixed(1) + "%");
    }
    
    print("\\n=== 最新3个文献的references ===");
    db.literatures.find({}, {_id: 1, "metadata.title": 1, references: 1, created_at: 1})
      .sort({created_at: -1})
      .limit(3)
      .forEach(function(doc) {
        print("文献ID: " + doc._id);
        print("标题: " + (doc.metadata && doc.metadata.title ? doc.metadata.title : "N/A"));
        print("创建时间: " + doc.created_at);
        print("References数量: " + (doc.references ? doc.references.length : 0));
        if (doc.references && doc.references.length > 0) {
          var ref = doc.references[0];
          print("第一个reference:");
          print("  Source: " + (ref.source || "N/A"));
          print("  Parsed: " + (ref.parsed ? "Yes" : "No"));
          if (ref.parsed) {
            print("  Title: " + (ref.parsed.title || "N/A"));
            print("  Year: " + (ref.parsed.year || "N/A"));
          }
          print("  Raw: " + (ref.raw_text ? ref.raw_text.substring(0, 80) + "..." : "N/A"));
        }
        print("---");
      });
    """

    try:
        # 使用docker exec执行MongoDB查询
        result = subprocess.run(
            ["docker", "exec", "paper_paser_1-db-1", "mongosh", "--eval", mongo_script],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"MongoDB查询失败: {result.stderr}")

    except subprocess.TimeoutExpired:
        print("MongoDB查询超时")
    except Exception as e:
        print(f"查询出错: {e}")


def check_specific_literature():
    """检查特定文献的详细信息"""
    print("\n=== 检查特定文献的详细信息 ===")

    # 获取最新的一个文献ID
    mongo_script = """
    use literature_parser;
    var latest = db.literatures.findOne({}, {_id: 1}, {sort: {created_at: -1}});
    if (latest) {
        print(latest._id);
    }
    """

    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "paper_paser_1-db-1",
                "mongosh",
                "--quiet",
                "--eval",
                mongo_script,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            literature_id = result.stdout.strip()
            if literature_id:
                print(f"最新文献ID: {literature_id}")

                # 获取该文献的详细信息
                detailed_script = f"""
                use literature_parser;
                var doc = db.literatures.findOne({{_id: ObjectId("{literature_id}")}});
                if (doc) {{
                    print("=== 文献详情 ===");
                    print("标题: " + (doc.metadata && doc.metadata.title ? doc.metadata.title : "N/A"));
                    print("年份: " + (doc.metadata && doc.metadata.year ? doc.metadata.year : "N/A"));
                    print("作者数: " + (doc.metadata && doc.metadata.authors ? doc.metadata.authors.length : 0));
                    print("References数量: " + (doc.references ? doc.references.length : 0));
                    
                    if (doc.references && doc.references.length > 0) {{
                        print("\\n=== References详情 ===");
                        for (var i = 0; i < Math.min(3, doc.references.length); i++) {{
                            var ref = doc.references[i];
                            print("Reference " + (i+1) + ":");
                            print("  Source: " + (ref.source || "N/A"));
                            print("  Raw: " + (ref.raw_text ? ref.raw_text.substring(0, 100) + "..." : "N/A"));
                            print("  Parsed: " + (ref.parsed ? "Yes" : "No"));
                            if (ref.parsed) {{
                                print("    Title: " + (ref.parsed.title || "N/A"));
                                print("    Year: " + (ref.parsed.year || "N/A"));
                                print("    Authors: " + (ref.parsed.authors ? ref.parsed.authors.length + " 位" : "N/A"));
                                print("    Journal: " + (ref.parsed.journal || "N/A"));
                            }}
                            print("");
                        }}
                    }}
                }}
                """

                detail_result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "paper_paser_1-db-1",
                        "mongosh",
                        "--quiet",
                        "--eval",
                        detailed_script,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if detail_result.returncode == 0:
                    print(detail_result.stdout)
                else:
                    print(f"详细查询失败: {detail_result.stderr}")
            else:
                print("没有找到文献记录")

    except Exception as e:
        print(f"查询出错: {e}")


if __name__ == "__main__":
    check_database_references()
    check_specific_literature()

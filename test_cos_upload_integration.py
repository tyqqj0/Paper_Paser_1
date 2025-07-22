#!/usr/bin/env python3
"""
腾讯云COS文件上传集成测试脚本

测试完整的文件上传和文献处理流程：
1. 请求预签名URL
2. 模拟前端上传文件到COS
3. 提交文献处理任务
4. 验证文献处理结果
"""

import json
import os
import time
from typing import Dict, Any, Optional
import requests
from io import BytesIO


class COSUploadIntegrationTester:
    """COS上传集成测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
        
    def log_test(self, test_name: str, status: str, details: Dict[str, Any]):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "status": status,
            "timestamp": time.time(),
            "details": details
        }
        self.test_results.append(result)
        
        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_emoji} {test_name}: {status}")
        if details.get("message"):
            print(f"   {details['message']}")
    
    def create_test_pdf(self, size_kb: int = 10) -> bytes:
        """创建一个测试用的PDF文件"""
        # 创建一个简单的PDF内容
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Content) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
300
%%EOF
"""
        
        # 如果需要更大的文件，添加填充内容
        if size_kb > 1:
            padding_size = (size_kb * 1024) - len(pdf_content)
            if padding_size > 0:
                # 添加注释作为填充
                padding = b"\n% " + b"X" * (padding_size - 3) + b"\n"
                pdf_content = pdf_content[:-6] + padding + b"%%EOF\n"
        
        return pdf_content
    
    def test_request_upload_url(self) -> Optional[Dict[str, str]]:
        """测试请求上传URL"""
        try:
            request_data = {
                "fileName": "test_paper.pdf",
                "contentType": "application/pdf",
                "fileSize": 10240,  # 10KB
                "userId": "test_user_123"
            }
            
            response = requests.post(
                f"{self.base_url}/api/upload/request-url",
                json=request_data,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["uploadUrl", "publicUrl", "objectKey", "expires"]
                
                if all(field in data for field in required_fields):
                    self.log_test("请求上传URL", "PASS", {
                        "message": f"成功获取上传URL，对象键: {data['objectKey']}",
                        "object_key": data["objectKey"],
                        "expires": data["expires"]
                    })
                    return data
                else:
                    missing_fields = [f for f in required_fields if f not in data]
                    self.log_test("请求上传URL", "FAIL", {
                        "message": f"响应缺少必需字段: {missing_fields}",
                        "response": data
                    })
            else:
                self.log_test("请求上传URL", "FAIL", {
                    "message": f"HTTP错误: {response.status_code}",
                    "response": response.text
                })
                
        except Exception as e:
            self.log_test("请求上传URL", "FAIL", {
                "message": f"请求异常: {str(e)}"
            })
        
        return None
    
    def test_upload_to_cos(self, upload_info: Dict[str, str]) -> bool:
        """测试上传文件到COS"""
        try:
            # 创建测试PDF文件
            pdf_content = self.create_test_pdf(10)  # 10KB
            
            # 模拟前端上传到COS
            upload_response = requests.put(
                upload_info["uploadUrl"],
                data=pdf_content,
                headers={
                    "Content-Type": "application/pdf"
                },
                timeout=30
            )
            
            if upload_response.status_code in [200, 204]:
                self.log_test("上传文件到COS", "PASS", {
                    "message": f"成功上传文件到COS，大小: {len(pdf_content)} bytes",
                    "status_code": upload_response.status_code
                })
                return True
            else:
                self.log_test("上传文件到COS", "FAIL", {
                    "message": f"上传失败，HTTP状态: {upload_response.status_code}",
                    "response": upload_response.text
                })
                
        except Exception as e:
            self.log_test("上传文件到COS", "FAIL", {
                "message": f"上传异常: {str(e)}"
            })
        
        return False
    
    def test_check_upload_status(self, public_url: str) -> bool:
        """测试检查上传状态"""
        try:
            response = requests.get(
                f"{self.base_url}/api/upload/status",
                params={"public_url": public_url},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("exists"):
                    self.log_test("检查上传状态", "PASS", {
                        "message": f"文件存在，大小: {data.get('size', 'unknown')} bytes",
                        "file_info": data
                    })
                    return True
                else:
                    self.log_test("检查上传状态", "FAIL", {
                        "message": "文件不存在",
                        "response": data
                    })
            else:
                self.log_test("检查上传状态", "FAIL", {
                    "message": f"HTTP错误: {response.status_code}",
                    "response": response.text
                })
                
        except Exception as e:
            self.log_test("检查上传状态", "FAIL", {
                "message": f"请求异常: {str(e)}"
            })
        
        return False
    
    def test_literature_processing(self, public_url: str) -> Optional[str]:
        """测试文献处理"""
        try:
            # 提交文献处理任务
            literature_data = {
                "pdf_url": public_url,
                "title": "Test Paper from COS Upload"
            }
            
            response = requests.post(
                f"{self.base_url}/api/literature",
                json=literature_data,
                timeout=10
            )
            
            if response.status_code == 202:
                data = response.json()
                task_id = data.get("task_id")
                
                if task_id:
                    self.log_test("提交文献处理任务", "PASS", {
                        "message": f"成功提交任务: {task_id}",
                        "task_id": task_id
                    })
                    
                    # 等待任务完成
                    return self.wait_for_task_completion(task_id)
                else:
                    self.log_test("提交文献处理任务", "FAIL", {
                        "message": "响应中缺少task_id",
                        "response": data
                    })
            else:
                self.log_test("提交文献处理任务", "FAIL", {
                    "message": f"HTTP错误: {response.status_code}",
                    "response": response.text
                })
                
        except Exception as e:
            self.log_test("提交文献处理任务", "FAIL", {
                "message": f"请求异常: {str(e)}"
            })
        
        return None
    
    def wait_for_task_completion(self, task_id: str, max_wait: int = 120) -> Optional[str]:
        """等待任务完成"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = requests.get(
                    f"{self.base_url}/api/task/{task_id}",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    
                    if status in ["success_created", "success_duplicate"]:
                        literature_id = data.get("literature_id")
                        self.log_test("文献处理任务完成", "PASS", {
                            "message": f"任务完成，状态: {status}，文献ID: {literature_id}",
                            "task_id": task_id,
                            "literature_id": literature_id,
                            "status": status
                        })
                        return literature_id
                    elif status == "failure":
                        self.log_test("文献处理任务完成", "FAIL", {
                            "message": f"任务失败: {data.get('error', 'Unknown error')}",
                            "task_id": task_id,
                            "task_data": data
                        })
                        return None
                    else:
                        # 任务仍在进行中
                        print(f"   任务进行中: {status}")
                        time.sleep(3)
                        continue
                else:
                    self.log_test("查询任务状态", "FAIL", {
                        "message": f"HTTP错误: {response.status_code}",
                        "task_id": task_id
                    })
                    return None
                    
            except Exception as e:
                self.log_test("查询任务状态", "FAIL", {
                    "message": f"请求异常: {str(e)}",
                    "task_id": task_id
                })
                return None
        
        self.log_test("文献处理任务完成", "FAIL", {
            "message": f"任务超时（{max_wait}秒）",
            "task_id": task_id
        })
        return None
    
    def test_security_validation(self):
        """测试安全验证"""
        print("\n🔒 测试安全验证...")
        
        # 测试危险文件名
        dangerous_files = [
            "test.exe.pdf",  # 双扩展名
            "../../../etc/passwd.pdf",  # 路径遍历
            "CON.pdf",  # Windows保留名称
            "test<script>.pdf",  # 危险字符
            "a" * 300 + ".pdf",  # 过长文件名
        ]
        
        for filename in dangerous_files:
            try:
                request_data = {
                    "fileName": filename,
                    "contentType": "application/pdf",
                    "fileSize": 1024
                }
                
                response = requests.post(
                    f"{self.base_url}/api/upload/request-url",
                    json=request_data,
                    timeout=10
                )
                
                if response.status_code == 400:
                    self.log_test(f"安全验证-{filename[:20]}...", "PASS", {
                        "message": "正确拒绝危险文件名"
                    })
                else:
                    self.log_test(f"安全验证-{filename[:20]}...", "FAIL", {
                        "message": f"未能拒绝危险文件名，状态码: {response.status_code}"
                    })
                    
            except Exception as e:
                self.log_test(f"安全验证-{filename[:20]}...", "FAIL", {
                    "message": f"测试异常: {str(e)}"
                })
    
    def run_full_integration_test(self):
        """运行完整的集成测试"""
        print("🚀 开始COS文件上传集成测试...")
        print("=" * 60)
        
        # 1. 测试请求上传URL
        upload_info = self.test_request_upload_url()
        if not upload_info:
            print("❌ 无法获取上传URL，终止测试")
            return
        
        # 2. 测试上传文件到COS
        upload_success = self.test_upload_to_cos(upload_info)
        if not upload_success:
            print("❌ 文件上传失败，终止测试")
            return
        
        # 3. 等待一下让COS处理完成
        print("⏳ 等待COS处理完成...")
        time.sleep(3)
        
        # 4. 测试检查上传状态
        status_check = self.test_check_upload_status(upload_info["publicUrl"])
        if not status_check:
            print("⚠️ 文件状态检查失败，但继续测试文献处理")
        
        # 5. 测试文献处理
        literature_id = self.test_literature_processing(upload_info["publicUrl"])
        if literature_id:
            print(f"✅ 完整流程测试成功！文献ID: {literature_id}")
        else:
            print("❌ 文献处理失败")
        
        # 6. 测试安全验证
        self.test_security_validation()
        
        # 统计结果
        print("\n" + "=" * 60)
        print("📊 测试结果统计:")
        
        pass_count = len([r for r in self.test_results if r["status"] == "PASS"])
        fail_count = len([r for r in self.test_results if r["status"] == "FAIL"])
        warn_count = len([r for r in self.test_results if r["status"] == "WARN"])
        total_count = len(self.test_results)
        
        print(f"✅ 通过: {pass_count}")
        print(f"❌ 失败: {fail_count}")
        print(f"⚠️  警告: {warn_count}")
        print(f"📈 总计: {total_count}")
        
        if fail_count == 0:
            print("\n🎉 所有测试通过！COS上传集成功能正常！")
        else:
            print(f"\n⚠️  有 {fail_count} 个测试失败，需要检查配置和服务状态。")
        
        return {
            "pass": pass_count,
            "fail": fail_count,
            "warn": warn_count,
            "total": total_count,
            "results": self.test_results
        }


if __name__ == "__main__":
    tester = COSUploadIntegrationTester()
    results = tester.run_full_integration_test()
    
    # 保存详细结果
    with open("cos_upload_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 详细测试结果已保存到: cos_upload_test_results.json")

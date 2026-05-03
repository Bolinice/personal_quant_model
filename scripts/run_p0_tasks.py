"""
P0任务一键执行脚本

按顺序执行所有P0验证和修复任务：
1. 数据库字段迁移
2. 数据补充
3. 验证测试
4. 生成报告

执行前提：
- 数据库已初始化
- Tushare API token已配置
- 有足够的API调用额度
"""

import sys
import subprocess
from datetime import datetime
from pathlib import Path


class P0TaskRunner:
    """P0任务执行器"""

    def __init__(self):
        self.results = []
        self.start_time = datetime.now()

    def run_command(self, cmd: str, description: str):
        """运行命令并记录结果"""
        print(f"\n{'='*60}")
        print(f"执行: {description}")
        print(f"命令: {cmd}")
        print(f"{'='*60}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            if result.returncode == 0:
                print(f"✅ {description} - 成功")
                print(result.stdout)
                self.results.append({
                    'task': description,
                    'status': 'success',
                    'output': result.stdout
                })
                return True
            else:
                print(f"❌ {description} - 失败")
                print(result.stderr)
                self.results.append({
                    'task': description,
                    'status': 'failed',
                    'error': result.stderr
                })
                return False

        except subprocess.TimeoutExpired:
            print(f"⏱️  {description} - 超时")
            self.results.append({
                'task': description,
                'status': 'timeout'
            })
            return False
        except Exception as e:
            print(f"❌ {description} - 异常: {e}")
            self.results.append({
                'task': description,
                'status': 'error',
                'error': str(e)
            })
            return False

    def run_all(self):
        """执行所有P0任务"""
        print("="*60)
        print("P0任务执行开始")
        print(f"开始时间: {self.start_time}")
        print("="*60)

        # 任务1: 运行已完成的测试（验证修复）
        print("\n\n【阶段1】验证已完成的修复")
        self.run_command(
            "python -m pytest tests/test_pit_guard_multiversion.py -v",
            "任务1: 验证PIT多版本去重修复"
        )
        self.run_command(
            "python -m pytest tests/test_survivorship_bias.py -v",
            "任务2: 验证幸存者偏差修复"
        )

        # 任务2: 数据库迁移
        print("\n\n【阶段2】数据库字段迁移")
        self.run_command(
            "python scripts/migrate_add_pit_fields.py",
            "任务3: 添加PIT和行业历史字段"
        )

        # 任务3: 数据补充（可选，需要Tushare API）
        print("\n\n【阶段3】数据补充（可选）")
        print("⚠️  以下任务需要Tushare API，如果没有配置可以跳过")

        response = input("\n是否执行数据补充任务？(y/n): ")
        if response.lower() == 'y':
            self.run_command(
                "python scripts/backfill_financial_priority.py mark",
                "任务4: 标记财务数据优先级"
            )
            self.run_command(
                "python scripts/backfill_financial_priority.py create",
                "任务5: 创建业绩预告/快报表"
            )
            self.run_command(
                "python scripts/sync_industry_history.py sync",
                "任务6: 同步行业分类历史"
            )
        else:
            print("跳过数据补充任务")

        # 任务4: 数据验证
        print("\n\n【阶段4】数据完整性验证")
        self.run_command(
            "python scripts/sync_industry_history.py verify",
            "任务7: 验证行业分类历史数据"
        )

        # 任务5: 生成报告
        print("\n\n【阶段5】生成验证报告")
        self.generate_report()

    def generate_report(self):
        """生成执行报告"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        report = []
        report.append("="*60)
        report.append("P0任务执行报告")
        report.append("="*60)
        report.append(f"开始时间: {self.start_time}")
        report.append(f"结束时间: {end_time}")
        report.append(f"总耗时: {duration:.1f}秒")
        report.append("")

        # 统计
        success_count = sum(1 for r in self.results if r['status'] == 'success')
        failed_count = sum(1 for r in self.results if r['status'] == 'failed')
        error_count = sum(1 for r in self.results if r['status'] == 'error')
        timeout_count = sum(1 for r in self.results if r['status'] == 'timeout')

        report.append("执行统计:")
        report.append(f"  ✅ 成功: {success_count}")
        report.append(f"  ❌ 失败: {failed_count}")
        report.append(f"  ⚠️  错误: {error_count}")
        report.append(f"  ⏱️  超时: {timeout_count}")
        report.append("")

        # 详细结果
        report.append("详细结果:")
        for i, result in enumerate(self.results, 1):
            status_icon = {
                'success': '✅',
                'failed': '❌',
                'error': '⚠️',
                'timeout': '⏱️'
            }.get(result['status'], '❓')

            report.append(f"{i}. {status_icon} {result['task']}")
            if result['status'] != 'success':
                error_msg = result.get('error', 'Unknown error')
                report.append(f"   错误: {error_msg[:100]}")
        report.append("")

        # 下一步建议
        report.append("下一步建议:")
        if failed_count == 0 and error_count == 0:
            report.append("  ✅ 所有P0任务已完成！")
            report.append("  📋 可以开始P1性能优化任务")
            report.append("  📊 建议运行完整回测，对比修复前后的IC/收益差异")
        else:
            report.append("  ⚠️  部分任务失败，请检查错误信息")
            report.append("  📝 查看详细日志: document/P0_EXECUTION_LOG.txt")

        report.append("")
        report.append("="*60)

        # 打印报告
        report_text = "\n".join(report)
        print("\n" + report_text)

        # 保存报告
        report_file = Path("document/P0_EXECUTION_REPORT.txt")
        report_file.parent.mkdir(exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"\n报告已保存: {report_file}")


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     量化模型系统 P0 任务执行器                           ║
║                                                          ║
║     本脚本将执行以下任务：                               ║
║     1. 验证已完成的修复（PIT去重、幸存者偏差）           ║
║     2. 数据库字段迁移（添加优先级、历史时点字段）        ║
║     3. 数据补充（可选，需要Tushare API）                 ║
║     4. 数据完整性验证                                    ║
║     5. 生成执行报告                                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)

    response = input("是否继续执行？(y/n): ")
    if response.lower() != 'y':
        print("已取消")
        sys.exit(0)

    runner = P0TaskRunner()
    runner.run_all()


if __name__ == '__main__':
    main()
